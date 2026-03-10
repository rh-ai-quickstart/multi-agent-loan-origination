# This project was developed with assistance from AI tools.
"""Custom LangGraph graph with safety shields and rule-based model routing.

Graph structure:
    input_shield -> classify (rule-based) -> agent_fast / agent_capable
         |                                          |
         +-(blocked)-> END               tools <-> agent_capable -> output_shield -> END

The input_shield node calls Llama Guard on the user's message.  If unsafe, it
short-circuits to END with a refusal message.  The output_shield node checks the
agent's completed response and replaces it with a refusal if unsafe.

Shields are active when SAFETY_MODEL is configured; otherwise they are no-ops.
On any safety-model error the check is skipped (fail-open).

Rule-based routing with confidence escalation:
  - The classify node uses keyword/pattern rules (no LLM call) to decide
    SIMPLE vs COMPLEX routing.
  - COMPLEX -> agent_capable directly (tool-calling with reliable model)
  - SIMPLE  -> agent_fast (NO tools bound, text-only).  If the response
    indicates low confidence (via logprobs or hedging phrases), discard
    and escalate to agent_capable.

The fast model never sees tools, so it can never attempt tool calls.
Confidence escalation catches edge cases where a non-keyword query
slips through to fast but gets a garbage response.
"""

import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from ..inference.safety import get_safety_checker

logger = logging.getLogger(__name__)

SAFETY_REFUSAL_MESSAGE = (
    "I'm not able to help with that request. Can I assist you with something else?"
)

# -- Confidence escalation --------------------------------------------------

# Hedging phrases that indicate model uncertainty
_HEDGING_PHRASES = [
    "i'm not sure",
    "i don't know",
    "i cannot",
    "i can't",
    "you should consult",
    "please check",
    "i'd recommend asking",
    "beyond my",
    "outside my",
    "not certain",
]

# Logprob thresholds (calibrate against your model + quantization)
_LOGPROB_ESCALATION_THRESHOLD = -1.5  # mean logprob below this -> escalate
_HEDGING_ESCALATION_COUNT = 2  # 2+ hedging phrases -> escalate


def _low_confidence(response: AIMessage) -> bool:
    """Check if a fast model response indicates low confidence.

    Uses token logprobs (primary) and hedging phrase detection (secondary).
    Logprobs are a direct window into model uncertainty -- unlike self-reported
    confidence which is unreliable for small models.

    If logprobs are unavailable (model/backend doesn't support them), falls
    through to hedging detection only -- graceful degradation.
    """
    content = response.content or ""

    # Strip <think>...</think> blocks (reasoning models emit these)
    text = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    # Signal 1: Token logprobs (primary -- 0-latency, from same API call)
    logprobs_data = (response.response_metadata or {}).get("logprobs")
    if logprobs_data and logprobs_data.get("content"):
        token_logprobs = [
            t["logprob"] for t in logprobs_data["content"] if t.get("logprob") is not None
        ]
        if token_logprobs:
            mean_logprob = sum(token_logprobs) / len(token_logprobs)
            if mean_logprob < _LOGPROB_ESCALATION_THRESHOLD:
                return True

    # Signal 2: Hedging phrase detection (secondary -- regex, near-zero cost)
    text_lower = text.lower()
    hedge_count = sum(1 for phrase in _HEDGING_PHRASES if phrase in text_lower)
    if hedge_count >= _HEDGING_ESCALATION_COUNT:
        return True

    return False


class AgentState(MessagesState):
    """Graph state extended with model routing, safety, and auth fields."""

    model_tier: str
    safety_blocked: bool
    escalated: bool
    user_role: str
    user_id: str
    user_email: str
    user_name: str
    tool_allowed_roles: dict[str, list[str]]
    decision_proposals: dict


def build_routed_graph(
    *,
    system_prompt: str,
    tools: list,
    llms: dict[str, ChatOpenAI],
    tool_allowed_roles: dict[str, list[str]] | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """Build a compiled LangGraph graph with safety shields and rule-based routing.

    Args:
        system_prompt: The agent's system prompt (injected per LLM call).
        tools: LangChain tools available to the agent.
        llms: Mapping of tier name to ChatOpenAI instance.
        tool_allowed_roles: Mapping of tool name to list of allowed role strings.
            When provided, a pre-tool authorization node checks the user's role
            before each tool invocation (RBAC Layer 3).

    Returns:
        A compiled StateGraph with rule-based routing and confidence escalation.
    """
    fast_llm = llms["fast_small"]
    capable_llm = llms["capable_large"]

    async def input_shield(state: AgentState) -> dict:
        """Check user input against Llama Guard safety categories."""
        checker = get_safety_checker()
        if not checker:
            return {"safety_blocked": False}

        last_msg = state["messages"][-1]
        result = await checker.check_input(last_msg.content)
        if not result.is_safe:
            logger.warning("Input shield BLOCKED: categories=%s", result.violation_categories)
            return {
                "safety_blocked": True,
                "messages": [AIMessage(content=SAFETY_REFUSAL_MESSAGE)],
            }
        logger.debug("Input shield: safe")
        return {"safety_blocked": False}

    def after_input_shield(state: AgentState) -> str:
        """Route to END if input was blocked, otherwise continue to classify."""
        if state.get("safety_blocked"):
            return END
        return "classify"

    async def classify(state: AgentState) -> dict:
        """Rule-based intent classifier -- picks the model tier (no LLM call)."""
        from ..inference.router import classify_query

        last_msg = state["messages"][-1]
        tier = classify_query(last_msg.content)
        logger.info("Routed to '%s' for: %s", tier, last_msg.content[:80])
        return {"model_tier": tier}

    def after_classify(state: AgentState) -> str:
        """Route to agent_fast for SIMPLE, agent_capable for COMPLEX."""
        tier = state.get("model_tier", "capable_large")
        if tier == "fast_small":
            return "agent_fast"
        return "agent_capable"

    async def agent_fast(state: AgentState) -> dict:
        """Fast model pass (NO tools bound, text-only).

        Requests logprobs for confidence scoring. If the response
        indicates low confidence (low logprobs or hedging phrases),
        the response is discarded and the graph escalates to
        agent_capable.
        """
        # TODO: re-enable logprobs once LiteLLM proxy fixes MockValSer
        # Pydantic serialization bug in streaming responses with logprobs.
        # When re-enabling, also unskip test_fast_model_low_logprobs_escalates
        # in tests/test_chat.py.
        # llm_with_logprobs = fast_llm.bind(logprobs=True)
        messages = [SystemMessage(content=system_prompt), *state["messages"]]
        # response = await llm_with_logprobs.ainvoke(messages)
        response = await fast_llm.ainvoke(messages)

        # if _low_confidence(response):
        #     logger.info("Fast model low confidence, escalating to capable_large")
        #     return {"escalated": True}

        return {"messages": [response]}

    def after_agent_fast(state: AgentState) -> str:
        """Route to agent_capable if fast model response was low confidence."""
        if state.get("escalated"):
            return "agent_capable"
        return "output_shield"

    async def agent_capable(state: AgentState) -> dict:
        """Call the capable LLM with tools bound (reliable tool-calling)."""
        llm = capable_llm.bind_tools(tools)
        messages = [SystemMessage(content=system_prompt), *state["messages"]]
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        """Route to tool_auth (or tools) if the LLM made tool calls, else output shield."""
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tool_auth" if tool_allowed_roles else "tools"
        return "output_shield"

    async def tool_auth(state: AgentState) -> dict:
        """Pre-tool authorization node (RBAC Layer 3).

        Checks each pending tool call against allowed_roles for the user's role.
        Authorized calls proceed; unauthorized calls are replaced with an error
        message back to the agent.
        """
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {}

        user_role = state.get("user_role", "")
        user_id = state.get("user_id", "anonymous")
        # Use graph-level defaults only -- never allow state to override roles
        roles_map = dict(tool_allowed_roles or {})

        blocked: list[str] = []
        for tc in last.tool_calls:
            allowed = roles_map.get(tc["name"])
            if allowed is not None and user_role not in allowed:
                blocked.append(tc["name"])
                logger.warning(
                    "Tool auth DENIED: user=%s role=%s tool=%s allowed=%s",
                    user_id,
                    user_role,
                    tc["name"],
                    allowed,
                )

        if not blocked:
            return {}

        # Return an error message so the agent can inform the user
        denied_list = ", ".join(blocked)
        return {
            "messages": [
                AIMessage(
                    content=f"Tool authorization denied: your role '{user_role}' "
                    f"is not permitted to use: {denied_list}. "
                    "Please let the user know you cannot perform that action."
                )
            ]
        }

    def after_tool_auth(state: AgentState) -> str:
        """Route to tools if auth passed, back to agent if blocked."""
        last = state["messages"][-1]
        # If tool_auth injected an AIMessage (denial), go to output_shield
        if isinstance(last, AIMessage) and not last.tool_calls:
            return "output_shield"
        return "tools"

    async def output_shield(state: AgentState) -> dict:
        """Check agent output against Llama Guard safety categories."""
        checker = get_safety_checker()
        if not checker:
            return {}

        last_msg = state["messages"][-1]
        if not isinstance(last_msg, AIMessage) or not last_msg.content:
            return {}

        user_msg = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_msg = msg.content
                break

        result = await checker.check_output(user_msg, last_msg.content)
        if not result.is_safe:
            logger.warning("Output shield BLOCKED: categories=%s", result.violation_categories)
            return {"messages": [AIMessage(content=SAFETY_REFUSAL_MESSAGE)]}
        logger.debug("Output shield: safe")
        return {}

    tool_node = ToolNode(tools)

    graph = StateGraph(AgentState)
    graph.add_node("input_shield", input_shield)
    graph.add_node("classify", classify)
    graph.add_node("agent_fast", agent_fast)
    graph.add_node("agent_capable", agent_capable)
    graph.add_node("tools", tool_node)
    graph.add_node("output_shield", output_shield)

    graph.set_entry_point("input_shield")
    graph.add_conditional_edges(
        "input_shield", after_input_shield, {END: END, "classify": "classify"}
    )
    graph.add_conditional_edges(
        "classify",
        after_classify,
        {"agent_fast": "agent_fast", "agent_capable": "agent_capable"},
    )

    # Fast model path: high confidence -> output_shield, low confidence -> agent_capable
    graph.add_conditional_edges(
        "agent_fast",
        after_agent_fast,
        {"output_shield": "output_shield", "agent_capable": "agent_capable"},
    )

    # Capable model path: tool calls -> auth/tools loop, text -> output_shield
    if tool_allowed_roles:
        graph.add_node("tool_auth", tool_auth)
        graph.add_conditional_edges(
            "agent_capable",
            should_continue,
            {"tool_auth": "tool_auth", "output_shield": "output_shield"},
        )
        graph.add_conditional_edges(
            "tool_auth",
            after_tool_auth,
            {"tools": "tools", "output_shield": "output_shield"},
        )
    else:
        graph.add_conditional_edges(
            "agent_capable",
            should_continue,
            {"tools": "tools", "output_shield": "output_shield"},
        )

    graph.add_edge("tools", "agent_capable")
    graph.add_edge("output_shield", END)

    return graph.compile(checkpointer=checkpointer)


def build_agent_graph(
    config: dict[str, Any],
    tools: list,
    *,
    checkpointer=None,
):
    """Shared factory for building agent graphs from YAML config + tool list.

    Handles LLM initialization, tool_allowed_roles extraction, and
    build_routed_graph invocation -- the boilerplate common to all agents.
    """
    from ..inference.config import get_model_config, get_model_tiers

    system_prompt = config.get("system_prompt", "You are a helpful mortgage assistant.")

    tool_allowed_roles: dict[str, list[str]] = {}
    for tool_cfg in config.get("tools", []):
        name = tool_cfg.get("name")
        allowed = tool_cfg.get("allowed_roles")
        if name and allowed:
            tool_allowed_roles[name] = allowed

    llms: dict[str, ChatOpenAI] = {}
    for tier in get_model_tiers():
        model_cfg = get_model_config(tier)
        llms[tier] = ChatOpenAI(
            model=model_cfg["model_name"],
            base_url=model_cfg["endpoint"],
            api_key=model_cfg.get("api_key", "not-needed"),
        )

    return build_routed_graph(
        system_prompt=system_prompt,
        tools=tools,
        llms=llms,
        tool_allowed_roles=tool_allowed_roles,
        checkpointer=checkpointer,
    )
