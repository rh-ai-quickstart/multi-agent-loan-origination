# This project was developed with assistance from AI tools.
"""Custom LangGraph graph with safety shields.

Graph structure:
    input_shield -> agent -> tools <-> agent -> output_shield -> END

The input_shield node calls Llama Guard on the user's message.  If unsafe, it
short-circuits to END with a refusal message.  The output_shield node checks the
agent's completed response and replaces it with a refusal if unsafe.

Shields are active when SAFETY_MODEL is configured; otherwise they are no-ops.
On any safety-model error the check is skipped (fail-open).
"""

import logging
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


class AgentState(MessagesState):
    """Graph state extended with safety and auth fields."""

    safety_blocked: bool
    user_role: str
    user_id: str
    user_email: str
    user_name: str
    tool_allowed_roles: dict[str, list[str]]
    decision_proposals: dict


def build_agent_graph_compiled(
    *,
    system_prompt: str,
    tools: list,
    llm: ChatOpenAI,
    tool_allowed_roles: dict[str, list[str]] | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """Build a compiled LangGraph graph with safety shields.

    Args:
        system_prompt: The agent's system prompt (injected per LLM call).
        tools: LangChain tools available to the agent.
        llm: ChatOpenAI instance for the primary LLM.
        tool_allowed_roles: Mapping of tool name to list of allowed role strings.
            When provided, a pre-tool authorization node checks the user's role
            before each tool invocation (RBAC Layer 3).

    Returns:
        A compiled StateGraph.
    """

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
        """Route to END if input was blocked, otherwise continue to agent."""
        if state.get("safety_blocked"):
            return END
        return "agent"

    async def agent(state: AgentState) -> dict:
        """Call the LLM with tools bound."""
        bound_llm = llm.bind_tools(tools)
        messages = [SystemMessage(content=system_prompt), *state["messages"]]
        response = await bound_llm.ainvoke(messages)
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
    graph.add_node("agent", agent)
    graph.add_node("tools", tool_node)
    graph.add_node("output_shield", output_shield)

    graph.set_entry_point("input_shield")
    graph.add_conditional_edges("input_shield", after_input_shield, {END: END, "agent": "agent"})

    # Agent path: tool calls -> auth/tools loop, text -> output_shield
    if tool_allowed_roles:
        graph.add_node("tool_auth", tool_auth)
        graph.add_conditional_edges(
            "agent",
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
            "agent",
            should_continue,
            {"tools": "tools", "output_shield": "output_shield"},
        )

    graph.add_edge("tools", "agent")
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
    graph invocation -- the boilerplate common to all agents.
    """
    from ..inference.config import get_model_config

    system_prompt = config.get("system_prompt", "You are a helpful mortgage assistant.")

    # Inject agent name awareness when AGENT_NAME is set
    from ..core.config import Settings

    agent_name = Settings().AGENT_NAME
    if agent_name:
        system_prompt = f"Your name is {agent_name}.\n\n{system_prompt}"

    tool_allowed_roles: dict[str, list[str]] = {}
    for tool_cfg in config.get("tools", []):
        name = tool_cfg.get("name")
        allowed = tool_cfg.get("allowed_roles")
        if name and allowed:
            tool_allowed_roles[name] = allowed

    model_cfg = get_model_config("llm")
    llm = ChatOpenAI(
        model=model_cfg["model_name"],
        base_url=model_cfg["endpoint"],
        api_key=model_cfg.get("api_key", "not-needed"),
    )

    return build_agent_graph_compiled(
        system_prompt=system_prompt,
        tools=tools,
        llm=llm,
        tool_allowed_roles=tool_allowed_roles,
        checkpointer=checkpointer,
    )
