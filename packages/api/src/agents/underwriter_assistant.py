# This project was developed with assistance from AI tools.
"""Underwriter assistant -- LangGraph agent for authenticated underwriters.

Tools include native tools (queue, detail, save, conditions, decisions)
plus MCP risk assessment tools loaded at startup from the MCP server.
"""

from typing import Any

from .base import build_agent_graph
from .compliance_check_tool import compliance_check
from .compliance_tools import kb_search
from .condition_tools import (
    uw_clear_condition,
    uw_condition_summary,
    uw_issue_condition,
    uw_return_condition,
    uw_review_condition,
    uw_waive_condition,
)
from .decision_tools import (
    uw_draft_adverse_action,
    uw_generate_cd,
    uw_generate_le,
    uw_render_decision,
)
from .mcp_integration import get_mcp_tools
from .tools import affordability_calc, current_date, product_info
from .underwriter_tools import (
    uw_application_detail,
    uw_preliminary_recommendation,
    uw_queue_view,
    uw_save_risk_assessment,
)


def build_graph(config: dict[str, Any], checkpointer=None):
    """Build a routed LangGraph graph for the underwriter assistant."""
    native_tools = [
        current_date,
        product_info,
        affordability_calc,
        uw_queue_view,
        uw_application_detail,
        uw_save_risk_assessment,
        uw_preliminary_recommendation,
        compliance_check,
        kb_search,
        uw_issue_condition,
        uw_review_condition,
        uw_clear_condition,
        uw_waive_condition,
        uw_return_condition,
        uw_condition_summary,
        uw_render_decision,
        uw_draft_adverse_action,
        uw_generate_le,
        uw_generate_cd,
    ]

    mcp_tools = get_mcp_tools()
    all_tools = native_tools + mcp_tools

    return build_agent_graph(
        config,
        all_tools,
        checkpointer=checkpointer,
    )
