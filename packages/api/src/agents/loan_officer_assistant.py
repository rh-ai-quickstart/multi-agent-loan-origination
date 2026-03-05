# This project was developed with assistance from AI tools.
"""Loan officer assistant -- LangGraph agent for authenticated loan officers.

Tools: lo_pipeline_summary, lo_application_detail, lo_document_review,
lo_document_quality, lo_completeness_check, lo_mark_resubmission,
lo_underwriting_readiness, lo_submit_to_underwriting, lo_draft_communication,
lo_send_communication, lo_pull_credit, lo_prequalification_check,
lo_issue_prequalification, product_info, affordability_calc, kb_search.
"""

from typing import Any

from .base import build_agent_graph
from .compliance_tools import kb_search
from .loan_officer_tools import (
    lo_application_detail,
    lo_completeness_check,
    lo_document_quality,
    lo_document_review,
    lo_draft_communication,
    lo_issue_prequalification,
    lo_mark_resubmission,
    lo_pipeline_summary,
    lo_prequalification_check,
    lo_pull_credit,
    lo_send_communication,
    lo_submit_to_underwriting,
    lo_underwriting_readiness,
)
from .tools import affordability_calc, product_info


def build_graph(config: dict[str, Any], checkpointer=None):
    """Build a routed LangGraph graph for the loan officer assistant."""
    return build_agent_graph(
        config,
        [
            product_info,
            affordability_calc,
            lo_pipeline_summary,
            lo_application_detail,
            lo_document_review,
            lo_document_quality,
            lo_completeness_check,
            lo_mark_resubmission,
            lo_underwriting_readiness,
            lo_submit_to_underwriting,
            lo_draft_communication,
            lo_send_communication,
            lo_pull_credit,
            lo_prequalification_check,
            lo_issue_prequalification,
            kb_search,
        ],
        checkpointer=checkpointer,
    )
