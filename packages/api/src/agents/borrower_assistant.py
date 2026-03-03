# This project was developed with assistance from AI tools.
"""Borrower assistant -- LangGraph agent for authenticated borrowers.

Tools: product_info, affordability_calc, list_my_applications,
start_application, update_application_data, get_application_summary,
document_completeness, document_processing_status, application_status,
regulatory_deadlines, acknowledge_disclosure, disclosure_status,
rate_lock_status, list_conditions, respond_to_condition_tool,
check_condition_satisfaction.
"""

from typing import Any

from .base import build_agent_graph
from .borrower_tools import (
    acknowledge_disclosure,
    application_status,
    check_condition_satisfaction,
    disclosure_status,
    document_completeness,
    document_processing_status,
    get_application_summary,
    list_conditions,
    list_my_applications,
    rate_lock_status,
    regulatory_deadlines,
    respond_to_condition_tool,
    start_application,
    update_application_data,
)
from .tools import affordability_calc, product_info


def build_graph(config: dict[str, Any], checkpointer=None):
    """Build a routed LangGraph graph for the borrower assistant."""
    return build_agent_graph(
        config,
        [
            product_info,
            affordability_calc,
            list_my_applications,
            start_application,
            update_application_data,
            get_application_summary,
            document_completeness,
            document_processing_status,
            application_status,
            regulatory_deadlines,
            acknowledge_disclosure,
            disclosure_status,
            rate_lock_status,
            list_conditions,
            respond_to_condition_tool,
            check_condition_satisfaction,
        ],
        checkpointer=checkpointer,
    )
