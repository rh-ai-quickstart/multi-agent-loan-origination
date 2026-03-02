# This project was developed with assistance from AI tools.
"""LangGraph tools for the loan officer assistant agent.

These wrap existing services so the LO agent can review applications,
inspect documents, flag documents for resubmission, check underwriting
readiness, and submit applications to underwriting.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  This is intentional: LangGraph
    tool nodes run as independent async tasks and may execute in any order,
    so sharing a session would risk interleaved flushes, stale reads, and
    MissingGreenlet errors.  The per-tool pattern keeps each DB interaction
    self-contained and avoids cross-tool state leakage.
"""

from typing import Annotated

from db.database import SessionLocal
from db.enums import ApplicationStage, DocumentStatus
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..services.application import get_application, transition_stage
from ..services.audit import write_audit_event
from ..services.completeness import check_completeness, check_underwriting_readiness
from ..services.condition import get_conditions, parse_quality_flags
from ..services.document import get_document, list_documents, update_document_status
from ..services.rate_lock import get_rate_lock_status
from ..services.status import get_application_status
from .shared import format_enum_label, user_context_from_state

_COMMUNICATION_TYPES = {
    "document_request",
    "condition_explanation",
    "status_update",
    "resubmission_notice",
}

_LOAN_TYPE_LABELS: dict[str, str] = {
    "conventional_30": "Conventional 30-Year Fixed",
    "conventional_15": "Conventional 15-Year Fixed",
    "fha": "FHA Loan",
    "va": "VA Loan",
    "jumbo": "Jumbo Loan",
    "usda": "USDA Loan",
    "arm": "5/1 Adjustable Rate Mortgage",
}

_SEVERITY_LABELS: dict[str, str] = {
    "prior_to_approval": "Prior to Approval",
    "prior_to_docs": "Prior to Docs",
    "prior_to_closing": "Prior to Closing",
    "prior_to_funding": "Prior to Funding",
}

_COMM_TYPE_LABELS: dict[str, str] = {
    "document_request": "Document Request",
    "condition_explanation": "Condition Explanation",
    "status_update": "Status Update",
    "resubmission_notice": "Resubmission Notice",
}


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="loan_officer")


@tool
async def lo_application_detail(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Get a detailed summary of a loan application including borrower info, financials, stage, documents, and conditions.

    Args:
        application_id: The loan application ID to review.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "Application not found or you don't have access to it."

        status = await get_application_status(session, user, application_id)

    stage = app.stage.value if app.stage else "inquiry"
    lines = [
        f"Application #{application_id} Summary:",
        f"Stage: {format_enum_label(stage)}",
    ]

    if app.loan_type:
        lines.append(f"Loan type: {app.loan_type.value}")
    if app.property_address:
        lines.append(f"Property: {app.property_address}")
    if app.loan_amount:
        lines.append(f"Loan amount: ${app.loan_amount:,.2f}")
    if app.property_value:
        lines.append(f"Property value: ${app.property_value:,.2f}")

    # Borrower info
    for ab in app.application_borrowers or []:
        if ab.borrower:
            b = ab.borrower
            role_label = "Primary borrower" if ab.is_primary else "Co-borrower"
            lines.append(f"{role_label}: {b.first_name} {b.last_name} ({b.email})")

    # Status summary
    if status:
        lines.append("")
        lines.append(
            f"Documents: {status.provided_doc_count}/{status.required_doc_count} "
            f"({'complete' if status.is_document_complete else 'incomplete'})"
        )
        if status.open_condition_count > 0:
            lines.append(f"Open conditions: {status.open_condition_count}")
        if status.pending_actions:
            lines.append("Pending actions:")
            for action in status.pending_actions:
                lines.append(f"  - {action.description}")

    return "\n".join(lines)


@tool
async def lo_document_review(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """List all documents for an application with their status, quality flags, and upload date.

    Args:
        application_id: The loan application ID.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        documents, total = await list_documents(session, user, application_id, limit=50)

    if total == 0:
        return f"No documents found for application {application_id}."

    lines = [f"Documents for application {application_id} ({total} total):"]
    for doc in documents:
        doc_type = doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type)
        status_val = doc.status.value if hasattr(doc.status, "value") else str(doc.status)
        line = f"- [{doc.id}] {doc_type}: {status_val}"

        if doc.quality_flags:
            flags = parse_quality_flags(doc.quality_flags)
            if flags:
                line += f" (issues: {', '.join(flags)})"

        if doc.created_at:
            line += f" (uploaded: {doc.created_at.strftime('%Y-%m-%d')})"
        lines.append(line)

    return "\n".join(lines)


@tool
async def lo_document_quality(
    application_id: int,
    document_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Get detailed quality information for a specific document.

    Args:
        application_id: The loan application ID.
        document_id: The document ID to inspect.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        doc = await get_document(session, user, document_id)

    if doc is None:
        return "Document not found or you don't have access to it."

    if doc.application_id != application_id:
        return "Document does not belong to this application."

    doc_type = doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type)
    status_val = doc.status.value if hasattr(doc.status, "value") else str(doc.status)

    lines = [
        f"Document #{document_id} Detail:",
        f"Type: {doc_type}",
        f"Status: {status_val}",
    ]

    if doc.quality_flags:
        flags = parse_quality_flags(doc.quality_flags)
        if flags:
            lines.append("Quality issues:")
            for flag in flags:
                lines.append(f"  - {flag}")
        else:
            lines.append("Quality: No issues detected")
    else:
        lines.append("Quality: No issues detected")

    if doc.created_at:
        lines.append(f"Uploaded: {doc.created_at.strftime('%Y-%m-%d %H:%M')}")

    return "\n".join(lines)


@tool
async def lo_completeness_check(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check document completeness for an application from the loan officer's perspective.

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
        if req.status:
            line += f" ({req.status.value})"
        if req.quality_flags:
            line += f" [issues: {', '.join(req.quality_flags)}]"
        lines.append(line)

    return "\n".join(lines)


@tool
async def lo_mark_resubmission(
    application_id: int,
    document_id: int,
    reason: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Flag a document for resubmission by the borrower, with a reason.

    Only documents that have been processed (PROCESSING_COMPLETE, PENDING_REVIEW,
    or ACCEPTED) can be flagged. The borrower will be notified to upload a
    replacement.

    Args:
        application_id: The loan application ID.
        document_id: The document ID to flag.
        reason: Explanation of why the document needs resubmission.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        try:
            doc = await update_document_status(
                session,
                user,
                application_id,
                document_id,
                DocumentStatus.FLAGGED_FOR_RESUBMISSION,
                reason=reason,
            )
        except ValueError as e:
            return str(e)

        if doc is None:
            return "Document not found, not in this application, or you don't have access."

        await write_audit_event(
            session,
            event_type="document_flagged_for_resubmission",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "document_id": document_id,
                "reason": reason,
            },
        )
        await session.commit()

    return (
        f"Document #{document_id} has been flagged for resubmission. "
        f"Reason: {reason}. The borrower will be notified."
    )


@tool
async def lo_underwriting_readiness(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check whether an application is ready to be submitted to underwriting.

    Reviews stage, document completeness, processing status, and quality
    flags. Returns a clear verdict with any blockers that must be resolved.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await check_underwriting_readiness(session, user, application_id)

    if result is None:
        return "Application not found or you don't have access to it."

    if result["is_ready"]:
        return (
            f"Application {application_id} is READY for underwriting submission. "
            "All documents are complete, processed, and have no quality issues. "
            "Would you like to submit it?"
        )

    lines = [
        f"Application {application_id} is NOT ready for underwriting. Blockers:",
    ]
    for blocker in result["blockers"]:
        lines.append(f"  - {blocker}")
    lines.append("")
    lines.append("Resolve these issues before submitting to underwriting.")

    return "\n".join(lines)


@tool
async def lo_submit_to_underwriting(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Submit an application to underwriting.

    This performs a two-step stage transition: APPLICATION -> PROCESSING ->
    UNDERWRITING. The state machine requires PROCESSING as an intermediate
    stage. Both transitions are audited.

    Note: When the Processor persona is added in a future phase, this tool
    would only transition to PROCESSING; the Processor would then prep the
    loan file and submit to UNDERWRITING.

    Readiness is checked first -- if blockers exist, the submission is
    refused with details.

    Args:
        application_id: The loan application ID to submit.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        # Gate: check readiness
        readiness = await check_underwriting_readiness(session, user, application_id)
        if readiness is None:
            return "Application not found or you don't have access to it."

        if not readiness["is_ready"]:
            lines = ["Cannot submit -- application is not ready:"]
            for b in readiness["blockers"]:
                lines.append(f"  - {b}")
            return "\n".join(lines)

        # Step 1: APPLICATION -> PROCESSING
        app = await transition_stage(session, user, application_id, ApplicationStage.PROCESSING)
        if app is None:
            return "Failed to transition to processing stage."

        await write_audit_event(
            session,
            event_type="stage_transition",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "from_stage": "application",
                "to_stage": "processing",
                "action": "lo_submit_to_underwriting",
            },
        )

        # Step 2: PROCESSING -> UNDERWRITING
        app = await transition_stage(session, user, application_id, ApplicationStage.UNDERWRITING)
        if app is None:
            return "Failed to transition to underwriting stage."

        await write_audit_event(
            session,
            event_type="stage_transition",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "from_stage": "processing",
                "to_stage": "underwriting",
                "action": "lo_submit_to_underwriting",
            },
        )
        await session.commit()

    return (
        f"Application {application_id} has been submitted to underwriting. "
        "Stage: UNDERWRITING. The underwriting team will review and may "
        "issue conditions."
    )


@tool
async def lo_draft_communication(
    application_id: int,
    communication_type: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Gather comprehensive application context for drafting a borrower communication.

    Collects borrower info, loan details, document completeness, open conditions,
    and rate lock status in a single call. The LLM uses this context to compose
    the actual communication draft.

    Args:
        application_id: The loan application ID.
        communication_type: One of: document_request, condition_explanation,
            status_update, resubmission_notice.
    """
    if communication_type not in _COMMUNICATION_TYPES:
        valid = ", ".join(sorted(_COMMUNICATION_TYPES))
        return f"Invalid communication type '{communication_type}'. Must be one of: {valid}"

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "Application not found or you don't have access to it."

        completeness = await check_completeness(session, user, application_id)
        conditions = await get_conditions(session, user, application_id, open_only=True)
        rate_lock = await get_rate_lock_status(session, user, application_id)

    # --- Header ---
    type_label = _COMM_TYPE_LABELS.get(communication_type, communication_type)
    lines = [
        f"Communication context for application #{application_id}",
        f"Type: {type_label}",
        "",
    ]

    # --- Borrower ---
    lines.append("BORROWER:")
    for ab in app.application_borrowers or []:
        if ab.borrower:
            b = ab.borrower
            role_label = "Primary" if ab.is_primary else "Co-borrower"
            lines.append(f"  {role_label}: {b.first_name} {b.last_name} ({b.email})")

    # --- Loan details ---
    lines.append("")
    lines.append("LOAN DETAILS:")
    if app.property_address:
        lines.append(f"  Property: {app.property_address}")
    if app.loan_type:
        lt_val = app.loan_type.value if hasattr(app.loan_type, "value") else str(app.loan_type)
        lt_label = _LOAN_TYPE_LABELS.get(lt_val, lt_val)
        lines.append(f"  Loan type: {lt_label}")
    if app.loan_amount:
        lines.append(f"  Loan amount: ${app.loan_amount:,.2f}")
    stage = app.stage.value if app.stage else "inquiry"
    lines.append(f"  Stage: {format_enum_label(stage)}")

    # --- Documents ---
    if completeness:
        provided = completeness.provided_count
        required = completeness.required_count
        lines.append("")
        lines.append(f"DOCUMENTS ({provided}/{required} provided):")
        for req in completeness.requirements:
            if req.is_provided:
                status_val = req.status.value if req.status else "provided"
                line = f"  - {req.label}: Provided ({status_val})"
                if req.quality_flags:
                    line += f" (quality issues: {', '.join(req.quality_flags)})"
            else:
                line = f"  - {req.label}: MISSING"
            lines.append(line)

    # --- Conditions ---
    if conditions:
        lines.append("")
        lines.append(f"OPEN CONDITIONS ({len(conditions)}):")
        for c in conditions:
            sev = c.get("severity", "")
            sev_label = _SEVERITY_LABELS.get(sev, sev) if sev else ""
            desc = c.get("description", "")
            if sev_label:
                lines.append(f"  - [{sev_label}] {desc}")
            else:
                lines.append(f"  - {desc}")
    elif conditions is not None:
        lines.append("")
        lines.append("OPEN CONDITIONS (0):")
        lines.append("  None")

    # --- Rate lock ---
    if rate_lock:
        lines.append("")
        lines.append("RATE LOCK:")
        rl_status = rate_lock.get("status", "none")
        if rl_status == "none":
            lines.append("  No rate lock on file")
        else:
            lines.append(f"  Status: {rl_status.title()}")
            if rate_lock.get("locked_rate") is not None:
                lines.append(f"  Rate: {rate_lock['locked_rate']:.3f}%")
            if rate_lock.get("expiration_date"):
                days = rate_lock.get("days_remaining", 0)
                lines.append(
                    f"  Expires: {rate_lock['expiration_date'][:10]} ({days} days remaining)"
                )
            if rate_lock.get("is_urgent"):
                lines.append("  *** URGENT: Rate lock expiring within 7 days ***")

    # HMDA exclusion reminder
    lines.append("")
    lines.append(
        "NOTE: Do not include any demographic information "
        "(race, ethnicity, sex) in the communication."
    )

    return "\n".join(lines)


@tool
async def lo_send_communication(
    application_id: int,
    communication_type: str,
    subject: str,
    recipient_name: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Record that a borrower communication was sent (audit only -- no actual email delivery at MVP).

    Call this only after the loan officer has reviewed and approved the draft.

    Args:
        application_id: The loan application ID.
        communication_type: One of: document_request, condition_explanation,
            status_update, resubmission_notice.
        subject: The subject line of the communication.
        recipient_name: The borrower's name.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "Application not found or you don't have access to it."

        await write_audit_event(
            session,
            event_type="communication_sent",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "communication_type": communication_type,
                "subject": subject,
                "recipient_name": recipient_name,
                "delivery_method": "audit_only",
            },
        )
        await session.commit()

    return (
        f"Communication recorded: '{subject}' to {recipient_name} "
        f"for application #{application_id}. "
        "(MVP: audit log only -- no email delivery.)"
    )
