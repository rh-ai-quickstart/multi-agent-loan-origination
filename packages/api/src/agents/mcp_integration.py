# This project was developed with assistance from AI tools.
"""MCP client lifecycle management for LangGraph agent integration.

Initializes a MultiServerMCPClient at app startup, caches the resulting
LangChain tools, and provides them to the underwriter agent graph.
"""

import logging

from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

_client: MultiServerMCPClient | None = None
_tools: list = []
_predictive_model_connected: bool = False


async def init_mcp_client(
    url: str,
    *,
    predictive_model_url: str | None = None,
) -> None:
    """Connect to MCP servers and load tools."""
    global _client, _tools, _predictive_model_connected

    servers: dict = {
        "risk-assessment": {
            "transport": "streamable_http",
            "url": url,
        },
    }
    if predictive_model_url:
        servers["predictive-model"] = {
            "transport": "streamable_http",
            "url": predictive_model_url,
        }

    _client = MultiServerMCPClient(servers)
    try:
        logger.info("Connecting to MCP servers: %s", list(servers.keys()))
        _tools = await _client.get_tools()
        _predictive_model_connected = predictive_model_url is not None
        logger.info(
            "MCP connected: %d tools, predictive=%s", len(_tools), _predictive_model_connected
        )
    except Exception as exc:
        logger.exception("MCP get_tools() failed: %s", exc)
        if predictive_model_url:
            logger.warning(
                "Predictive model MCP at %s unreachable, continuing without it",
                predictive_model_url,
            )
            _client = MultiServerMCPClient(
                {
                    "risk-assessment": {
                        "transport": "streamable_http",
                        "url": url,
                    },
                }
            )
            _tools = await _client.get_tools()
            _predictive_model_connected = False
        else:
            raise

    server_names = ["risk-assessment"]
    if _predictive_model_connected:
        server_names.append("predictive-model")
    logger.info(
        "MCP client initialized: %d tools loaded from %s",
        len(_tools),
        ", ".join(server_names),
    )


async def shutdown_mcp_client() -> None:
    """Clean up MCP client references."""
    global _client, _tools, _predictive_model_connected
    _client = None
    _tools = []
    _predictive_model_connected = False
    logger.info("MCP client shut down")


def get_mcp_tools() -> list:
    """Return the cached MCP tools as LangChain StructuredTool instances."""
    return list(_tools)


def is_predictive_model_available() -> bool:
    """Check whether the external predictive model MCP connected successfully."""
    return _predictive_model_connected


def get_predictive_tool():
    """Return the check_loan_approval tool instance, or None if unavailable."""
    if not _predictive_model_connected:
        return None
    for t in _tools:
        if t.name == "check_loan_approval":
            return t
    return None
