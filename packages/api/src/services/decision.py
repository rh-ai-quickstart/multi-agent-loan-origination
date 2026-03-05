# This project was developed with assistance from AI tools.
"""Decision service for underwriting decision lifecycle.

Handles rendering decisions (approve/deny/suspend), comparing with AI
recommendations, and querying decision history.
"""

import logging

from db import AuditEvent, Decision
from db.enums import ApplicationStage, DecisionType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.auth import UserContext
from ..services.application import get_application
from ..services.audit import write_audit_event
from ..services.condition import get_outstanding_count

logger = logging.getLogger(__name__)

_DECISION_STAGES = frozenset({ApplicationStage.UNDERWRITING, ApplicationStage.CONDITIONAL_APPROVAL})
_APPROVAL_CATEGORIES = frozenset({"Approve", "Approve with Conditions"})
_DENY_CATEGORIES = frozenset({"Deny"})
_SUSPEND_CATEGORIES = frozenset({"Suspend"})


async def check_compliance_gate(session: AsyncSession, application_id: int) -> str | None:
    """Check that a passing compliance check exists for the application.

    Returns an error message string if the gate fails, or None if it passes.
    Does NOT enforce data scope -- caller must check access to the application first.

    Args:
        session: Database session.
        application_id: The application ID.

    Returns:
        Error message if the gate fails, None if it passes.
    """
    comp_stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.application_id == application_id,
            AuditEvent.event_type == "compliance_check",
        )
        .order_by(AuditEvent.timestamp.desc())
        .limit(1)
    )
    comp_result = await session.execute(comp_stmt)
    comp_event = comp_result.scalar_one_or_none()

    if comp_event is None:
        return (
            "Run compliance_check before rendering a decision. No compliance "
            f"check found for application #{application_id}."
        )

    event_data = comp_event.event_data or {}
    overall = event_data.get("overall_status") or event_data.get("status")
    if overall == "FAIL" or not event_data.get("can_proceed", True):
        failed_checks = event_data.get("failed_checks", [])
        failed_str = ", ".join(failed_checks) if failed_checks else "one or more checks"
        return (
            f"Cannot approve application #{application_id} -- compliance check "
            f"FAILED ({failed_str}). Resolve compliance issues before approval."
        )

    return None


async def _get_ai_recommendation(
    session: AsyncSession, application_id: int
) -> tuple[str | None, str | None]:
    """Query audit events for the last preliminary recommendation.

    Returns (recommendation_text, category) where category is the
    recommendation string from the tool output (e.g. 'Approve', 'Deny').
    """
    stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.application_id == application_id,
            AuditEvent.event_type == "agent_tool_called",
        )
        .order_by(AuditEvent.timestamp.desc())
        .limit(20)
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    for event in events:
        if event.event_data and event.event_data.get("tool") == "uw_preliminary_recommendation":
            rec = event.event_data.get("recommendation")
            return rec, rec
    return None, None


def _decision_category(decision_type: DecisionType) -> str:
    """Map a DecisionType to a recommendation category for AI comparison."""
    if decision_type in (DecisionType.APPROVED, DecisionType.CONDITIONAL_APPROVAL):
        return "approve"
    if decision_type == DecisionType.DENIED:
        return "deny"
    return "suspend"


def _ai_category(rec: str | None) -> str | None:
    """Normalize AI recommendation to a comparison category."""
    if rec is None:
        return None
    lower = rec.lower()
    if "deny" in lower:
        return "deny"
    if "suspend" in lower:
        return "suspend"
    if "approve" in lower:
        return "approve"
    return None


async def _resolve_decision(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    decision: str,
    rationale: str,
    *,
    denial_reasons: list[str] | None = None,
    override_rationale: str | None = None,
) -> dict | None:
    """Validate inputs and compute the decision outcome without persisting.

    Returns None if application not found / out of scope.
    Returns dict with "error" key on business rule violations.
    Returns dict with resolved decision details on success:
        app, decision_type, new_stage, ai_rec_text, ai_rec_category,
        ai_agreement, current_stage, outstanding_conditions.
    """
    app = await get_application(session, user, application_id)
    if app is None:
        return None

    current_stage = app.stage or ApplicationStage.INQUIRY
    if current_stage not in _DECISION_STAGES:
        return {
            "error": (
                f"Decisions can only be rendered during underwriting or conditional "
                f"approval. Application #{application_id} is in "
                f"{current_stage.value.replace('_', ' ').title()}."
            )
        }

    # Get AI recommendation for comparison
    ai_rec_text, ai_rec_category = await _get_ai_recommendation(session, application_id)

    decision_lower = decision.strip().lower()
    outstanding_conditions = 0

    # Determine decision type and new stage
    if decision_lower == "approve":
        outstanding_conditions = await get_outstanding_count(session, application_id)

        if current_stage == ApplicationStage.CONDITIONAL_APPROVAL:
            if outstanding_conditions > 0:
                return {
                    "error": (
                        f"Cannot approve application #{application_id} from Conditional "
                        f"Approval -- there are still outstanding conditions. Clear or "
                        f"waive all conditions before final approval."
                    )
                }
            decision_type = DecisionType.APPROVED
            new_stage = ApplicationStage.CLEAR_TO_CLOSE
        else:
            # From UNDERWRITING
            if outstanding_conditions > 0:
                decision_type = DecisionType.CONDITIONAL_APPROVAL
                new_stage = ApplicationStage.CONDITIONAL_APPROVAL
            else:
                decision_type = DecisionType.APPROVED
                new_stage = ApplicationStage.CLEAR_TO_CLOSE

    elif decision_lower == "deny":
        if not denial_reasons:
            return {"error": "Denial requires at least one denial_reason (ECOA compliance)."}
        decision_type = DecisionType.DENIED
        new_stage = ApplicationStage.DENIED

    elif decision_lower == "suspend":
        if current_stage != ApplicationStage.UNDERWRITING:
            return {
                "error": (
                    f"Suspend is only available from the UNDERWRITING stage. "
                    f"Application #{application_id} is in "
                    f"{current_stage.value.replace('_', ' ').title()}."
                )
            }
        decision_type = DecisionType.SUSPENDED
        new_stage = None  # No stage change for suspend
    else:
        return {"error": f"Invalid decision '{decision}'. Must be approve, deny, or suspend."}

    # Compute AI agreement
    ai_agreement = None
    if ai_rec_category is not None:
        uw_cat = _decision_category(decision_type)
        ai_cat = _ai_category(ai_rec_category)
        if ai_cat is not None:
            ai_agreement = uw_cat == ai_cat

    return {
        "app": app,
        "decision_type": decision_type,
        "new_stage": new_stage,
        "ai_rec_text": ai_rec_text,
        "ai_rec_category": ai_rec_category,
        "ai_agreement": ai_agreement,
        "current_stage": current_stage,
        "outstanding_conditions": outstanding_conditions,
    }


async def propose_decision(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    decision: str,
    rationale: str,
    *,
    denial_reasons: list[str] | None = None,
    override_rationale: str | None = None,
) -> dict | None:
    """Preview what a decision would do without persisting anything.

    Returns the same error/None semantics as render_decision, but on
    success returns a preview dict instead of creating records.
    """
    resolved = await _resolve_decision(
        session,
        user,
        application_id,
        decision,
        rationale,
        denial_reasons=denial_reasons,
        override_rationale=override_rationale,
    )

    if resolved is None or "error" in resolved:
        return resolved

    dt = resolved["decision_type"]
    new_stage = resolved["new_stage"]
    ai_agreement = resolved["ai_agreement"]

    return {
        "proposal": True,
        "application_id": application_id,
        "decision_type": dt.value,
        "new_stage": new_stage.value if new_stage else None,
        "current_stage": resolved["current_stage"].value,
        "rationale": rationale,
        "ai_recommendation": resolved["ai_rec_text"],
        "ai_agreement": ai_agreement,
        "denial_reasons": denial_reasons,
        "outstanding_conditions": resolved["outstanding_conditions"],
        "override_rationale": override_rationale if ai_agreement is False else None,
    }


async def render_decision(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    decision: str,
    rationale: str,
    *,
    denial_reasons: list[str] | None = None,
    credit_score_used: int | None = None,
    credit_score_source: str | None = None,
    contributing_factors: str | None = None,
    override_rationale: str | None = None,
) -> dict | None:
    """Render an underwriting decision on an application.

    Returns None if application not found / out of scope.
    Returns dict with "error" key on business rule violations.
    Returns dict with decision details on success.
    """
    resolved = await _resolve_decision(
        session,
        user,
        application_id,
        decision,
        rationale,
        denial_reasons=denial_reasons,
        override_rationale=override_rationale,
    )

    if resolved is None or "error" in resolved:
        return resolved

    app = resolved["app"]
    decision_type = resolved["decision_type"]
    new_stage = resolved["new_stage"]
    ai_rec_text = resolved["ai_rec_text"]
    ai_rec_category = resolved["ai_rec_category"]
    ai_agreement = resolved["ai_agreement"]

    # Create Decision record
    decision_record = Decision(
        application_id=application_id,
        decision_type=decision_type,
        rationale=rationale,
        ai_recommendation=ai_rec_text,
        decided_by=user.user_id,
        ai_agreement=ai_agreement,
        override_rationale=override_rationale if ai_agreement is False else None,
        denial_reasons=denial_reasons,
        credit_score_used=credit_score_used,
        credit_score_source=credit_score_source,
        contributing_factors=contributing_factors,
    )
    session.add(decision_record)

    # Transition stage
    if new_stage is not None:
        app.stage = new_stage

    # Write decision audit event
    await write_audit_event(
        session,
        event_type="decision",
        user_id=user.user_id,
        user_role=user.role.value,
        application_id=application_id,
        event_data={
            "decision_type": decision_type.value,
            "rationale": rationale,
            "ai_recommendation": ai_rec_text,
            "ai_agreement": ai_agreement,
            "new_stage": new_stage.value if new_stage else None,
            "denial_reasons": denial_reasons,
        },
    )

    # Write override audit event if AI disagrees
    if ai_agreement is False:
        is_high_risk = (
            _ai_category(ai_rec_category) == "deny"
            and _decision_category(decision_type) == "approve"
        )
        await write_audit_event(
            session,
            event_type="override",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "ai_recommendation": ai_rec_text,
                "uw_decision": decision_type.value,
                "override_rationale": override_rationale,
                "high_risk": is_high_risk,
            },
        )

    await session.commit()
    await session.refresh(decision_record)

    return {
        "id": decision_record.id,
        "application_id": application_id,
        "decision_type": decision_record.decision_type.value,
        "rationale": decision_record.rationale,
        "ai_recommendation": decision_record.ai_recommendation,
        "ai_agreement": decision_record.ai_agreement,
        "override_rationale": decision_record.override_rationale,
        "denial_reasons": denial_reasons,
        "credit_score_used": decision_record.credit_score_used,
        "credit_score_source": decision_record.credit_score_source,
        "contributing_factors": decision_record.contributing_factors,
        "decided_by": decision_record.decided_by,
        "new_stage": new_stage.value if new_stage else None,
    }


async def get_decisions(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
) -> list[dict] | None:
    """List all decisions for an application, ordered by created_at.

    Returns None if application not found / out of scope.
    """
    app = await get_application(session, user, application_id)
    if app is None:
        return None

    stmt = (
        select(Decision)
        .where(Decision.application_id == application_id)
        .order_by(Decision.created_at.asc())
    )
    result = await session.execute(stmt)
    decisions = result.scalars().all()

    return [_decision_to_dict(d) for d in decisions]


async def get_latest_decision(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
) -> dict | None:
    """Get the most recent decision for an application.

    Returns None if application not found / out of scope.
    Returns {"no_decisions": True} if no decisions exist for the application.
    Returns decision dict otherwise.
    """
    app = await get_application(session, user, application_id)
    if app is None:
        return None

    stmt = (
        select(Decision)
        .where(Decision.application_id == application_id)
        .order_by(Decision.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    decision = result.scalar_one_or_none()

    if decision is None:
        return {"no_decisions": True}

    return _decision_to_dict(decision)


def _decision_to_dict(d: Decision) -> dict:
    """Convert a Decision ORM object to a dict."""
    return {
        "id": d.id,
        "application_id": d.application_id,
        "decision_type": d.decision_type.value if d.decision_type else None,
        "rationale": d.rationale,
        "ai_recommendation": d.ai_recommendation,
        "ai_agreement": d.ai_agreement,
        "override_rationale": d.override_rationale,
        "denial_reasons": d.denial_reasons,
        "credit_score_used": d.credit_score_used,
        "credit_score_source": d.credit_score_source,
        "contributing_factors": d.contributing_factors,
        "decided_by": d.decided_by,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }
