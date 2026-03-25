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

    mock_agent_response = AIMessage(content="Hello! How can I help?")
    mock_agent_response.tool_calls = []

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_agent_response)
    mock_llm.bind_tools.return_value = mock_llm

    from src.agents.base import build_agent_graph_compiled
    from src.agents.tools import affordability_calc, product_info

    tools = [product_info, affordability_calc]
    graph = build_agent_graph_compiled(
        system_prompt="test",
        tools=tools,
        llm=mock_llm,
    )

    result = await graph.ainvoke({"messages": [HumanMessage(content="Hello")]})

    assert not result.get("safety_blocked")
    assert result["messages"][-1].content == "Hello! How can I help?"


@pytest.mark.asyncio
async def test_output_shield_replaces_unsafe_response(_fresh_graph, monkeypatch):
    """should replace agent response with refusal when output is flagged unsafe."""
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage, HumanMessage

    from src.agents.base import SAFETY_REFUSAL_MESSAGE
    from src.inference.safety import SafetyChecker, SafetyResult

    mock_checker = AsyncMock(spec=SafetyChecker)
    mock_checker.check_input.return_value = SafetyResult(is_safe=True)
    mock_checker.check_output.return_value = SafetyResult(
        is_safe=False, violation_categories=["S6"]
    )
    monkeypatch.setattr("src.agents.base.get_safety_checker", lambda: mock_checker)

    mock_agent_response = AIMessage(content="Here is some unsafe advice")
    mock_agent_response.tool_calls = []

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_agent_response)
    mock_llm.bind_tools.return_value = mock_llm

    from src.agents.base import build_agent_graph_compiled
    from src.agents.tools import affordability_calc, product_info

    tools = [product_info, affordability_calc]
    graph = build_agent_graph_compiled(
        system_prompt="test",
        tools=tools,
        llm=mock_llm,
    )

    result = await graph.ainvoke({"messages": [HumanMessage(content="give me bad advice")]})

    assert result["messages"][-1].content == SAFETY_REFUSAL_MESSAGE
    mock_checker.check_input.assert_awaited_once()
    mock_checker.check_output.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_invokes_llm(_fresh_graph, monkeypatch):
    """should invoke the LLM and return its response."""
    from unittest.mock import AsyncMock, MagicMock

    from langchain_core.messages import AIMessage, HumanMessage

    monkeypatch.setattr("src.agents.base.get_safety_checker", lambda: None)

    agent_response = AIMessage(content="Based on your income of $95k...")
    agent_response.tool_calls = []

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=agent_response)
    mock_llm.bind_tools.return_value = mock_llm

    from src.agents.base import build_agent_graph_compiled
    from src.agents.tools import affordability_calc, product_info

    tools = [product_info, affordability_calc]
    graph = build_agent_graph_compiled(
        system_prompt="test",
        tools=tools,
        llm=mock_llm,
    )

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="Calculate affordability for $95k income")]}
    )

    assert result["messages"][-1].content == "Based on your income of $95k..."
    mock_llm.ainvoke.assert_awaited_once()
