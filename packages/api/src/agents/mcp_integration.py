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


async def init_mcp_client(url: str) -> None:
    """Connect to the MCP risk-assessment server and load tools."""
    global _client, _tools

    _client = MultiServerMCPClient(
        {
            "risk-assessment": {
                "transport": "streamable_http",
                "url": url,
            },
        }
    )
    _tools = await _client.get_tools()
    logger.info(
        "MCP client initialized: %d tools loaded from %s",
        len(_tools),
        url,
    )


async def shutdown_mcp_client() -> None:
    """Clean up MCP client references."""
    global _client, _tools
    _client = None
    _tools = []
    logger.info("MCP client shut down")


def get_mcp_tools() -> list:
    """Return the cached MCP tools as LangChain StructuredTool instances."""
    return list(_tools)
