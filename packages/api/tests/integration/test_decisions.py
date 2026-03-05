# This project was developed with assistance from AI tools.
"""Decision service integration tests with real PostgreSQL.

Validates Decision record creation, stage transitions, audit event
generation, denial_reasons JSON round-trip, and AI agreement detection
against a real database -- the class of bugs that mocked tests cannot catch.
"""

import pytest
from db.enums import (
    ApplicationStage,
    ConditionSeverity,
    ConditionStatus,
    DecisionType,
)
from db.models import AuditEvent, Condition, Decision
from sqlalchemy import select

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uw_user():
    from tests.functional.personas import underwriter

    return underwriter()


async def _set_stage(db_session, app_id, stage: ApplicationStage):
    """Move an application to the given stage."""
    from db.models import Application

    result = await db_session.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one()
    app.stage = stage
    await db_session.flush()


async def _add_conditions(db_session, app_id, *, outstanding=2, cleared=1):
    """Insert conditions: `outstanding` OPEN + `cleared` CLEARED."""
    conditions = []
    for i in range(outstanding):
        conditions.append(
            Condition(
                application_id=app_id,
                description=f"Outstanding condition {i + 1}",
                severity=ConditionSeverity.PRIOR_TO_APPROVAL,
                status=ConditionStatus.OPEN,
                issued_by="uw-test",
            )
        )
    for i in range(cleared):
        conditions.append(
            Condition(
                application_id=app_id,
                description=f"Cleared condition {i + 1}",
                severity=ConditionSeverity.PRIOR_TO_APPROVAL,
                status=ConditionStatus.CLEARED,
                issued_by="uw-test",
                cleared_by="uw-test",
            )
        )
    db_session.add_all(conditions)
    await db_session.flush()
    return conditions


async def _write_ai_recommendation(db_session, app_id, recommendation: str):
    """Insert an audit event that mimics uw_preliminary_recommendation output."""
    event = AuditEvent(
        event_type="agent_tool_called",
        user_id="uw-test",
        user_role="underwriter",
        application_id=app_id,
        event_data={
            "tool": "uw_preliminary_recommendation",
            "recommendation": recommendation,
        },
    )
    db_session.add(event)
    await db_session.flush()


# ---------------------------------------------------------------------------
# render_decision -- approve flows
# ---------------------------------------------------------------------------


class TestRenderDecisionApprove:
    """Approval paths with real DB: record creation, stage transition, audit."""

    async def test_approve_no_conditions_creates_approved_record(self, db_session, seed_data):
        """Approve from UNDERWRITING with no conditions -> APPROVED + CLEAR_TO_CLOSE."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)

        result = await render_decision(
            db_session, _uw_user(), app_id, "approve", "Strong financials"
        )

        assert result is not None
        assert "error" not in result
        assert result["decision_type"] == "approved"
        assert result["new_stage"] == "clear_to_close"

        # Verify Decision row persisted
        row = await db_session.execute(select(Decision).where(Decision.application_id == app_id))
        dec = row.scalar_one()
        assert dec.decision_type == DecisionType.APPROVED
        assert dec.rationale == "Strong financials"

        # Verify stage transitioned
        from db.models import Application

        app_row = await db_session.execute(select(Application).where(Application.id == app_id))
        app = app_row.scalar_one()
        assert app.stage == ApplicationStage.CLEAR_TO_CLOSE

    async def test_approve_with_conditions_creates_conditional(self, db_session, seed_data):
        """Approve from UNDERWRITING with outstanding conditions -> CONDITIONAL_APPROVAL."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)
        await _add_conditions(db_session, app_id, outstanding=2, cleared=0)

        result = await render_decision(
            db_session, _uw_user(), app_id, "approve", "Subject to conditions"
        )

        assert result["decision_type"] == "conditional_approval"
        assert result["new_stage"] == "conditional_approval"

        # Verify stage
        from db.models import Application

        app_row = await db_session.execute(select(Application).where(Application.id == app_id))
        assert app_row.scalar_one().stage == ApplicationStage.CONDITIONAL_APPROVAL

    async def test_approve_from_conditional_all_cleared(self, db_session, seed_data):
        """Approve from CONDITIONAL_APPROVAL (all cleared) -> APPROVED + CLEAR_TO_CLOSE."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.CONDITIONAL_APPROVAL)
        await _add_conditions(db_session, app_id, outstanding=0, cleared=3)

        result = await render_decision(
            db_session, _uw_user(), app_id, "approve", "All conditions met"
        )

        assert result["decision_type"] == "approved"
        assert result["new_stage"] == "clear_to_close"

    async def test_approve_from_conditional_outstanding_blocked(self, db_session, seed_data):
        """Approve from CONDITIONAL_APPROVAL with outstanding conditions -> error."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.CONDITIONAL_APPROVAL)
        await _add_conditions(db_session, app_id, outstanding=1, cleared=1)

        result = await render_decision(
            db_session, _uw_user(), app_id, "approve", "Trying to approve"
        )

        assert "error" in result
        assert "outstanding conditions" in result["error"].lower()


# ---------------------------------------------------------------------------
# render_decision -- deny flows
# ---------------------------------------------------------------------------


class TestRenderDecisionDeny:
    """Denial paths: stage transition, denial_reasons JSON round-trip."""

    async def test_deny_creates_denied_record(self, db_session, seed_data):
        """Deny from UNDERWRITING -> DENIED + stage DENIED."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)

        reasons = ["Insufficient income", "Credit score below 640"]
        result = await render_decision(
            db_session,
            _uw_user(),
            app_id,
            "deny",
            "Does not meet minimum criteria",
            denial_reasons=reasons,
            credit_score_used=620,
            credit_score_source="TransUnion",
            contributing_factors="Excessive revolving debt",
        )

        assert result["decision_type"] == "denied"
        assert result["new_stage"] == "denied"

        # Verify Decision row and JSON round-trip
        row = await db_session.execute(select(Decision).where(Decision.application_id == app_id))
        dec = row.scalar_one()
        assert dec.decision_type == DecisionType.DENIED
        assert dec.denial_reasons == reasons
        assert dec.credit_score_used == 620
        assert dec.credit_score_source == "TransUnion"
        assert dec.contributing_factors == "Excessive revolving debt"

        # Verify stage
        from db.models import Application

        app_row = await db_session.execute(select(Application).where(Application.id == app_id))
        assert app_row.scalar_one().stage == ApplicationStage.DENIED

    async def test_deny_without_reasons_returns_error(self, db_session, seed_data):
        """Deny without denial_reasons -> error (ECOA compliance)."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)

        result = await render_decision(db_session, _uw_user(), app_id, "deny", "Bad profile")

        assert "error" in result
        assert "denial_reason" in result["error"].lower()


# ---------------------------------------------------------------------------
# render_decision -- suspend + stage validation
# ---------------------------------------------------------------------------


class TestRenderDecisionSuspendAndEdge:
    """Suspend path and wrong-stage validation."""

    async def test_suspend_no_stage_change(self, db_session, seed_data):
        """Suspend from UNDERWRITING -> SUSPENDED, stage unchanged."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)

        result = await render_decision(
            db_session, _uw_user(), app_id, "suspend", "Missing documents"
        )

        assert result["decision_type"] == "suspended"
        assert result["new_stage"] is None

        from db.models import Application

        app_row = await db_session.execute(select(Application).where(Application.id == app_id))
        assert app_row.scalar_one().stage == ApplicationStage.UNDERWRITING

    async def test_wrong_stage_returns_error(self, db_session, seed_data):
        """Decision on APPLICATION stage -> error."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        # seed_data.sarah_app1 starts in APPLICATION stage

        result = await render_decision(db_session, _uw_user(), app_id, "approve", "Good profile")

        assert "error" in result
        assert "underwriting" in result["error"].lower()


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------


class TestDecisionAudit:
    """Verify audit events are persisted with correct structure."""

    async def test_decision_audit_event_written(self, db_session, seed_data):
        """render_decision writes a 'decision' audit event."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)

        await render_decision(db_session, _uw_user(), app_id, "approve", "Solid financials")

        events = await db_session.execute(
            select(AuditEvent).where(
                AuditEvent.application_id == app_id, AuditEvent.event_type == "decision"
            )
        )
        audit = events.scalar_one()
        assert audit.event_data["decision_type"] == "approved"
        assert audit.event_data["rationale"] == "Solid financials"
        assert audit.user_role == "underwriter"

    async def test_override_audit_event_on_disagree(self, db_session, seed_data):
        """AI override generates both 'decision' and 'override' audit events."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)
        await _write_ai_recommendation(db_session, app_id, "Deny")

        await render_decision(
            db_session,
            _uw_user(),
            app_id,
            "approve",
            "Compensating factors",
            override_rationale="Strong reserves",
        )

        override_events = await db_session.execute(
            select(AuditEvent).where(
                AuditEvent.application_id == app_id, AuditEvent.event_type == "override"
            )
        )
        override = override_events.scalar_one()
        assert override.event_data["high_risk"] is True
        assert override.event_data["override_rationale"] == "Strong reserves"


# ---------------------------------------------------------------------------
# AI agreement detection
# ---------------------------------------------------------------------------


class TestAIAgreement:
    """AI agreement/override detection with real audit events."""

    async def test_ai_concurrence(self, db_session, seed_data):
        """Decision agrees with AI recommendation -> ai_agreement=True."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)
        await _write_ai_recommendation(db_session, app_id, "Approve")

        result = await render_decision(db_session, _uw_user(), app_id, "approve", "Looks great")

        assert result["ai_agreement"] is True
        assert result["ai_recommendation"] == "Approve"

        # Verify persisted on the Decision row
        row = await db_session.execute(select(Decision).where(Decision.application_id == app_id))
        assert row.scalar_one().ai_agreement is True

    async def test_ai_override(self, db_session, seed_data):
        """Decision disagrees with AI recommendation -> ai_agreement=False."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)
        await _write_ai_recommendation(db_session, app_id, "Deny")

        result = await render_decision(
            db_session,
            _uw_user(),
            app_id,
            "approve",
            "Compensating factors present",
            override_rationale="Strong reserves",
        )

        assert result["ai_agreement"] is False

        row = await db_session.execute(select(Decision).where(Decision.application_id == app_id))
        dec = row.scalar_one()
        assert dec.ai_agreement is False
        assert dec.override_rationale == "Strong reserves"

    async def test_no_ai_recommendation_yields_null(self, db_session, seed_data):
        """No prior AI recommendation -> ai_agreement=None."""
        from src.services.decision import render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)

        result = await render_decision(
            db_session, _uw_user(), app_id, "approve", "No AI to compare"
        )

        assert result["ai_agreement"] is None
        assert result["ai_recommendation"] is None


# ---------------------------------------------------------------------------
# get_decisions / get_latest_decision
# ---------------------------------------------------------------------------


class TestQueryDecisions:
    """Query functions against real DB."""

    async def test_get_decisions_returns_ordered(self, db_session, seed_data):
        """get_decisions returns decisions in created_at order."""
        from src.services.decision import get_decisions, render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)

        # Create two decisions: first conditional, then deny
        await _add_conditions(db_session, app_id, outstanding=1, cleared=0)
        await render_decision(db_session, _uw_user(), app_id, "approve", "First pass")
        await render_decision(
            db_session,
            _uw_user(),
            app_id,
            "deny",
            "Second pass",
            denial_reasons=["Changed mind"],
        )

        decisions = await get_decisions(db_session, _uw_user(), app_id)
        assert len(decisions) == 2
        assert decisions[0]["decision_type"] == "conditional_approval"
        assert decisions[1]["decision_type"] == "denied"

    async def test_get_latest_decision(self, db_session, seed_data):
        """get_latest_decision returns the most recent."""
        from src.services.decision import get_latest_decision, render_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)

        await render_decision(db_session, _uw_user(), app_id, "suspend", "Hold on")

        latest = await get_latest_decision(db_session, _uw_user(), app_id)
        assert latest["decision_type"] == "suspended"

    async def test_get_latest_decision_no_decisions(self, db_session, seed_data):
        """get_latest_decision returns indicator when empty."""
        from src.services.decision import get_latest_decision

        app_id = seed_data.sarah_app1.id

        latest = await get_latest_decision(db_session, _uw_user(), app_id)
        assert latest is not None
        assert latest.get("no_decisions") is True


# ---------------------------------------------------------------------------
# propose_decision (preview, no DB writes)
# ---------------------------------------------------------------------------


class TestProposeDecision:
    """propose_decision validates without persisting."""

    async def test_propose_does_not_persist(self, db_session, seed_data):
        """propose_decision returns preview without creating Decision records."""
        from src.services.decision import propose_decision

        app_id = seed_data.sarah_app1.id
        await _set_stage(db_session, app_id, ApplicationStage.UNDERWRITING)

        result = await propose_decision(db_session, _uw_user(), app_id, "approve", "Preview only")

        assert result["proposal"] is True
        assert result["decision_type"] == "approved"

        # No Decision rows should exist
        rows = await db_session.execute(select(Decision).where(Decision.application_id == app_id))
        assert rows.scalars().all() == []
