# This project was developed with assistance from AI tools.
"""LangGraph tools for the borrower assistant agent.

These wrap the completeness and status services so the agent can
check document requirements, application status, and regulatory
deadlines during a conversation.  DB-backed tools use InjectedState
to receive the caller's identity from the graph state.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  This is intentional: LangGraph
    tool nodes run as independent async tasks and may execute in any order,
    so sharing a session would risk interleaved flushes, stale reads, and
    MissingGreenlet errors.  The per-tool pattern keeps each DB interaction
    self-contained and avoids cross-tool state leakage.
"""

from datetime import date, datetime, timedelta
from typing import Annotated

from db.database import SessionLocal
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..services import application as app_service
from ..services.audit import write_audit_event
from ..services.completeness import DOC_TYPE_LABELS, check_completeness
from ..services.condition import (
    check_condition_documents,
    get_conditions,
    respond_to_condition,
)
from ..services.disclosure import get_disclosure_status
from ..services.document import list_documents
from ..services.intake import (
    get_application_progress,
    update_application_fields,
)
from ..services.intake import (
    start_application as start_application_service,
)
from ..services.rate_lock import get_rate_lock_status
from ..services.status import get_application_status
from .shared import format_enum_label, user_context_from_state

# REQ-CC-17 disclaimer appended to all regulatory deadline responses
_REGULATORY_DISCLAIMER = (
    "\n\n*This content is simulated for demonstration purposes "
    "and does not constitute legal or regulatory advice.*"
)


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="borrower")


@tool
async def list_my_applications(
    state: Annotated[dict, InjectedState],
) -> str:
    """List the borrower's mortgage applications. Use this to discover the borrower's application IDs before calling other tools that require an application_id."""
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        apps, total = await app_service.list_applications(session, user, limit=10)

    if total == 0:
        return "You don't have any mortgage applications yet. Would you like to start one?"

    lines = [f"You have {total} application(s):"]
    for app in apps:
        stage = format_enum_label(app.stage.value)
        loan_amt = f"${app.loan_amount:,.0f}" if app.loan_amount else "not set"
        addr = app.property_address or "no address"
        lines.append(f"  Application #{app.id}: {stage}, loan {loan_amt}, {addr}")

    if total == 1:
        lines.append(f"\nYour active application ID is {apps[0].id}.")

    return "\n".join(lines)


@tool
async def document_completeness(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check which documents have been uploaded and which are still needed for a loan application.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await check_completeness(session, user, application_id)

    if result is None:
        return "Application not found or you don't have access to it."

    lines = [
        f"Document completeness for application {application_id}:",
        f"Status: {'Complete' if result.is_complete else 'Incomplete'} "
        f"({result.provided_count}/{result.required_count} documents provided)",
        "",
    ]
    for req in result.requirements:
        status = "Provided" if req.is_provided else "MISSING"
        line = f"- {req.label}: {status}"
        if req.quality_flags:
            line += f" (issues: {', '.join(req.quality_flags)})"
        lines.append(line)

    missing = [r for r in result.requirements if not r.is_provided]
    if missing:
        lines.append("")
        lines.append("Next step: Upload " + missing[0].label)

    return "\n".join(lines)


_STATUS_LABELS: dict[str, str] = {
    "uploaded": "Uploaded (waiting to process)",
    "processing": "Processing...",
    "processing_complete": "Processed successfully",
    "processing_failed": "Processing failed",
    "pending_review": "Pending review",
    "accepted": "Accepted",
    "flagged_for_resubmission": "Needs resubmission",
    "rejected": "Rejected",
}


@tool
async def document_processing_status(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check the processing status of documents uploaded for a loan application. Shows each document's current status (processing, complete, failed, etc.).

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        documents, total = await list_documents(session, user, application_id, limit=50)

    if total == 0:
        return (
            f"No documents have been uploaded for application {application_id} yet. "
            "Would you like to upload a document?"
        )

    lines = [f"Document status for application {application_id} ({total} document(s)):"]

    processing_count = 0
    failed_count = 0
    complete_count = 0

    for doc in documents:
        status_val = doc.status.value if hasattr(doc.status, "value") else str(doc.status)
        label = DOC_TYPE_LABELS.get(doc.doc_type, str(doc.doc_type))
        status_label = _STATUS_LABELS.get(status_val, status_val)
        lines.append(f"- {label}: {status_label}")

        if status_val == "processing":
            processing_count += 1
        elif status_val == "processing_failed":
            failed_count += 1
        elif status_val == "processing_complete":
            complete_count += 1

    if processing_count > 0:
        lines.append("")
        lines.append(
            f"{processing_count} document(s) still processing. I'll let you know when they're done."
        )
    if failed_count > 0:
        lines.append("")
        lines.append(
            f"{failed_count} document(s) failed processing. "
            "You may need to re-upload a clearer copy."
        )

    return "\n".join(lines)


@tool
async def application_status(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Get the current status summary for a loan application including stage, document progress, and pending actions.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await get_application_status(session, user, application_id)

    if result is None:
        return "Application not found or you don't have access to it."

    lines = [
        f"Application {application_id} Status:",
        f"Stage: {result.stage_info.label}",
        f"  {result.stage_info.description}",
        f"  Next step: {result.stage_info.next_step}",
        f"  Typical timeline: {result.stage_info.typical_timeline}",
        "",
        f"Documents: {result.provided_doc_count}/{result.required_doc_count} "
        f"({'complete' if result.is_document_complete else 'incomplete'})",
    ]

    if result.open_condition_count > 0:
        lines.append(f"Open conditions: {result.open_condition_count}")

    if result.pending_actions:
        lines.append("")
        lines.append("Pending actions:")
        for action in result.pending_actions:
            lines.append(f"- {action.description}")

    return "\n".join(lines)


@tool
def regulatory_deadlines(
    application_date: str,
    current_stage: str,
) -> str:
    """Look up regulatory deadlines that may apply to a loan application.

    Args:
        application_date: The date the application was created (YYYY-MM-DD format).
        current_stage: The current application stage (e.g. 'application', 'processing').
    """
    try:
        app_date = datetime.strptime(application_date, "%Y-%m-%d").date()
    except ValueError:
        return "Invalid date format. Please use YYYY-MM-DD." + _REGULATORY_DISCLAIMER

    today = date.today()
    lines = [f"Regulatory deadlines for application dated {application_date}:"]

    # Pre-application stages don't trigger regulatory clocks
    pre_app_stages = {"inquiry", "prequalification"}
    if current_stage in pre_app_stages:
        lines.append(
            "No regulatory deadlines apply yet. Deadlines begin when "
            "a formal application is submitted."
        )
        return "\n".join(lines) + _REGULATORY_DISCLAIMER

    # Reg B (ECOA): Lender must notify applicant of action taken within
    # 30 calendar days of receiving a completed application.
    reg_b_deadline = app_date + timedelta(days=30)
    reg_b_remaining = (reg_b_deadline - today).days
    if reg_b_remaining > 0:
        lines.append(
            f"- Reg B (ECOA) 30-day notice: Decision or notice of action required by "
            f"{reg_b_deadline.isoformat()} ({reg_b_remaining} days remaining)"
        )
    else:
        lines.append(
            f"- Reg B (ECOA) 30-day notice: Deadline was {reg_b_deadline.isoformat()} "
            f"({abs(reg_b_remaining)} days ago)"
        )

    # TRID: Loan Estimate must be delivered within 3 business days
    # of receiving a completed application.
    trid_deadline = app_date + timedelta(days=3)
    trid_remaining = (trid_deadline - today).days
    if trid_remaining > 0:
        lines.append(
            f"- TRID Loan Estimate: Must be delivered by "
            f"{trid_deadline.isoformat()} ({trid_remaining} days remaining)"
        )
    elif trid_remaining == 0:
        lines.append(f"- TRID Loan Estimate: Due today ({trid_deadline.isoformat()})")
    else:
        lines.append(
            f"- TRID Loan Estimate: Was due by {trid_deadline.isoformat()} "
            f"({abs(trid_remaining)} days ago)"
        )

    return "\n".join(lines) + _REGULATORY_DISCLAIMER


@tool
async def acknowledge_disclosure(
    application_id: int,
    disclosure_id: str,
    borrower_confirmation: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Record a borrower's acknowledgment of a required disclosure in the audit trail.

    Call this when the borrower confirms they have received and reviewed
    a disclosure (e.g., "yes", "I acknowledge", "I agree").

    Args:
        application_id: The loan application ID.
        disclosure_id: Identifier of the disclosure (loan_estimate, privacy_notice, hmda_notice, equal_opportunity_notice).
        borrower_confirmation: The borrower's exact confirmation text.
    """
    from ..services.disclosure import DISCLOSURE_BY_ID

    disclosure = DISCLOSURE_BY_ID.get(disclosure_id)
    if disclosure is None:
        valid = ", ".join(sorted(DISCLOSURE_BY_ID.keys()))
        return f"Unknown disclosure '{disclosure_id}'. Valid IDs: {valid}"

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        await write_audit_event(
            session,
            event_type="disclosure_acknowledged",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "disclosure_id": disclosure_id,
                "disclosure_label": disclosure["label"],
                "borrower_confirmation": borrower_confirmation,
            },
        )
        await session.commit()

    return f"Recorded: {disclosure['label']} acknowledged for application {application_id}."


@tool
async def disclosure_status(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check which required disclosures have been acknowledged and which are still pending for a loan application.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        # Verify user has access to this application
        app = await app_service.get_application(session, user, application_id)
        if app is None:
            return f"Application {application_id} not found or access denied."
        result = await get_disclosure_status(session, application_id)

    lines = [f"Disclosure status for application {application_id}:"]

    if result["all_acknowledged"]:
        lines.append("All required disclosures have been acknowledged.")
    else:
        lines.append(
            f"{len(result['acknowledged'])}/{len(result['acknowledged']) + len(result['pending'])} "
            "disclosures acknowledged."
        )

    if result["acknowledged"]:
        lines.append("")
        lines.append("Acknowledged:")
        for d_id in result["acknowledged"]:
            from ..services.disclosure import DISCLOSURE_BY_ID

            label = DISCLOSURE_BY_ID.get(d_id, {}).get("label", d_id)
            lines.append(f"  - {label}")

    if result["pending"]:
        lines.append("")
        lines.append("Pending:")
        for d_id in result["pending"]:
            from ..services.disclosure import DISCLOSURE_BY_ID

            label = DISCLOSURE_BY_ID.get(d_id, {}).get("label", d_id)
            lines.append(f"  - {label}")

    return "\n".join(lines)


@tool
async def rate_lock_status(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check the current rate lock status for a loan application, including locked rate, expiration date, and days remaining.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await get_rate_lock_status(session, user, application_id)

    if result is None:
        return "Application not found or you don't have access to it."

    if result["status"] == "none":
        return (
            f"Application {application_id} does not have a rate lock yet. "
            "Would you like me to explain how rate locks work?"
        )

    lines = [f"Rate lock status for application {application_id}:"]

    if result["status"] == "active":
        lines.append("Status: Active")
        lines.append(f"Locked rate: {result['locked_rate']}%")
        lines.append(f"Lock date: {result['lock_date']}")
        lines.append(f"Expiration date: {result['expiration_date']}")
        days = result["days_remaining"]
        lines.append(f"Days remaining: {days}")

        if days == 0:
            lines.append("")
            lines.append("Your rate lock expires today! Contact your loan officer immediately.")
        elif days <= 3:
            lines.append("")
            lines.append(
                f"Urgent: Your rate lock expires in {days} days. "
                "You need to close soon, or you may need to re-lock at a different rate."
            )
        elif days <= 7:
            lines.append("")
            lines.append(
                f"Note: Your rate lock expires in {days} days. "
                "Please work with your loan officer to close on time."
            )
    else:
        lines.append("Status: Expired")
        lines.append(f"Locked rate was: {result['locked_rate']}%")
        lines.append(f"Expired on: {result['expiration_date']}")
        lines.append("")
        lines.append(
            "Your rate lock has expired. You'll need to request a new rate lock. "
            "Contact your loan officer to discuss current rates."
        )

    return "\n".join(lines)


@tool
async def list_conditions(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """List underwriting conditions for a loan application. Shows open and responded conditions that the borrower needs to address.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await get_conditions(session, user, application_id, open_only=True)

    if result is None:
        return "Application not found or you don't have access to it."

    if not result:
        return f"Application {application_id} has no pending conditions. You're all set!"

    lines = [f"Open conditions for application {application_id}:"]
    for i, cond in enumerate(result, 1):
        status_label = cond["status"].replace("_", " ").title()
        line = f"{i}. [{status_label}] {cond['description']} (condition #{cond['id']})"
        if cond.get("response_text"):
            line += f"\n   Your response: {cond['response_text']}"
        lines.append(line)

    open_count = sum(1 for c in result if c["status"] == "open")
    if open_count > 0:
        lines.append("")
        lines.append(
            f"You have {open_count} condition(s) that still need a response. "
            "Would you like to address them now?"
        )

    return "\n".join(lines)


@tool
async def respond_to_condition_tool(
    application_id: int,
    condition_id: int,
    response_text: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Record the borrower's text response to an underwriting condition. Use this when the borrower provides an explanation or answer for a condition.

    Args:
        application_id: The loan application ID.
        condition_id: The condition ID to respond to (from list_conditions output).
        response_text: The borrower's response text.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await respond_to_condition(
            session,
            user,
            application_id,
            condition_id,
            response_text,
        )

    if result is None:
        return "Application or condition not found, or you don't have access."

    return (
        f"Recorded your response for condition #{result['id']}: "
        f'"{result["description"]}". '
        "The underwriter will review your response."
    )


@tool
async def check_condition_satisfaction(
    application_id: int,
    condition_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check whether a condition has been satisfied by reviewing linked documents and their extraction results. Use this after a borrower uploads a document for a condition.

    Args:
        application_id: The loan application ID.
        condition_id: The condition ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await check_condition_documents(
            session,
            user,
            application_id,
            condition_id,
        )

    if result is None:
        return "Application or condition not found, or you don't have access."

    lines = [f"Condition #{result['condition_id']}: {result['description']}"]
    lines.append(f"Status: {result['status']}")

    if result["response_text"]:
        lines.append(f"Borrower response: {result['response_text']}")

    if not result["has_documents"]:
        lines.append("")
        lines.append("No documents have been linked to this condition yet.")
        if result["response_text"]:
            lines.append(
                "The borrower provided a text response. Review it to determine "
                "if the explanation is sufficient or if a document is still needed."
            )
        return "\n".join(lines)

    lines.append("")
    lines.append(f"Linked documents ({len(result['documents'])}):")
    for doc in result["documents"]:
        label = doc["file_path"].rsplit("/", 1)[-1] if doc.get("file_path") else f"doc-{doc['id']}"
        doc_line = f"  - {label} (type: {doc['doc_type']}, status: {doc['status']})"
        lines.append(doc_line)

        if doc["quality_flags"]:
            lines.append(f"    Quality issues: {', '.join(doc['quality_flags'])}")

        if doc["extractions"]:
            lines.append("    Extracted fields:")
            for ext in doc["extractions"]:
                conf = f" (confidence: {ext['confidence']:.0%})" if ext["confidence"] else ""
                lines.append(f"      {ext['field']}: {ext['value']}{conf}")

    if result["has_quality_issues"]:
        lines.append("")
        lines.append(
            "There are quality issues with the uploaded document(s). "
            "Consider asking the borrower to upload a corrected version."
        )
    else:
        lines.append("")
        lines.append(
            "The document(s) look good. Confirm to the borrower that their "
            "submission is complete and the underwriter will review it."
        )

    return "\n".join(lines)


@tool
async def start_application(
    state: Annotated[dict, InjectedState],
) -> str:
    """Start a new mortgage application or continue an existing one.

    Call this when the borrower expresses intent to apply for a mortgage.
    If they already have an active application, it returns that instead
    of creating a duplicate.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await start_application_service(session, user)

        if result["is_new"]:
            await write_audit_event(
                session,
                event_type="application_started",
                user_id=user.user_id,
                user_role=user.role.value,
                application_id=result["application_id"],
                event_data={"source": "conversational_intake"},
            )
            await session.commit()
            return (
                f"Created new application #{result['application_id']}. "
                "Let's collect your information. I'll ask about your personal "
                "details, property information, and financial situation."
            )

        stage = format_enum_label(result["stage"])
        return (
            f"You already have an active application #{result['application_id']} "
            f"(stage: {stage}). Would you like to continue with this application?"
        )


@tool
async def update_application_data(
    application_id: int,
    fields: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Update one or more fields on a mortgage application.

    Args:
        application_id: The application ID to update.
        fields: JSON string of field_name:value pairs, e.g.
            '{"gross_monthly_income": "6250", "employment_status": "w2"}'

    Valid field names: first_name, last_name, email, ssn, date_of_birth,
        employment_status, loan_type, property_address, loan_amount,
        property_value, gross_monthly_income, monthly_debts, total_assets,
        credit_score
    """
    import json as _json

    user = _user_context_from_state(state)

    try:
        parsed = _json.loads(fields)
    except _json.JSONDecodeError:
        return "Could not parse fields -- please provide a valid JSON object."

    if not isinstance(parsed, dict) or not parsed:
        return "Fields must be a non-empty JSON object of {field_name: value} pairs."

    async with SessionLocal() as session:
        result = await update_application_fields(session, user, application_id, parsed)

        # Write audit event (field names only, not PII values)
        audit_data = {
            "fields_updated": result["updated"],
            "fields_failed": list(result["errors"].keys()),
        }
        if result.get("corrections"):
            audit_data["corrections"] = list(result["corrections"].keys())

        await write_audit_event(
            session,
            event_type="data_collection",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data=audit_data,
        )
        await session.commit()

    # Format response
    parts = []
    if result["updated"]:
        parts.append(f"Updated: {', '.join(result['updated'])}.")
    if result["errors"]:
        for fname, msg in result["errors"].items():
            if fname == "_":
                parts.append(msg)
            else:
                parts.append(f"Could not save {fname}: {msg}.")
    if result["remaining"]:
        parts.append(f"Still needed: {', '.join(result['remaining'])}.")
    else:
        parts.append("All required fields are complete!")

    return " ".join(parts)


@tool
async def get_application_summary(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Show collected application data and remaining fields. Use when the borrower asks to review their application, see what's been collected, or check progress.

    Args:
        application_id: The application ID to summarize.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        progress = await get_application_progress(session, user, application_id)

        if progress is None:
            return "Application not found or you don't have access to it."

        await write_audit_event(
            session,
            event_type="data_access",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={"action": "review", "tool": "get_application_summary"},
        )
        await session.commit()

    pct = round(progress["completed"] / progress["total"] * 100) if progress["total"] else 0
    stage = format_enum_label(progress["stage"])

    lines = [
        f"Application #{progress['application_id']} (Stage: {stage})",
        f"Progress: {progress['completed']}/{progress['total']} fields ({pct}%)",
        "",
    ]

    for section_name, fields in progress["sections"].items():
        lines.append(f"{section_name}:")
        for label, value in fields.items():
            display = value if value is not None else "(not provided)"
            lines.append(f"  {label}: {display}")
        lines.append("")

    if progress["remaining"]:
        lines.append(f"Still needed: {', '.join(progress['remaining'])}")
    else:
        lines.append("All required fields are complete!")

    return "\n".join(lines)
