# This project was developed with assistance from AI tools.
"""Tests for agent tools, registry, and WebSocket chat endpoint."""

import pytest
from fastapi.testclient import TestClient

from src.agents.registry import list_agents, load_agent_config
from src.agents.tools import affordability_calc, product_info
from src.core.config import settings
from src.main import app


@pytest.fixture(autouse=True)
def _disable_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DISABLED", True)


@pytest.fixture
def client():
    return TestClient(app)


# -- Tools --


def test_product_info_tool_returns_all_products():
    """product_info tool should return all 7 mortgage products."""
    result = product_info.invoke({})
    assert "30-Year Fixed Conventional" in result
    assert "FHA Loan" in result
    assert "VA Loan" in result
    assert "Adjustable Rate Mortgage" in result
    # Should have 7 products (7 bullet points)
    assert result.count("- **") == 7


def test_affordability_calc_tool_returns_estimate():
    """affordability_calc tool should return formatted estimate."""
    result = affordability_calc.invoke(
        {"gross_annual_income": 80000, "monthly_debts": 500, "down_payment": 20000}
    )
    assert "Max loan amount:" in result
    assert "Estimated monthly payment:" in result
    assert "DTI ratio:" in result


# -- Registry --


def test_list_agents_finds_public_assistant():
    """Agent registry should discover public-assistant from config dir."""
    agents = list_agents()
    assert "public-assistant" in agents


def test_load_agent_config_has_required_fields():
    """Agent config should have name, persona, and system_prompt."""
    config = load_agent_config("public-assistant")
    assert config["agent"]["name"] == "public_assistant"
    assert config["agent"]["persona"] == "prospect"
    assert "system_prompt" in config
    assert len(config["system_prompt"]) > 50


# -- WebSocket --


def test_websocket_rejects_invalid_json(client):
    """WebSocket should return error for non-JSON messages."""
    with client.websocket_connect("/api/chat") as ws:
        ws.send_text("not json")
        resp = ws.receive_json()
        assert resp["type"] == "error"
        assert "Invalid JSON" in resp["content"]


def test_websocket_rejects_missing_content(client):
    """WebSocket should return error for messages without content."""
    with client.websocket_connect("/api/chat") as ws:
        ws.send_json({"type": "message"})
        resp = ws.receive_json()
        assert resp["type"] == "error"


def test_existing_public_endpoint_still_works(client):
    """Refactoring affordability calc into services shouldn't break the route."""
    response = client.post(
        "/api/public/calculate-affordability",
        json={"gross_annual_income": 80000, "monthly_debts": 500, "down_payment": 20000},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["max_loan_amount"] > 0


# -- Safety shield graph integration --


@pytest.fixture
def _fresh_graph():
    """Clear the agent registry graph cache before and after each test."""
    from src.agents.registry import _graphs

    _graphs.clear()
    yield
    _graphs.clear()


@pytest.mark.asyncio
async def test_input_shield_blocks_unsafe_message(_fresh_graph, monkeypatch):
    """should short-circuit to END with refusal when input is flagged unsafe."""
    from unittest.mock import AsyncMock

    from langchain_core.messages import HumanMessage

    from src.agents.base import SAFETY_REFUSAL_MESSAGE
    from src.inference.safety import SafetyChecker, SafetyResult

    mock_checker = AsyncMock(spec=SafetyChecker)
    mock_checker.check_input.return_value = SafetyResult(is_safe=False, violation_categories=["S1"])
    monkeypatch.setattr("src.agents.base.get_safety_checker", lambda: mock_checker)

    from src.agents.registry import get_agent

    graph = get_agent("public-assistant")
    result = await graph.ainvoke({"messages": [HumanMessage(content="harmful request")]})

    assert result.get("safety_blocked") is True
    assert result["messages"][-1].content == SAFETY_REFUSAL_MESSAGE
    mock_checker.check_input.assert_awaited_once()
    mock_checker.check_output.assert_not_awaited()


@pytest.mark.asyncio
async def test_input_shield_passes_when_disabled(_fresh_graph, monkeypatch):
    """should not block when shields are disabled (get_safety_checker returns None).

    Verifies that safety_blocked is NOT set and the graph reaches the agent node.
    Uses mock LLMs to avoid hitting a real model endpoint.
    """
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage, HumanMessage

    monkeypatch.setattr("src.agents.base.get_safety_checker", lambda: None)
    # Route to capable so we only need the capable mock
    monkeypatch.setattr("src.inference.router.classify_query", lambda q: "capable_large")

    mock_fast = MagicMock()
    mock_fast.bind = MagicMock(return_value=mock_fast)

    mock_agent_response = AIMessage(content="Hello! How can I help?")
    mock_agent_response.tool_calls = []

    mock_agent_llm = MagicMock()
    mock_agent_llm.ainvoke = AsyncMock(return_value=mock_agent_response)
    mock_agent_llm.bind_tools.return_value = mock_agent_llm

    mock_llms = {"fast_small": mock_fast, "capable_large": mock_agent_llm}

    from src.agents.base import build_routed_graph
    from src.agents.tools import affordability_calc, product_info

    tools = [product_info, affordability_calc]
    graph = build_routed_graph(
        system_prompt="test",
        tools=tools,
        llms=mock_llms,
    )

    result = await graph.ainvoke({"messages": [HumanMessage(content="Hello")]})

    assert not result.get("safety_blocked")
    assert result["messages"][-1].content == "Hello! How can I help?"


@pytest.mark.asyncio
async def test_output_shield_replaces_unsafe_response(_fresh_graph, monkeypatch):
    """should replace agent response with refusal when output is flagged unsafe."""
    from unittest.mock import AsyncMock

    from langchain_core.messages import AIMessage, HumanMessage

    from src.agents.base import SAFETY_REFUSAL_MESSAGE
    from src.inference.safety import SafetyChecker, SafetyResult

    mock_checker = AsyncMock(spec=SafetyChecker)
    mock_checker.check_input.return_value = SafetyResult(is_safe=True)
    mock_checker.check_output.return_value = SafetyResult(
        is_safe=False, violation_categories=["S6"]
    )
    monkeypatch.setattr("src.agents.base.get_safety_checker", lambda: mock_checker)

    from unittest.mock import MagicMock

    # Route to capable so the graph reaches output_shield via agent_capable
    monkeypatch.setattr("src.inference.router.classify_query", lambda q: "capable_large")

    mock_fast = MagicMock()
    mock_fast.bind = MagicMock(return_value=mock_fast)

    mock_agent_response = AIMessage(content="Here is some unsafe advice")
    mock_agent_response.tool_calls = []

    mock_agent_llm = MagicMock()
    mock_agent_llm.ainvoke = AsyncMock(return_value=mock_agent_response)
    mock_agent_llm.bind_tools.return_value = mock_agent_llm

    mock_llms = {"fast_small": mock_fast, "capable_large": mock_agent_llm}

    from src.agents.base import build_routed_graph
    from src.agents.tools import affordability_calc, product_info

    tools = [product_info, affordability_calc]
    graph = build_routed_graph(
        system_prompt="test",
        tools=tools,
        llms=mock_llms,
    )

    result = await graph.ainvoke({"messages": [HumanMessage(content="give me bad advice")]})

    assert result["messages"][-1].content == SAFETY_REFUSAL_MESSAGE
    mock_checker.check_input.assert_awaited_once()
    mock_checker.check_output.assert_awaited_once()


# -- Rule-based model routing --


def test_rule_based_router_classifies_correctly():
    """Rule-based router handles simple patterns and long queries."""
    from src.inference.router import classify_query

    # "rate" is a complex keyword, so it routes to capable_large
    assert classify_query("what is your rate?") == "capable_large"
    # Simple pattern "what is" matches without complex keywords
    assert classify_query("what is my name?") == "fast_small"
    # Long query exceeds max_query_words -> capable
    assert classify_query("I earn $95k and want to buy a $400k home with 10% down") == (
        "capable_large"
    )


# -- Confidence escalation routing --


@pytest.mark.asyncio
async def test_simple_query_uses_fast_model(_fresh_graph, monkeypatch):
    """SIMPLE classification with high-confidence response stays on fast model."""
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage, HumanMessage

    monkeypatch.setattr("src.agents.base.get_safety_checker", lambda: None)
    # Force routing to fast_small
    monkeypatch.setattr("src.inference.router.classify_query", lambda q: "fast_small")

    # Fast model returns high-confidence response (good logprobs)
    fast_response = AIMessage(
        content="Hi there! How can I help?",
        response_metadata={
            "logprobs": {
                "content": [
                    {"logprob": -0.1},
                    {"logprob": -0.2},
                    {"logprob": -0.15},
                ]
            }
        },
    )

    mock_fast = MagicMock()
    mock_fast.bind = MagicMock(return_value=mock_fast)
    mock_fast.ainvoke = AsyncMock(return_value=fast_response)

    mock_capable = MagicMock()
    mock_capable.ainvoke = AsyncMock()
    mock_capable.bind_tools.return_value = mock_capable

    from src.agents.base import build_routed_graph
    from src.agents.tools import affordability_calc, product_info

    tools = [product_info, affordability_calc]
    graph = build_routed_graph(
        system_prompt="test",
        tools=tools,
        llms={"fast_small": mock_fast, "capable_large": mock_capable},
    )

    result = await graph.ainvoke({"messages": [HumanMessage(content="Hello")]})

    assert result["messages"][-1].content == "Hi there! How can I help?"
    # Capable model should NOT have been called
    mock_capable.ainvoke.assert_not_awaited()


@pytest.mark.skip(
    reason="Logprobs/escalation disabled -- LiteLLM MockValSer bug. Re-enable with confidence escalation in base.py agent_fast."
)
@pytest.mark.asyncio
async def test_fast_model_low_logprobs_escalates(_fresh_graph, monkeypatch):
    """should escalate to capable when fast model response has low logprobs."""
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage, HumanMessage

    monkeypatch.setattr("src.agents.base.get_safety_checker", lambda: None)
    monkeypatch.setattr("src.inference.router.classify_query", lambda q: "fast_small")

    # Fast model returns low-confidence response (bad logprobs)
    fast_response = AIMessage(
        content="Uh, maybe something about rates?",
        response_metadata={
            "logprobs": {
                "content": [
                    {"logprob": -2.5},
                    {"logprob": -3.0},
                    {"logprob": -2.8},
                ]
            }
        },
    )

    mock_fast = MagicMock()
    mock_fast.bind = MagicMock(return_value=mock_fast)
    mock_fast.ainvoke = AsyncMock(return_value=fast_response)

    # Capable model gives a proper response
    capable_response = AIMessage(content="Here are our mortgage products...")
    capable_response.tool_calls = []

    mock_capable = MagicMock()
    mock_capable.ainvoke = AsyncMock(return_value=capable_response)
    mock_capable.bind_tools.return_value = mock_capable

    from src.agents.base import build_routed_graph
    from src.agents.tools import affordability_calc, product_info

    tools = [product_info, affordability_calc]
    graph = build_routed_graph(
        system_prompt="test",
        tools=tools,
        llms={"fast_small": mock_fast, "capable_large": mock_capable},
    )

    result = await graph.ainvoke({"messages": [HumanMessage(content="Show me products")]})

    # Final response should be from capable model
    assert result["messages"][-1].content == "Here are our mortgage products..."
    mock_capable.ainvoke.assert_awaited_once()


@pytest.mark.skip(
    reason="Logprobs/escalation disabled -- LiteLLM MockValSer bug. Re-enable with confidence escalation in base.py agent_fast."
)
@pytest.mark.asyncio
async def test_fast_model_hedging_escalates(_fresh_graph, monkeypatch):
    """should escalate to capable when fast model uses multiple hedging phrases."""
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage, HumanMessage

    monkeypatch.setattr("src.agents.base.get_safety_checker", lambda: None)
    monkeypatch.setattr("src.inference.router.classify_query", lambda q: "fast_small")

    # Fast model hedges with 2+ phrases (no logprobs -- graceful degradation)
    fast_response = AIMessage(
        content="I'm not sure about that. I don't know the specifics.",
        response_metadata={},
    )

    mock_fast = MagicMock()
    mock_fast.bind = MagicMock(return_value=mock_fast)
    mock_fast.ainvoke = AsyncMock(return_value=fast_response)

    capable_response = AIMessage(content="Let me look that up for you...")
    capable_response.tool_calls = []

    mock_capable = MagicMock()
    mock_capable.ainvoke = AsyncMock(return_value=capable_response)
    mock_capable.bind_tools.return_value = mock_capable

    from src.agents.base import build_routed_graph
    from src.agents.tools import affordability_calc, product_info

    tools = [product_info, affordability_calc]
    graph = build_routed_graph(
        system_prompt="test",
        tools=tools,
        llms={"fast_small": mock_fast, "capable_large": mock_capable},
    )

    result = await graph.ainvoke({"messages": [HumanMessage(content="Tell me about rates")]})

    assert result["messages"][-1].content == "Let me look that up for you..."
    mock_capable.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_fast_model_no_logprobs_fallback(_fresh_graph, monkeypatch):
    """should fall through to hedging check when logprobs are unavailable."""
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage, HumanMessage

    monkeypatch.setattr("src.agents.base.get_safety_checker", lambda: None)
    monkeypatch.setattr("src.inference.router.classify_query", lambda q: "fast_small")

    # No logprobs, no hedging -- should stay on fast path
    fast_response = AIMessage(
        content="Welcome! I can help you with mortgage questions.",
        response_metadata={},
    )

    mock_fast = MagicMock()
    mock_fast.bind = MagicMock(return_value=mock_fast)
    mock_fast.ainvoke = AsyncMock(return_value=fast_response)

    mock_capable = MagicMock()
    mock_capable.ainvoke = AsyncMock()
    mock_capable.bind_tools.return_value = mock_capable

    from src.agents.base import build_routed_graph
    from src.agents.tools import affordability_calc, product_info

    tools = [product_info, affordability_calc]
    graph = build_routed_graph(
        system_prompt="test",
        tools=tools,
        llms={"fast_small": mock_fast, "capable_large": mock_capable},
    )

    result = await graph.ainvoke({"messages": [HumanMessage(content="Hi")]})

    assert result["messages"][-1].content == "Welcome! I can help you with mortgage questions."
    mock_capable.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_complex_query_skips_fast_model(_fresh_graph, monkeypatch):
    """COMPLEX classification goes directly to capable model."""
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage, HumanMessage

    monkeypatch.setattr("src.agents.base.get_safety_checker", lambda: None)
    # Force routing to capable_large
    monkeypatch.setattr("src.inference.router.classify_query", lambda q: "capable_large")

    mock_fast = MagicMock()
    mock_fast.bind = MagicMock(return_value=mock_fast)
    mock_fast.ainvoke = AsyncMock()

    capable_response = AIMessage(content="Based on your income of $95k...")
    capable_response.tool_calls = []

    mock_capable = MagicMock()
    mock_capable.ainvoke = AsyncMock(return_value=capable_response)
    mock_capable.bind_tools.return_value = mock_capable

    from src.agents.base import build_routed_graph
    from src.agents.tools import affordability_calc, product_info

    tools = [product_info, affordability_calc]
    graph = build_routed_graph(
        system_prompt="test",
        tools=tools,
        llms={"fast_small": mock_fast, "capable_large": mock_capable},
    )

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="Calculate affordability for $95k income")]}
    )

    assert result["messages"][-1].content == "Based on your income of $95k..."
    # Fast model should NOT have been called for agent_fast
    mock_fast.ainvoke.assert_not_awaited()
    # Capable model called for agent_capable
    mock_capable.ainvoke.assert_awaited_once()
