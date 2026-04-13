# This project was developed with assistance from AI tools.
"""Unit tests for MCP client integration module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.mcp_integration import (
    get_mcp_tools,
    get_predictive_tool,
    init_mcp_client,
    is_predictive_model_available,
    shutdown_mcp_client,
)


@pytest.fixture(autouse=True)
async def _clean_mcp_state():
    """Reset MCP module state before and after each test."""
    await shutdown_mcp_client()
    yield
    await shutdown_mcp_client()


class TestInitMcpClient:
    """Tests for MCP client initialization."""

    @pytest.mark.asyncio
    async def test_init_single_server(self):
        """Risk-assessment-only init loads tools and marks predictive unavailable."""
        mock_tools = [MagicMock(name="calculate_dti"), MagicMock(name="calculate_ltv")]

        with patch("src.agents.mcp_integration.MultiServerMCPClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get_tools = AsyncMock(return_value=mock_tools)
            mock_cls.return_value = mock_client

            await init_mcp_client("http://localhost:8081/mcp")

        assert len(get_mcp_tools()) == 2
        assert is_predictive_model_available() is False
        assert get_predictive_tool() is None

    @pytest.mark.asyncio
    async def test_init_two_servers(self):
        """Both servers configured loads all tools and marks predictive available."""
        mock_risk_tool = MagicMock(name="calculate_dti")
        mock_predict_tool = MagicMock()
        mock_predict_tool.name = "check_loan_approval"

        with patch("src.agents.mcp_integration.MultiServerMCPClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get_tools = AsyncMock(return_value=[mock_risk_tool, mock_predict_tool])
            mock_cls.return_value = mock_client

            await init_mcp_client(
                "http://localhost:8081/mcp",
                predictive_model_url="http://localhost:9090/mcp",
            )

        assert len(get_mcp_tools()) == 2
        assert is_predictive_model_available() is True
        assert get_predictive_tool() is mock_predict_tool

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Predictive model unreachable falls back to risk-assessment only."""
        mock_risk_tool = MagicMock(name="calculate_dti")

        call_count = 0

        def make_client(servers):
            nonlocal call_count
            call_count += 1
            client = AsyncMock()
            if call_count == 1 and len(servers) > 1:
                # First call with both servers fails
                client.get_tools = AsyncMock(side_effect=ConnectionError("predictive model down"))
            else:
                # Retry with just risk-assessment succeeds
                client.get_tools = AsyncMock(return_value=[mock_risk_tool])
            return client

        with patch(
            "src.agents.mcp_integration.MultiServerMCPClient",
            side_effect=make_client,
        ):
            await init_mcp_client(
                "http://localhost:8081/mcp",
                predictive_model_url="http://unreachable:9090/mcp",
            )

        assert len(get_mcp_tools()) == 1
        assert is_predictive_model_available() is False
        assert get_predictive_tool() is None

    @pytest.mark.asyncio
    async def test_risk_server_failure_raises(self):
        """Risk-assessment-only failure raises (no fallback)."""
        with patch("src.agents.mcp_integration.MultiServerMCPClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get_tools = AsyncMock(side_effect=ConnectionError("server down"))
            mock_cls.return_value = mock_client

            with pytest.raises(ConnectionError):
                await init_mcp_client("http://localhost:8081/mcp")


class TestShutdown:
    """Tests for MCP client shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self):
        """Shutdown resets all module state."""
        mock_tool = MagicMock()
        mock_tool.name = "check_loan_approval"

        with patch("src.agents.mcp_integration.MultiServerMCPClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get_tools = AsyncMock(return_value=[mock_tool])
            mock_cls.return_value = mock_client

            await init_mcp_client(
                "http://localhost:8081/mcp",
                predictive_model_url="http://localhost:9090/mcp",
            )

        assert is_predictive_model_available() is True

        await shutdown_mcp_client()

        assert get_mcp_tools() == []
        assert is_predictive_model_available() is False
        assert get_predictive_tool() is None
