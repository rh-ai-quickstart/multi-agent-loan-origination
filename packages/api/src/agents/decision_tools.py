# This project was developed with assistance from AI tools.
"""LangGraph tools for underwriting decision management.

Wraps decision service functions so the underwriter agent can render
decisions, draft adverse action notices, and generate LE/CD documents.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  See underwriter_tools.py
    for rationale.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Annotated

from db import Decision
from db.database import SessionLocal
from db.enums import DecisionType
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from sqlalchemy import select

from ..core.config import settings
from ..services.application import get_application
from ..services.audit import write_audit_event
from ..services.condition import get_outstanding_count
from ..services.decision import check_compliance_gate, propose_decision, render_decision
from ..services.rate_lock import get_rate_lock_status
from .disclosure_tools import generate_cd_text, generate_le_text, get_primary_borrower_name
from .shared import format_enum_label, resolve_app_id, user_context_from_state

logger = logging.getLogger(__name__)


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="underwriter")


def _format_proposal(result: dict) -> str:
    """Format a proposal dict into a human-readable preview for the underwriter."""
    dt = format_enum_label(result["decision_type"])
    lines = [
        "PROPOSED DECISION -- awaiting underwriter confirmation",
        "=====================================================",
        f"  Application: #{result['application_id']}",
        f"  Decision: {dt}",
        f"  Rationale: {result['rationale']}",
    ]

    if result.get("new_stage"):
        stage_label = format_enum_label(result["new_stage"])
        lines.append(
            f"  Stage transition: {format_enum_label(result['current_stage'])} -> {stage_label}"
        )

    if result.get("outstanding_conditions", 0) > 0:
        lines.append(f"  Outstanding conditions: {result['outstanding_conditions']}")

    if result.get("ai_recommendation"):
        lines.append(f"  AI recommendation: {result['ai_recommendation']}")
        if result.get("ai_agreement") is True:
            lines.append("  AI agreement: Yes (concurrence)")
        elif result.get("ai_agreement") is False:
            lines.append("  AI agreement: No (OVERRIDE -- provide override_rationale)")
            if result.get("override_rationale"):
                lines.append(f"  Override rationale: {result['override_rationale']}")

    if result.get("denial_reasons"):
        lines.append("  Denial reasons:")
        for i, reason in enumerate(result["denial_reasons"], 1):
            lines.append(f"    {i}. {reason}")

    # Add proposal_id if present
    if result.get("proposal_id"):
        lines.extend(
            [
                "",
                f"PROPOSAL ID: {result['proposal_id']}",
                "",
                "This decision has NOT been recorded yet.",
                "Present this proposal to the underwriter and ask them to confirm.",
                f"To confirm, call this tool again with confirmed=true and proposal_id='{result['proposal_id']}'",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "This decision has NOT been recorded yet.",
                "Present this proposal to the underwriter and ask them to confirm",
                "before calling this tool again with confirmed=true.",
            ]
        )

    return "\n".join(lines)


def _format_confirmed(result: dict, rationale: str) -> str:
    """Format a confirmed decision dict into output text."""
    dt = format_enum_label(result["decision_type"])
    lines = [
        f"Decision rendered for application #{result['application_id']}:",
        f"  Decision ID: {result.get('id', 'N/A')}",
        f"  Type: {dt}",
        f"  Rationale: {rationale}",
    ]

    if result.get("new_stage"):
        stage_label = format_enum_label(result["new_stage"])
        lines.append(f"  New stage: {stage_label}")

    if result.get("ai_recommendation"):
        lines.append(f"  AI recommendation: {result['ai_recommendation']}")
        if result.get("ai_agreement") is True:
            lines.append("  AI agreement: Yes (concurrence)")
        elif result.get("ai_agreement") is False:
            lines.append("  AI agreement: No (override)")
            if result.get("override_rationale"):
                lines.append(f"  Override rationale: {result['override_rationale']}")

    if result.get("denial_reasons"):
        lines.append("  Denial reasons:")
        for i, reason in enumerate(result["denial_reasons"], 1):
            lines.append(f"    {i}. {reason}")

    return "\n".join(lines)


@tool
async def uw_render_decision(
    application_id: int,
    decision: str,
    rationale: str,
    confirmed: bool = False,
    proposal_id: str | None = None,
    denial_reasons: list[str] | None = None,
    credit_score_used: int | None = None,
    credit_score_source: str | None = None,
    contributing_factors: str | None = None,
    override_rationale: str | None = None,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Render an underwriting decision on a loan application.

    This tool uses a two-phase flow to ensure human confirmation:

    Phase 1 (confirmed=false, the default): Returns a PROPOSAL showing
    what the decision would do (decision type, stage transition, AI
    agreement). The proposal is stored in agent state with a unique
    proposal_id. No database records are created. You MUST present
    this proposal to the underwriter and wait for their explicit
    confirmation.

    Phase 2 (confirmed=true): After the underwriter confirms, call
    again with confirmed=true and the proposal_id from Phase 1 to
    execute the decision. This validates the proposal_id, creates
    the decision record, transitions the application stage, and
    writes audit events.

    IMPORTANT: Never set confirmed=true without first showing the
    proposal to the underwriter and receiving their explicit approval.
    The proposal_id parameter is required when confirmed=true.

    Args:
        application_id: The loan application ID.
        decision: One of "approve", "deny", or "suspend".
        rationale: Explanation for the decision.
        confirmed: Set to true only after the underwriter confirms the proposal.
        proposal_id: Required when confirmed=true. The ID from Phase 1 proposal.
        denial_reasons: Required for denials. List of specific reasons.
        credit_score_used: Credit score at time of decision (for denials).
        credit_score_source: Credit bureau source (for denials).
        contributing_factors: Factors that contributed to the decision.
        override_rationale: Explanation when overriding AI recommendation.
    """
    import uuid

    application_id = resolve_app_id(application_id, state)
    user = _user_context_from_state(state)
    decision_lower = decision.strip().lower()

    async with SessionLocal() as session:
        # Compliance gate for approvals (both phases)
        if decision_lower == "approve":
            gate_error = await check_compliance_gate(session, application_id)
            if gate_error:
                return gate_error

        if not confirmed:
            # Phase 1: propose only
            result = await propose_decision(
                session,
                user,
                application_id,
                decision_lower,
                rationale,
                denial_reasons=denial_reasons,
                override_rationale=override_rationale,
            )

            if result is None:
                return f"Application #{application_id} not found or you don't have access to it."
            if "error" in result:
                return result["error"]

            # Generate proposal_id and store in state
            proposal_id_generated = str(uuid.uuid4())

            # Store proposal in state
            if state is not None:
                if "decision_proposals" not in state:
                    state["decision_proposals"] = {}
                state["decision_proposals"][proposal_id_generated] = {
                    "application_id": application_id,
                    "decision": decision_lower,
                    "rationale": rationale,
                    "denial_reasons": denial_reasons,
                    "override_rationale": override_rationale,
                }

            # Add proposal_id to result for output
            result["proposal_id"] = proposal_id_generated

            return _format_proposal(result)

        # Phase 2: confirmed -- validate proposal_id and persist
        if proposal_id is None:
            return (
                "ERROR: proposal_id is required when confirmed=true. "
                "You must first call this tool with confirmed=false to generate "
                "a proposal, then call again with confirmed=true and the proposal_id."
            )

        # Validate proposal_id exists in state
        if state is None or "decision_proposals" not in state:
            return (
                f"ERROR: No proposals found in agent state. The proposal_id '{proposal_id}' "
                "is invalid or has expired. Please start over with confirmed=false."
            )

        proposal = state["decision_proposals"].get(proposal_id)
        if proposal is None:
            return (
                f"ERROR: proposal_id '{proposal_id}' not found in agent state. "
                "Please verify the proposal_id or start over with confirmed=false."
            )

        # Validate proposal matches current parameters
        if proposal["application_id"] != application_id:
            return (
                f"ERROR: proposal_id '{proposal_id}' is for application "
                f"#{proposal['application_id']}, but you are trying to confirm "
                f"for application #{application_id}. These must match."
            )

        if proposal["decision"] != decision_lower:
            return (
                f"ERROR: proposal_id '{proposal_id}' is for decision "
                f"'{proposal['decision']}', but you are trying to confirm "
                f"'{decision_lower}'. These must match."
            )

        # Proceed with rendering the decision
        result = await render_decision(
            session,
            user,
            application_id,
            decision_lower,
            rationale,
            denial_reasons=denial_reasons,
            credit_score_used=credit_score_used,
            credit_score_source=credit_score_source,
            contributing_factors=contributing_factors,
            override_rationale=override_rationale,
        )

        # Clear the proposal from state after successful confirmation
        if state is not None and "decision_proposals" in state:
            state["decision_proposals"].pop(proposal_id, None)

    if result is None:
        return f"Application #{application_id} not found or you don't have access to it."
    if "error" in result:
        return result["error"]

    return _format_confirmed(result, rationale)


@tool
async def uw_draft_adverse_action(
    application_id: int,
    decision_id: int | None = None,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Draft an adverse action notice for a denied application.

    Generates an ECOA/FCRA-compliant adverse action notice based on the
    denial decision. Includes credit score disclosure if applicable.
    The notice is stored as an audit event for compliance tracking.

    Args:
        application_id: The loan application ID.
        decision_id: Optional decision ID. If omitted, uses the most recent
            DENIED decision for the application.
    """
    application_id = resolve_app_id(application_id, state)
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return f"Application #{application_id} not found or you don't have access to it."

        if decision_id is not None:
            # Fetch specific decision
            dec_stmt = select(Decision).where(
                Decision.id == decision_id,
                Decision.application_id == application_id,
            )
        else:
            # Auto-find latest DENIED decision
            dec_stmt = (
                select(Decision)
                .where(
                    Decision.application_id == application_id,
                    Decision.decision_type == DecisionType.DENIED,
                )
                .order_by(Decision.created_at.desc())
                .limit(1)
            )

        dec_result = await session.execute(dec_stmt)
        dec = dec_result.scalar_one_or_none()

        if dec is None:
            if decision_id is not None:
                return f"Decision #{decision_id} not found on application #{application_id}."
            return f"No DENIED decision found on application #{application_id}."

        if dec.decision_type != DecisionType.DENIED:
            return (
                f"Decision #{dec.id} is '{dec.decision_type.value}' -- "
                f"adverse action notices are only for DENIED decisions."
            )

        # Get borrower info
        borrower_name = await get_primary_borrower_name(session, application_id)

        # Parse denial reasons
        denial_reasons = []
        if dec.denial_reasons:
            try:
                denial_reasons = json.loads(dec.denial_reasons)
            except (json.JSONDecodeError, TypeError):
                denial_reasons = [dec.denial_reasons]

        # Build notice
        today = datetime.now(UTC).strftime("%B %d, %Y")
        lines = [
            "ADVERSE ACTION NOTICE (SIMULATED)",
            "==================================",
            f"Date: {today}",
            f"Borrower: {borrower_name}",
            f"Application: #{application_id}",
            "",
            "We regret to inform you that your application for a mortgage loan",
            "has been denied for the following reason(s):",
        ]

        if denial_reasons:
            for i, reason in enumerate(denial_reasons, 1):
                lines.append(f"  {i}. {reason}")
        else:
            lines.append("  (No specific reasons recorded)")

        # Credit score disclosure
        if dec.credit_score_used is not None:
            lines.extend(
                [
                    "",
                    "CREDIT SCORE DISCLOSURE:",
                    f"  Your credit score: {dec.credit_score_used}",
                    "  Scores range from 300 to 850.",
                    f"  Source: {dec.credit_score_source or 'Not specified'}",
                ]
            )

        if dec.contributing_factors:
            lines.extend(
                [
                    "",
                    "CONTRIBUTING FACTORS:",
                    f"  {dec.contributing_factors}",
                ]
            )

        lines.extend(
            [
                "",
                "You have the right to:",
                "- Request a copy of the appraisal used in the decision",
                "- Dispute information on your credit report with the credit bureau",
                "- Request the specific reasons for denial within 60 days",
                "- Obtain a free copy of your credit report within 60 days",
                "",
                settings.COMPANY_NAME,
                "",
                "DISCLAIMER: This content is simulated for demonstration purposes",
                "and does not constitute an actual adverse action notice.",
            ]
        )

        notice_text = "\n".join(lines)

        # Store as audit event
        await write_audit_event(
            session,
            event_type="adverse_action_notice",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "decision_id": dec.id,
                "borrower_name": borrower_name,
                "denial_reasons": denial_reasons,
                "credit_score_used": dec.credit_score_used,
            },
        )
        await session.commit()

    return notice_text


@tool
async def uw_generate_le(
    application_id: int,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Generate a simulated Loan Estimate (LE) for an application.

    Creates a simplified Loan Estimate document with key loan terms,
    projected payments, and estimated closing costs. The LE is stored
    as an audit event for compliance tracking.

    Args:
        application_id: The loan application ID.
    """
    application_id = resolve_app_id(application_id, state)
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return f"Application #{application_id} not found or you don't have access to it."

        le_text = await generate_le_text(session, user, app, application_id)

        # Update LE delivery date
        app.le_delivery_date = datetime.now(UTC)

        # Extract values for audit (redundant calc but simpler than returning from helper)
        loan_amount = float(app.loan_amount) if app.loan_amount else 0
        rate_lock = await get_rate_lock_status(session, user, application_id)
        rate = 6.875
        if rate_lock and rate_lock.get("locked_rate"):
            rate = float(rate_lock["locked_rate"])
        loan_type = app.loan_type.value if app.loan_type else "conventional_30"
        term_years = 15 if loan_type == "conventional_15" else 30

        await write_audit_event(
            session,
            event_type="le_generated",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "loan_amount": loan_amount,
                "rate": rate,
                "term_years": term_years,
            },
        )
        await session.commit()

    return le_text


@tool
async def uw_generate_cd(
    application_id: int,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Generate a simulated Closing Disclosure (CD) for an application.

    Creates a simplified Closing Disclosure with final loan terms,
    actual closing costs, and cash to close. All conditions must be
    cleared or waived before a CD can be generated.

    Args:
        application_id: The loan application ID.
    """
    application_id = resolve_app_id(application_id, state)
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return f"Application #{application_id} not found or you don't have access to it."

        # Condition gate: all conditions must be cleared/waived
        outstanding = await get_outstanding_count(session, application_id)
        if outstanding > 0:
            return (
                f"Cannot generate Closing Disclosure for application #{application_id} "
                f"-- {outstanding} condition(s) still outstanding. Clear or waive all "
                f"conditions before generating the CD."
            )

        cd_text = await generate_cd_text(session, user, app, application_id)

        # Update CD delivery date
        app.cd_delivery_date = datetime.now(UTC)

        # Extract values for audit
        loan_amount = float(app.loan_amount) if app.loan_amount else 0
        rate_lock = await get_rate_lock_status(session, user, application_id)
        rate = 6.875
        if rate_lock and rate_lock.get("locked_rate"):
            rate = float(rate_lock["locked_rate"])
        loan_type = app.loan_type.value if app.loan_type else "conventional_30"
        term_years = 15 if loan_type == "conventional_15" else 30

        await write_audit_event(
            session,
            event_type="cd_generated",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "loan_amount": loan_amount,
                "rate": rate,
                "term_years": term_years,
            },
        )
        await session.commit()

    return cd_text
