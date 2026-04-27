# This project was developed with assistance from AI tools.
"""Tests for the A2A server module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.a2a_server import (
    AGENT_A2A_CONFIG,
    LoanAgentExecutor,
    _build_agent_card,
)


class TestAgentA2AConfig:
    """Verify agent A2A configuration completeness."""

    def test_all_five_agents_configured(self):
        assert len(AGENT_A2A_CONFIG) == 5

    def test_expected_agent_names(self):
        expected = {
            "public-assistant",
            "borrower-assistant",
            "loan-officer-assistant",
            "underwriter-assistant",
            "ceo-assistant",
        }
        assert set(AGENT_A2A_CONFIG.keys()) == expected

    def test_ports_are_unique(self):
        ports = [c["port"] for c in AGENT_A2A_CONFIG.values()]
        assert len(ports) == len(set(ports))

    def test_ports_in_expected_range(self):
        for name, config in AGENT_A2A_CONFIG.items():
            assert 8080 <= config["port"] <= 8084, f"{name} port out of range"

    def test_each_agent_has_skills(self):
        for name, config in AGENT_A2A_CONFIG.items():
            assert len(config["skills"]) >= 1, f"{name} has no skills"


class TestBuildAgentCard:
    """Verify AgentCard construction."""

    @pytest.mark.parametrize("agent_name", list(AGENT_A2A_CONFIG.keys()))
    def test_builds_valid_card(self, agent_name):
        port = AGENT_A2A_CONFIG[agent_name]["port"]
        card = _build_agent_card(agent_name, "0.0.0.0", port)

        assert card.name
        assert card.description
        assert len(card.skills) >= 1
        assert card.version == "1.0.0"
        assert card.capabilities.streaming is True

    def test_card_url_uses_host_and_port(self):
        card = _build_agent_card("public-assistant", "10.0.0.1", 9090)
        assert card.supported_interfaces[0].url == "http://10.0.0.1:9090/"

    def test_card_url_uses_agent_endpoint_env(self, monkeypatch):
        monkeypatch.setenv("AGENT_ENDPOINT", "https://my-agent.example.com")
        card = _build_agent_card("public-assistant", "0.0.0.0", 8080)
        assert card.supported_interfaces[0].url == "https://my-agent.example.com/"
        monkeypatch.delenv("AGENT_ENDPOINT")

    def test_unknown_agent_raises(self):
        with pytest.raises(KeyError):
            _build_agent_card("nonexistent-agent", "0.0.0.0", 9999)


class TestLoanAgentExecutorExtractResponse:
    """Verify response extraction from LangGraph results."""

    def test_extracts_last_ai_message(self):
        human = MagicMock(type="human", content="hello")
        ai = MagicMock(type="ai", content="I can help with that.")
        result = {"messages": [human, ai]}

        assert LoanAgentExecutor._extract_response(result) == "I can help with that."

    def test_skips_tool_messages(self):
        from langchain_core.messages import ToolMessage

        tool_msg = ToolMessage(content="tool result", tool_call_id="tc1")
        ai = MagicMock(type="ai", content="Based on the tool result...")
        result = {"messages": [ai, tool_msg]}

        assert LoanAgentExecutor._extract_response(result) == "Based on the tool result..."

    def test_skips_routing_messages(self):
        routing = MagicMock(type="ai", content="Routing to capable model")
        actual = MagicMock(type="ai", content="Here is your answer.")
        result = {"messages": [routing, actual]}

        assert LoanAgentExecutor._extract_response(result) == "Here is your answer."

    def test_returns_fallback_on_empty(self):
        result = {"messages": []}
        text = LoanAgentExecutor._extract_response(result)
        assert "try again" in text.lower()

    def test_handles_list_content(self):
        ai = MagicMock(type="ai", content=[{"text": "Part 1"}, {"text": "Part 2"}])
        result = {"messages": [ai]}

        assert LoanAgentExecutor._extract_response(result) == "Part 1 Part 2"

    def test_handles_none_messages(self):
        result = {"messages": None}
        text = LoanAgentExecutor._extract_response(result)
        assert "try again" in text.lower()


class TestLoanAgentExecutorExecute:
    """Verify the execute flow with mocked graph."""

    @pytest.fixture
    def executor(self):
        return LoanAgentExecutor("public-assistant")

    @pytest.fixture
    def mock_context(self):
        ctx = MagicMock()
        ctx.get_user_input.return_value = "What rates do you offer?"
        ctx.task_id = "task-123"
        ctx.context_id = "ctx-456"
        return ctx

    @pytest.fixture
    def mock_event_queue(self):
        eq = MagicMock()
        eq.enqueue_event = AsyncMock()
        return eq

    @pytest.mark.asyncio
    async def test_execute_happy_path(self, executor, mock_context, mock_event_queue):
        mock_graph = AsyncMock()
        mock_state = MagicMock()
        mock_state.values = {}
        mock_graph.get_state.return_value = mock_state

        ai_msg = MagicMock(type="ai", content="Our rates start at 6.5%.")
        mock_graph.ainvoke.return_value = {"messages": [ai_msg]}

        with patch("src.a2a_server.get_agent", return_value=mock_graph):
            await executor.execute(mock_context, mock_event_queue)

        mock_graph.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_no_input_raises(self, executor, mock_event_queue):
        ctx = MagicMock()
        ctx.get_user_input.return_value = ""

        with pytest.raises(Exception):
            await executor.execute(ctx, mock_event_queue)

    @pytest.mark.asyncio
    async def test_execute_handles_graph_error(self, executor, mock_context, mock_event_queue):
        mock_graph = AsyncMock()
        mock_state = MagicMock()
        mock_state.values = {}
        mock_graph.get_state.return_value = mock_state
        mock_graph.ainvoke.side_effect = RuntimeError("LLM timeout")

        with patch("src.a2a_server.get_agent", return_value=mock_graph):
            await executor.execute(mock_context, mock_event_queue)
