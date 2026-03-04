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

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from db import CreditReport, PrequalificationDecision
from db.database import SessionLocal
from db.enums import ApplicationStage, DocumentStatus
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from sqlalchemy import delete, select

from ..services.application import (
    InvalidTransitionError,
    get_application,
    get_financials,
    transition_stage,
)
from ..services.audit import write_audit_event
from ..services.completeness import check_completeness, check_underwriting_readiness
from ..services.condition import get_conditions, parse_quality_flags
from ..services.credit_bureau import get_credit_bureau_service
from ..services.document import get_document, list_documents, update_document_status
from ..services.prequalification import evaluate_prequalification
from ..services.products import PRODUCTS
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


_VALID_PRODUCT_IDS = {p.id for p in PRODUCTS}


@tool
async def lo_pull_credit(
    application_id: int,
    pull_type: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Pull credit for the primary borrower on a loan application.

    Performs a simulated soft or hard credit pull and stores the result.
    Soft pulls are used for pre-qualification; hard pulls for underwriting.

    Args:
        application_id: The loan application ID.
        pull_type: "soft" or "hard".
    """
    if pull_type not in ("soft", "hard"):
        return "Invalid pull_type. Must be 'soft' or 'hard'."

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "Application not found or you don't have access to it."

        # Find primary borrower
        primary_ab = next(
            (ab for ab in (app.application_borrowers or []) if ab.is_primary),
            None,
        )
        if primary_ab is None or primary_ab.borrower is None:
            return "No primary borrower found for this application."

        borrower = primary_ab.borrower
        bureau = get_credit_bureau_service()

        if pull_type == "soft":
            result = bureau.soft_pull(borrower.id, borrower.keycloak_user_id)
        else:
            result = bureau.hard_pull(borrower.id, borrower.keycloak_user_id)

        now = datetime.now(UTC)
        expiry_days = 30 if pull_type == "soft" else 120

        # Serialize trade lines for hard pulls
        trade_lines_json = None
        if pull_type == "hard":
            trade_lines_json = [tl.model_dump(mode="json") for tl in result.trade_lines]

        report = CreditReport(
            borrower_id=borrower.id,
            application_id=application_id,
            pull_type=pull_type,
            credit_score=result.credit_score,
            bureau=result.bureau,
            outstanding_accounts=result.outstanding_accounts,
            total_outstanding_debt=result.total_outstanding_debt,
            derogatory_marks=result.derogatory_marks,
            oldest_account_years=result.oldest_account_years,
            trade_lines=trade_lines_json,
            collections_count=getattr(result, "collections_count", None),
            bankruptcy_flag=getattr(result, "bankruptcy_flag", None),
            public_records_count=getattr(result, "public_records_count", None),
            pulled_at=now,
            pulled_by=user.user_id,
            expires_at=now + timedelta(days=expiry_days),
        )
        session.add(report)

        await write_audit_event(
            session,
            event_type="credit_pull",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "pull_type": pull_type,
                "bureau": result.bureau,
                "credit_score": result.credit_score,
                "borrower_id": borrower.id,
            },
        )
        await session.commit()

    lines = [
        f"Credit {pull_type} pull complete for {borrower.first_name} {borrower.last_name}:",
        f"Bureau: {result.bureau}",
        f"Credit score: {result.credit_score}",
        f"Outstanding accounts: {result.outstanding_accounts}",
        f"Total outstanding debt: ${result.total_outstanding_debt:,.2f}",
        f"Derogatory marks: {result.derogatory_marks}",
        f"Oldest account: {result.oldest_account_years} years",
        f"Expires: {report.expires_at.strftime('%Y-%m-%d')}",
    ]

    if pull_type == "hard":
        lines.append(f"Trade lines: {len(result.trade_lines)}")
        lines.append(f"Collections: {result.collections_count}")
        lines.append(f"Bankruptcy flag: {result.bankruptcy_flag}")
        lines.append(f"Public records: {result.public_records_count}")

    return "\n".join(lines)


@tool
async def lo_prequalification_check(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Run a pre-qualification evaluation for a loan application.

    Uses the bureau credit score from the most recent soft pull (not the
    self-reported score). Requires a credit pull to be on file first.

    Args:
        application_id: The loan application ID.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "Application not found or you don't have access to it."

        # Load most recent soft-pull credit report
        stmt = (
            select(CreditReport)
            .where(
                CreditReport.application_id == application_id,
                CreditReport.pull_type == "soft",
            )
            .order_by(CreditReport.pulled_at.desc())
            .limit(1)
        )
        cr = (await session.execute(stmt)).scalar_one_or_none()
        if cr is None:
            return (
                "No soft credit pull on file for this application. "
                "Use lo_pull_credit with pull_type='soft' first."
            )

        # Check expiration
        now = datetime.now(UTC)
        expired_warning = ""
        if cr.expires_at and cr.expires_at < now:
            expired_warning = (
                "WARNING: Credit report expired on "
                f"{cr.expires_at.strftime('%Y-%m-%d')}. Consider pulling fresh credit.\n\n"
            )

        # Load financials
        financials = await get_financials(session, application_id)
        if not financials:
            return "No financial data found for this application. Borrower needs to provide income and debt information."

        fin = financials[0]
        gross_monthly_income = fin.gross_monthly_income or Decimal("0")
        monthly_debts = fin.monthly_debts or Decimal("0")
        loan_amount = app.loan_amount or Decimal("0")
        property_value = app.property_value or Decimal("0")

        if loan_amount <= 0 or property_value <= 0:
            return "Loan amount and property value must be set on the application before running pre-qualification."

        loan_type = app.loan_type.value if app.loan_type else None

        result = evaluate_prequalification(
            credit_score=cr.credit_score,
            gross_monthly_income=gross_monthly_income,
            monthly_debts=monthly_debts,
            loan_amount=loan_amount,
            property_value=property_value,
            loan_type=loan_type,
        )

        await write_audit_event(
            session,
            event_type="prequalification_reviewed",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "credit_score_used": cr.credit_score,
                "dti_ratio": result.dti_ratio,
                "ltv_ratio": result.ltv_ratio,
                "eligible_count": len(result.eligible_products),
                "recommended": result.recommended_product_id,
            },
        )
        await session.commit()

    # Format output
    lines = [expired_warning] if expired_warning else []
    lines.extend(
        [
            f"Pre-qualification evaluation for application #{application_id}:",
            f"Bureau credit score: {cr.credit_score} (pulled {cr.pulled_at.strftime('%Y-%m-%d')})",
            f"Gross monthly income: ${gross_monthly_income:,.2f}",
            f"Monthly debts: ${monthly_debts:,.2f}",
            f"Loan amount: ${loan_amount:,.2f}",
            f"Property value: ${property_value:,.2f}",
            f"DTI: {result.dti_ratio:.1f}%  |  LTV: {result.ltv_ratio:.1f}%  |  Down payment: {result.down_payment_pct:.1f}%",
            "",
        ]
    )

    if result.eligible_products:
        lines.append(f"ELIGIBLE ({len(result.eligible_products)}):")
        for p in result.eligible_products:
            rec = " ** RECOMMENDED" if p.product_id == result.recommended_product_id else ""
            lines.append(
                f"  - {p.product_name}: max ${p.max_loan_amount:,.2f} "
                f"at {p.estimated_rate:.2f}% (${p.estimated_monthly_payment:,.2f}/mo){rec}"
            )
        lines.append("")

    if result.ineligible_products:
        lines.append(f"INELIGIBLE ({len(result.ineligible_products)}):")
        for p in result.ineligible_products:
            reasons = "; ".join(p.ineligibility_reasons)
            lines.append(f"  - {p.product_name}: {reasons}")
        lines.append("")

    lines.append(result.summary)

    return "\n".join(lines)


@tool
async def lo_issue_prequalification(
    application_id: int,
    product_id: str,
    max_amount: float,
    state: Annotated[dict, InjectedState],
    notes: str | None = None,
) -> str:
    """Issue a pre-qualification decision for an application.

    Transitions the application from INQUIRY to PREQUALIFICATION and records
    the decision. The application must be in the INQUIRY stage.

    Args:
        application_id: The loan application ID.
        product_id: The mortgage product ID (e.g., "conventional_30", "fha").
        max_amount: The maximum pre-qualified loan amount.
        notes: Optional notes from the loan officer.
    """
    if product_id not in _VALID_PRODUCT_IDS:
        valid = ", ".join(sorted(_VALID_PRODUCT_IDS))
        return f"Invalid product_id '{product_id}'. Must be one of: {valid}"

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "Application not found or you don't have access to it."

        current_stage = app.stage or ApplicationStage.INQUIRY
        if current_stage != ApplicationStage.INQUIRY:
            return (
                f"Application is in '{current_stage.value}' stage. "
                "Pre-qualification can only be issued from the INQUIRY stage."
            )

        # Load latest soft pull for credit score
        stmt = (
            select(CreditReport)
            .where(
                CreditReport.application_id == application_id,
                CreditReport.pull_type == "soft",
            )
            .order_by(CreditReport.pulled_at.desc())
            .limit(1)
        )
        cr = (await session.execute(stmt)).scalar_one_or_none()
        if cr is None:
            return "No soft credit pull on file. Pull credit before issuing pre-qualification."

        # Compute DTI and LTV for the decision record
        financials = await get_financials(session, application_id)
        fin = financials[0] if financials else None
        gross_monthly_income = float(fin.gross_monthly_income or 0) if fin else 0
        monthly_debts = float(fin.monthly_debts or 0) if fin else 0
        loan_amount = float(app.loan_amount or 0)
        property_value = float(app.property_value or 0)

        dti = (monthly_debts / gross_monthly_income) if gross_monthly_income > 0 else 1.0
        ltv = (loan_amount / property_value) if property_value > 0 else 1.0

        # Find product name for the confirmation message
        product_name = next((p.name for p in PRODUCTS if p.id == product_id), product_id)
        product_rate = next((p.typical_rate for p in PRODUCTS if p.id == product_id), 0.0)

        now = datetime.now(UTC)

        # Upsert: delete existing decision if any, then insert
        await session.execute(
            delete(PrequalificationDecision).where(
                PrequalificationDecision.application_id == application_id
            )
        )

        decision = PrequalificationDecision(
            application_id=application_id,
            product_id=product_id,
            max_loan_amount=Decimal(str(max_amount)),
            estimated_rate=Decimal(str(product_rate)),
            credit_score_at_decision=cr.credit_score,
            dti_at_decision=Decimal(str(round(dti, 4))),
            ltv_at_decision=Decimal(str(round(ltv, 4))),
            issued_by=user.user_id,
            issued_at=now,
            expires_at=now + timedelta(days=90),
            notes=notes,
        )
        session.add(decision)

        # Transition INQUIRY -> PREQUALIFICATION
        try:
            await transition_stage(
                session,
                user,
                application_id,
                ApplicationStage.PREQUALIFICATION,
            )
        except InvalidTransitionError as e:
            return str(e)

        await write_audit_event(
            session,
            event_type="prequalification_issued",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "product_id": product_id,
                "max_loan_amount": max_amount,
                "credit_score": cr.credit_score,
                "dti": round(dti, 4),
                "ltv": round(ltv, 4),
            },
        )
        await session.commit()

    return (
        f"Pre-qualification issued for application #{application_id}:\n"
        f"Product: {product_name}\n"
        f"Max amount: ${max_amount:,.2f}\n"
        f"Rate: {product_rate:.2f}%\n"
        f"Expires: {decision.expires_at.strftime('%Y-%m-%d')}\n"
        f"Stage transitioned to: PREQUALIFICATION"
    )
