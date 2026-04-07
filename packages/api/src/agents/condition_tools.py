# This project was developed with assistance from AI tools.
"""LangGraph tools for underwriter condition lifecycle management.

Wraps condition service functions so the underwriter agent can issue,
review, clear, waive, return conditions, and view condition summaries.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  See underwriter_tools.py
    for rationale.
"""

from datetime import datetime
from typing import Annotated

from db.database import SessionLocal
from db.enums import ConditionSeverity
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..services.condition import (
    clear_condition,
    get_condition_summary,
    issue_condition,
    return_condition,
    review_condition,
    waive_condition,
)
from .shared import format_enum_label, resolve_app_id, user_context_from_state

_SEVERITY_MAP = {s.value: s for s in ConditionSeverity}


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="underwriter")


@tool
async def uw_issue_condition(
    application_id: int,
    description: str,
    severity: str = "prior_to_docs",
    due_date: str | None = None,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Issue a new underwriting condition on a loan application.

    Creates a condition in OPEN status. The borrower will be notified
    to respond. Only available during UNDERWRITING or CONDITIONAL_APPROVAL.

    Args:
        application_id: The loan application ID.
        description: What the borrower must provide or resolve.
        severity: One of prior_to_approval, prior_to_docs, prior_to_closing,
            prior_to_funding. Defaults to prior_to_docs.
        due_date: Optional ISO-8601 date string for the condition deadline.
    """
    application_id = resolve_app_id(application_id, state)
    user = _user_context_from_state(state)

    sev = _SEVERITY_MAP.get(severity.lower().strip())
    if sev is None:
        valid = ", ".join(sorted(_SEVERITY_MAP.keys()))
        return f"Invalid severity '{severity}'. Must be one of: {valid}"

    parsed_due: datetime | None = None
    if due_date:
        try:
            parsed_due = datetime.fromisoformat(due_date)
        except ValueError:
            return f"Invalid due_date format: '{due_date}'. Use ISO-8601 (e.g. 2026-03-15)."

    async with SessionLocal() as session:
        result = await issue_condition(
            session,
            user,
            application_id,
            description,
            sev,
            parsed_due,
        )

    if result is None:
        return f"Application #{application_id} not found or you don't have access to it."
    if "error" in result:
        return result["error"]

    due_str = f" (due: {result['due_date'][:10]})" if result.get("due_date") else ""
    return (
        f"Condition #{result['id']} issued: {description} (severity: {result['severity']}){due_str}"
    )


@tool
async def uw_review_condition(
    application_id: int,
    condition_id: int,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Move a condition from RESPONDED to UNDER_REVIEW.

    Call this after a borrower has responded to a condition and you want
    to begin reviewing their response and any linked documents.

    Args:
        application_id: The loan application ID.
        condition_id: The condition ID to review.
    """
    application_id = resolve_app_id(application_id, state)
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await review_condition(session, user, application_id, condition_id)

    if result is None:
        return (
            f"Condition #{condition_id} on application #{application_id} "
            f"not found or you don't have access."
        )
    if "error" in result:
        return result["error"]

    return f"Condition #{condition_id} now under review."


@tool
async def uw_clear_condition(
    application_id: int,
    condition_id: int,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Clear a condition after reviewing the borrower's response.

    Moves condition from RESPONDED or UNDER_REVIEW to CLEARED. Shows
    a summary of remaining conditions after clearing.

    Args:
        application_id: The loan application ID.
        condition_id: The condition ID to clear.
    """
    application_id = resolve_app_id(application_id, state)
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await clear_condition(session, user, application_id, condition_id)
        if result is None:
            return (
                f"Condition #{condition_id} on application #{application_id} "
                f"not found or you don't have access."
            )
        if "error" in result:
            return result["error"]

        # Get summary after clearing
        summary = await get_condition_summary(session, user, application_id)

    summary_text = ""
    if summary:
        parts = []
        for status, count in summary["counts"].items():
            if count > 0:
                parts.append(f"{status}: {count}")
        summary_text = f" Remaining: {', '.join(parts)}." if parts else " All conditions cleared."

    return f"Condition #{condition_id} cleared.{summary_text}"


@tool
async def uw_waive_condition(
    application_id: int,
    condition_id: int,
    rationale: str,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Waive a condition (PRIOR_TO_CLOSING or PRIOR_TO_FUNDING only).

    PRIOR_TO_APPROVAL and PRIOR_TO_DOCS conditions cannot be waived.
    A rationale is required for audit purposes.

    Args:
        application_id: The loan application ID.
        condition_id: The condition ID to waive.
        rationale: Explanation for why this condition is being waived.
    """
    application_id = resolve_app_id(application_id, state)
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await waive_condition(
            session,
            user,
            application_id,
            condition_id,
            rationale,
        )

    if result is None:
        return (
            f"Condition #{condition_id} on application #{application_id} "
            f"not found or you don't have access."
        )
    if "error" in result:
        return result["error"]

    return f"Condition #{condition_id} waived: {rationale}"


@tool
async def uw_return_condition(
    application_id: int,
    condition_id: int,
    note: str,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Return a condition to the borrower for additional information.

    Moves condition from UNDER_REVIEW back to OPEN with an explanatory note.
    Increments the iteration count to track return cycles.

    Args:
        application_id: The loan application ID.
        condition_id: The condition ID to return.
        note: Explanation of what's missing or needs correction.
    """
    application_id = resolve_app_id(application_id, state)
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await return_condition(
            session,
            user,
            application_id,
            condition_id,
            note,
        )

    if result is None:
        return (
            f"Condition #{condition_id} on application #{application_id} "
            f"not found or you don't have access."
        )
    if "error" in result:
        return result["error"]

    return f"Condition #{condition_id} returned (attempt {result['iteration_count']}): {note}"


@tool
async def uw_condition_summary(
    application_id: int,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Get a summary of condition counts by status for an application.

    Shows how many conditions are in each status (open, responded,
    under_review, cleared, waived, escalated).

    Args:
        application_id: The loan application ID.
    """
    application_id = resolve_app_id(application_id, state)
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await get_condition_summary(session, user, application_id)

    if result is None:
        return f"Application #{application_id} not found or you don't have access to it."

    if result["total"] == 0:
        return f"Application #{application_id} has no conditions."

    lines = [f"Condition Summary -- Application #{application_id} ({result['total']} total):", ""]
    for status, count in result["counts"].items():
        if count > 0:
            lines.append(f"  {format_enum_label(status)}: {count}")

    # Highlight unresolved
    unresolved = (
        result["counts"].get("open", 0)
        + result["counts"].get("responded", 0)
        + result["counts"].get("under_review", 0)
        + result["counts"].get("escalated", 0)
    )
    resolved = result["counts"].get("cleared", 0) + result["counts"].get("waived", 0)
    lines.append("")
    lines.append(f"  Resolved: {resolved} | Unresolved: {unresolved}")

    return "\n".join(lines)
