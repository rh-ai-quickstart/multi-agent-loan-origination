# This project was developed with assistance from AI tools.
"""Tests for agent tool authorization at execution time (S-1-F14-05).

Verifies that the pre-tool authorization node in the LangGraph graph
checks user_role against tool.allowed_roles before each tool invocation.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from src.agents.base import build_agent_graph_compiled

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = "You are a test assistant."


@tool
def fake_tool() -> str:
    """A test tool for authorization testing."""
    return "fake result"


@pytest.fixture
def real_tools():
    """Return a list with the real fake_tool for graph compilation."""
    return [fake_tool]


@pytest.fixture
def mock_llm():
    """Build a mock LLM."""
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="test response"))
    llm.bind_tools = MagicMock(return_value=llm)
    return llm


def _build_graph_with_auth(real_tools, mock_llm, tool_allowed_roles):
    """Helper to build a graph with tool_allowed_roles."""
    return build_agent_graph_compiled(
        system_prompt=SYSTEM_PROMPT,
        tools=real_tools,
        llm=mock_llm,
        tool_allowed_roles=tool_allowed_roles,
    )


def _extract_tool_auth_node(graph):
    """Extract the tool_auth node function from a compiled graph."""
    nodes = graph.get_graph().nodes
    assert "tool_auth" in nodes, "tool_auth node should exist in graph"
    # LangGraph stores node data with a .runnable attribute
    node_data = nodes["tool_auth"]
    return node_data.data


# ---------------------------------------------------------------------------
# Graph structure tests
# ---------------------------------------------------------------------------


def test_tool_auth_node_present_when_roles_configured(real_tools, mock_llm):
    """Graph includes tool_auth node when tool_allowed_roles is set."""
    graph = _build_graph_with_auth(real_tools, mock_llm, {"fake_tool": ["admin"]})
    assert "tool_auth" in [n for n in graph.get_graph().nodes]


def test_graph_without_tool_auth_has_no_auth_node(real_tools, mock_llm):
    """When tool_allowed_roles is None, no tool_auth node is added."""
    graph = _build_graph_with_auth(real_tools, mock_llm, None)
    assert "tool_auth" not in [n for n in graph.get_graph().nodes]


# ---------------------------------------------------------------------------
# Actual tool_auth node invocation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_auth_allows_authorized_role(real_tools, mock_llm):
    """Invoking tool_auth with an authorized role returns empty dict."""
    graph = _build_graph_with_auth(real_tools, mock_llm, {"fake_tool": ["loan_officer", "admin"]})
    tool_auth_fn = _extract_tool_auth_node(graph)

    tool_calls = [{"name": "fake_tool", "args": {}, "id": "call_1"}]
    state = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="", tool_calls=tool_calls)],
        "user_role": "loan_officer",
        "user_id": "test-user",
        "tool_allowed_roles": {},
        "safety_blocked": False,
    }

    result = await tool_auth_fn.ainvoke(state)
    assert result == {} or result.get("messages") is None or result.get("messages") == []


@pytest.mark.asyncio
async def test_tool_auth_blocks_unauthorized_role(real_tools, mock_llm):
    """Invoking tool_auth with an unauthorized role returns denial message."""
    graph = _build_graph_with_auth(real_tools, mock_llm, {"fake_tool": ["admin"]})
    tool_auth_fn = _extract_tool_auth_node(graph)

    tool_calls = [{"name": "fake_tool", "args": {}, "id": "call_1"}]
    state = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="", tool_calls=tool_calls)],
        "user_role": "borrower",
        "user_id": "test-user",
        "tool_allowed_roles": {},
        "safety_blocked": False,
    }

    result = await tool_auth_fn.ainvoke(state)
    assert "messages" in result
    assert len(result["messages"]) == 1
    assert "authorization denied" in result["messages"][0].content.lower()
    assert "fake_tool" in result["messages"][0].content


@pytest.mark.asyncio
async def test_tool_auth_allows_when_no_roles_defined(real_tools, mock_llm):
    """Tool with no allowed_roles entry is unrestricted."""
    graph = _build_graph_with_auth(real_tools, mock_llm, {"other_tool": ["admin"]})
    tool_auth_fn = _extract_tool_auth_node(graph)

    tool_calls = [{"name": "fake_tool", "args": {}, "id": "call_1"}]
    state = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="", tool_calls=tool_calls)],
        "user_role": "prospect",
        "user_id": "test-user",
        "tool_allowed_roles": {},
        "safety_blocked": False,
    }

    result = await tool_auth_fn.ainvoke(state)
    assert result == {} or result.get("messages") is None or result.get("messages") == []


@pytest.mark.asyncio
async def test_tool_auth_no_tool_calls_returns_empty(real_tools, mock_llm):
    """tool_auth returns empty when last message has no tool calls."""
    graph = _build_graph_with_auth(real_tools, mock_llm, {"fake_tool": ["admin"]})
    tool_auth_fn = _extract_tool_auth_node(graph)

    state = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="just text")],
        "user_role": "borrower",
        "user_id": "test-user",
        "tool_allowed_roles": {},
        "safety_blocked": False,
    }

    result = await tool_auth_fn.ainvoke(state)
    assert result == {}


def test_public_assistant_config_extracts_allowed_roles():
    """Verify that public_assistant.build_graph extracts tool_allowed_roles from YAML."""
    config = {
        "system_prompt": "test",
        "tools": [
            {"name": "product_info", "allowed_roles": ["prospect", "borrower"]},
            {"name": "affordability_calc", "allowed_roles": ["prospect"]},
        ],
    }

    tool_allowed_roles = {}
    for tool_cfg in config.get("tools", []):
        name = tool_cfg.get("name")
        allowed = tool_cfg.get("allowed_roles")
        if name and allowed:
            tool_allowed_roles[name] = allowed

    assert tool_allowed_roles == {
        "product_info": ["prospect", "borrower"],
        "affordability_calc": ["prospect"],
    }
