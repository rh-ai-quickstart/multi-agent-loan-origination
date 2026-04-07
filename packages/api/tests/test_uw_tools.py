# This project was developed with assistance from AI tools.
"""Unit tests for underwriter agent tools.

Focus: _user_context_from_state (underwriter scope), uw_queue_view
(read + urgency sorting), uw_application_detail (multi-section output),
uw_save_risk_assessment (persistence + audit), and
uw_preliminary_recommendation (decision tree).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db.enums import ApplicationStage, UserRole

from src.agents.risk_tools import compute_risk_factors
from src.agents.underwriter_tools import (
    _user_context_from_state,
    uw_application_detail,
    uw_preliminary_recommendation,
    uw_queue_view,
    uw_save_risk_assessment,
)

# ---------------------------------------------------------------------------
# _user_context_from_state
# ---------------------------------------------------------------------------


class TestUserContextFromState:
    """The helper that builds UserContext for all UW tools."""

    def test_builds_underwriter_scope(self):
        """underwriter role produces DataScope(full_pipeline=True)."""
        state = {
            "user_id": "uw-maria",
            "user_role": "underwriter",
            "user_email": "maria@example.com",
            "user_name": "Maria Chen",
        }
        ctx = _user_context_from_state(state)

        assert ctx.user_id == "uw-maria"
        assert ctx.role == UserRole.UNDERWRITER
        assert ctx.data_scope.full_pipeline is True
        assert ctx.data_scope.assigned_to is None
        assert ctx.data_scope.own_data_only is False


# ---------------------------------------------------------------------------
# uw_queue_view
# ---------------------------------------------------------------------------


class TestUwQueueView:
    """Verify queue listing with urgency sorting."""

    @pytest.mark.asyncio
    async def test_queue_returns_apps_with_urgency(self):
        """Mock 2 apps, verify formatting and urgency-based sorting."""
        mock_borrower1 = MagicMock()
        mock_borrower1.first_name = "Sarah"
        mock_borrower1.last_name = "Johnson"
        mock_ab1 = MagicMock()
        mock_ab1.borrower = mock_borrower1
        mock_ab1.is_primary = True

        mock_app1 = MagicMock()
        mock_app1.id = 1
        mock_app1.loan_amount = 350000
        mock_app1.property_address = "123 Oak St"
        mock_app1.assigned_to = "lo-james"
        mock_app1.application_borrowers = [mock_ab1]

        mock_borrower2 = MagicMock()
        mock_borrower2.first_name = "Tom"
        mock_borrower2.last_name = "Lee"
        mock_ab2 = MagicMock()
        mock_ab2.borrower = mock_borrower2
        mock_ab2.is_primary = True

        mock_app2 = MagicMock()
        mock_app2.id = 2
        mock_app2.loan_amount = 500000
        mock_app2.property_address = "456 Elm St"
        mock_app2.assigned_to = "lo-anna"
        mock_app2.application_borrowers = [mock_ab2]

        from src.schemas.urgency import UrgencyIndicator, UrgencyLevel

        urgency_map = {
            1: UrgencyIndicator(
                level=UrgencyLevel.NORMAL, factors=[], days_in_stage=2, expected_stage_days=5
            ),
            2: UrgencyIndicator(
                level=UrgencyLevel.HIGH,
                factors=["Rate lock expires in 5 days"],
                days_in_stage=4,
                expected_stage_days=5,
            ),
        }

        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.list_applications",
                new_callable=AsyncMock,
                return_value=([mock_app1, mock_app2], 2),
            ),
            patch(
                "src.agents.underwriter_tools.compute_urgency",
                new_callable=AsyncMock,
                return_value=urgency_map,
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_queue_view.ainvoke({"state": state})

        assert "Underwriting Queue (2 applications)" in result
        assert "Sarah Johnson" in result
        assert "Tom Lee" in result
        # HIGH urgency app should appear before NORMAL
        tom_pos = result.index("Tom Lee")
        sarah_pos = result.index("Sarah Johnson")
        assert tom_pos < sarah_pos

    @pytest.mark.asyncio
    async def test_queue_returns_empty(self):
        """No apps in underwriting returns empty message."""
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.list_applications",
                new_callable=AsyncMock,
                return_value=([], 0),
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_queue_view.ainvoke({"state": state})

        assert "No applications in underwriting queue" in result

    @pytest.mark.asyncio
    async def test_queue_audits_access(self):
        """Verify audit event is written on queue view."""
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.list_applications",
                new_callable=AsyncMock,
                return_value=([], 0),
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ) as mock_audit,
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await uw_queue_view.ainvoke({"state": state})

        mock_audit.assert_awaited_once()
        audit_call = mock_audit.call_args
        assert audit_call.kwargs["event_type"] == "data_access"
        assert audit_call.kwargs["event_data"]["action"] == "underwriter_queue_view"


# ---------------------------------------------------------------------------
# uw_application_detail
# ---------------------------------------------------------------------------


class TestUwApplicationDetail:
    """Verify multi-section application detail output."""

    @pytest.mark.asyncio
    async def test_detail_returns_full_info(self):
        """Mock app, financials, docs, conditions -- verify all sections present."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "Sarah"
        mock_borrower.last_name = "Johnson"
        mock_borrower.email = "sarah@test.com"
        mock_borrower.employment_status = MagicMock(value="w2_employee")

        mock_ab = MagicMock()
        mock_ab.borrower = mock_borrower
        mock_ab.is_primary = True

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_type = MagicMock(value="conventional_30")
        mock_app.loan_amount = 350000
        mock_app.property_value = 450000
        mock_app.property_address = "123 Oak St"
        mock_app.application_borrowers = [mock_ab]

        mock_fin = MagicMock()
        mock_fin.gross_monthly_income = 8000
        mock_fin.monthly_debts = 2500
        mock_fin.total_assets = 120000
        mock_fin.credit_score = 720

        mock_doc = MagicMock()
        mock_doc.id = 10
        mock_doc.doc_type = MagicMock(value="w2_form")
        mock_doc.status = MagicMock(value="processing_complete")
        mock_doc.quality_flags = None

        mock_conditions = [
            {
                "id": 1,
                "description": "Verify employment",
                "severity": "prior_to_approval",
                "status": "open",
            }
        ]

        mock_rate_lock = {
            "status": "active",
            "locked_rate": 6.75,
            "expiration_date": "2025-04-15",
            "days_remaining": 10,
            "is_urgent": False,
        }

        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([mock_doc], 1),
            ),
            patch(
                "src.agents.underwriter_tools.get_conditions",
                new_callable=AsyncMock,
                return_value=mock_conditions,
            ),
            patch(
                "src.agents.underwriter_tools.get_rate_lock_status",
                new_callable=AsyncMock,
                return_value=mock_rate_lock,
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            # Mock the financials query
            mock_fin_result = MagicMock()
            mock_fin_result.scalars.return_value.all.return_value = [mock_fin]
            mock_session.execute = AsyncMock(return_value=mock_fin_result)
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_application_detail.ainvoke({"application_id": 101, "state": state})

        assert "Application #101" in result
        assert "BORROWER PROFILE:" in result
        assert "Sarah Johnson" in result
        assert "W2 Employee" in result
        assert "FINANCIAL SUMMARY:" in result
        assert "$8,000.00" in result
        assert "DTI ratio:" in result
        assert "LOAN DETAILS:" in result
        assert "LTV ratio:" in result
        assert "DOCUMENTS (1):" in result
        assert "w2_form" in result
        assert "CONDITIONS (1):" in result
        assert "Verify employment" in result
        assert "RATE LOCK:" in result
        assert "6.750%" in result

    @pytest.mark.asyncio
    async def test_detail_not_found(self):
        """get_application returns None => error message."""
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_application_detail.ainvoke({"application_id": 999, "state": state})

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_detail_audits_view(self):
        """Verify audit event is written on detail view."""
        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_type = None
        mock_app.loan_amount = None
        mock_app.property_value = None
        mock_app.property_address = None
        mock_app.application_borrowers = []

        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([], 0),
            ),
            patch(
                "src.agents.underwriter_tools.get_conditions",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "src.agents.underwriter_tools.get_rate_lock_status",
                new_callable=AsyncMock,
                return_value={"status": "none"},
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ) as mock_audit,
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_fin_result = MagicMock()
            mock_fin_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_fin_result)
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await uw_application_detail.ainvoke({"application_id": 101, "state": state})

        mock_audit.assert_awaited_once()
        audit_call = mock_audit.call_args
        assert audit_call.kwargs["event_type"] == "data_access"
        assert audit_call.kwargs["event_data"]["action"] == "underwriter_detail_view"


# ---------------------------------------------------------------------------
# compute_risk_factors (pure function tests)
# ---------------------------------------------------------------------------


def _make_fin(income=8000, debts=2500, assets=120000, credit=720):
    """Create a mock ApplicationFinancials row."""
    m = MagicMock()
    m.gross_monthly_income = income
    m.monthly_debts = debts
    m.total_assets = assets
    m.credit_score = credit
    return m


def _make_app(loan_amount=350000, property_value=450000):
    """Create a mock Application with loan and property values."""
    m = MagicMock()
    m.loan_amount = loan_amount
    m.property_value = property_value
    return m


class TestComputeRiskFactors:
    """Unit tests for the pure risk factor computation."""

    def test_dti_single_borrower(self):
        """DTI = debts / income = 2500/8000 = 31.25% -> Low."""
        app = _make_app()
        fins = [_make_fin(income=8000, debts=2500)]
        borrowers = [{"name": "Test", "is_primary": True, "employment_status": "w2_employee"}]

        result = compute_risk_factors(app, fins, borrowers)
        assert result.dti["value"] == 31.2
        assert result.dti["rating"] == "Low"

    def test_dti_co_borrower(self):
        """Combined income/debts across two borrowers."""
        app = _make_app()
        fins = [
            _make_fin(income=5000, debts=1500, credit=700),
            _make_fin(income=4000, debts=2000, credit=680),
        ]
        borrowers = [
            {"name": "A", "is_primary": True, "employment_status": "w2_employee"},
            {"name": "B", "is_primary": False, "employment_status": "w2_employee"},
        ]

        result = compute_risk_factors(app, fins, borrowers)
        # DTI = (1500+2000) / (5000+4000) = 3500/9000 = 38.9% -> Medium
        assert result.dti["value"] == pytest.approx(38.9, abs=0.1)
        assert result.dti["rating"] == "Medium"

    def test_credit_uses_lower_score(self):
        """Min of two borrowers' credit scores is used."""
        app = _make_app()
        fins = [_make_fin(credit=750), _make_fin(credit=640)]
        borrowers = []

        result = compute_risk_factors(app, fins, borrowers)
        assert result.credit["value"] == 640
        assert result.credit["rating"] == "Medium"

    def test_flags_high_dti(self):
        """DTI > 43% rated High."""
        app = _make_app()
        fins = [_make_fin(income=5000, debts=2500)]  # 50%
        borrowers = []

        result = compute_risk_factors(app, fins, borrowers)
        assert result.dti["value"] == 50.0
        assert result.dti["rating"] == "High"

    def test_flags_high_ltv(self):
        """LTV > 80% rated High."""
        app = _make_app(loan_amount=400000, property_value=450000)  # 88.9%
        fins = [_make_fin()]
        borrowers = []

        result = compute_risk_factors(app, fins, borrowers)
        assert result.ltv["value"] == pytest.approx(88.9, abs=0.1)
        assert result.ltv["rating"] == "High"

    def test_flags_low_credit(self):
        """Credit < 620 rated High."""
        app = _make_app()
        fins = [_make_fin(credit=580)]
        borrowers = []

        result = compute_risk_factors(app, fins, borrowers)
        assert result.credit["value"] == 580
        assert result.credit["rating"] == "High"

    def test_compensating_factors(self):
        """Strong credit (>740) + elevated DTI triggers compensating factor."""
        app = _make_app()
        fins = [_make_fin(income=5000, debts=2500, credit=760)]  # 50% DTI
        borrowers = []

        result = compute_risk_factors(app, fins, borrowers)
        assert result.dti["rating"] == "High"
        assert any("Strong credit" in f for f in result.compensating_factors)

    def test_handles_missing_financials(self):
        """No financials -> warnings, None values."""
        app = _make_app()
        fins = []
        borrowers = []

        result = compute_risk_factors(app, fins, borrowers)
        assert result.dti["value"] is None
        assert len(result.warnings) > 0

    def test_dti_boundary_at_43_is_medium(self):
        """DTI exactly 43% is Medium, not High (boundary test)."""
        app = _make_app()
        fins = [_make_fin(income=10000, debts=4300)]  # 43%
        borrowers = []

        result = compute_risk_factors(app, fins, borrowers)
        assert result.dti["value"] == 43.0
        assert result.dti["rating"] == "Medium"

    def test_ltv_boundary_at_80_is_medium(self):
        """LTV exactly 80% is Medium, not High (boundary test)."""
        app = _make_app(loan_amount=360000, property_value=450000)  # 80%
        fins = [_make_fin()]
        borrowers = []

        result = compute_risk_factors(app, fins, borrowers)
        assert result.ltv["value"] == 80.0
        assert result.ltv["rating"] == "Medium"

    def test_income_stability_unemployed_is_high(self):
        """Unemployed borrower -> High stability risk."""
        app = _make_app()
        fins = [_make_fin()]
        borrowers = [{"name": "Test", "is_primary": True, "employment_status": "unemployed"}]

        result = compute_risk_factors(app, fins, borrowers)
        assert result.income_stability["rating"] == "High"

    def test_income_stability_self_employed_is_medium(self):
        """Self-employed borrower -> Medium stability risk."""
        app = _make_app()
        fins = [_make_fin()]
        borrowers = [{"name": "Test", "is_primary": True, "employment_status": "self_employed"}]

        result = compute_risk_factors(app, fins, borrowers)
        assert result.income_stability["rating"] == "Medium"

    def test_low_ltv_offsets_weak_credit(self):
        """Low LTV (<60%) + High credit risk -> compensating factor."""
        app = _make_app(loan_amount=200000, property_value=450000)  # LTV ~44%
        fins = [_make_fin(credit=590)]  # High risk
        borrowers = []

        result = compute_risk_factors(app, fins, borrowers)
        assert result.ltv["rating"] == "Low"
        assert result.credit["rating"] == "High"
        assert any("Low LTV" in f for f in result.compensating_factors)

    def test_high_reserves_compensating_factor(self):
        """Assets >50% of loan triggers compensating factor."""
        app = _make_app(loan_amount=200000)
        fins = [_make_fin(assets=150000)]  # 75% of loan
        borrowers = []

        result = compute_risk_factors(app, fins, borrowers)
        assert any("High reserves" in f for f in result.compensating_factors)


# ---------------------------------------------------------------------------
# uw_save_risk_assessment (tool tests)
# ---------------------------------------------------------------------------


def _mock_session_with_fins(financials_rows):
    """Create a mock session that returns given financials from execute().

    Returns two results in order:
      1. Financials query (via get_financials) -- scalars().all() -> financials_rows
      2. CreditReport query (no hard pull) -- scalars().first() -> None
    """
    mock_session = AsyncMock()

    # Financials query result (first execute call via get_financials)
    mock_fin_result = MagicMock()
    mock_fin_result.scalars.return_value.all.return_value = financials_rows

    # CreditReport query result (second execute call -- no hard pull on file)
    mock_cr_result = MagicMock()
    mock_cr_result.scalars.return_value.first.return_value = None

    mock_session.execute = AsyncMock(side_effect=[mock_fin_result, mock_cr_result])
    return mock_session


_SAVE_PARAMS = {
    "application_id": 1,
    "dti_value": 31.2,
    "dti_rating": "Low",
    "ltv_value": 77.8,
    "ltv_rating": "Medium",
    "credit_value": 720,
    "credit_rating": "Low",
    "credit_source": "self_reported",
    "income_stability_value": "w2_employee",
    "income_stability_rating": "Low",
    "asset_sufficiency_value": 34.3,
    "asset_sufficiency_rating": "Low",
    "overall_risk": "Medium",
    "recommendation": "Approve",
    "rationale": None,
    "conditions": None,
    "compensating_factors": None,
    "warnings": None,
}


class TestUwSaveRiskAssessment:
    """Tests for the uw_save_risk_assessment tool."""

    @pytest.mark.asyncio
    async def test_rejects_non_underwriting_stage(self):
        """Wrong stage returns error and writes audit."""
        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.APPLICATION

        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ) as mock_audit,
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_save_risk_assessment.ainvoke({**_SAVE_PARAMS, "state": state})

        assert "only available for applications in the UNDERWRITING" in result
        mock_audit.assert_awaited_once()
        assert "wrong_stage" in mock_audit.call_args.kwargs["event_data"]["error"]

    @pytest.mark.asyncio
    async def test_saves_and_audits(self):
        """Successful save persists assessment and writes audit event."""
        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING

        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ) as mock_create,
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ) as mock_audit,
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_save_risk_assessment.ainvoke({**_SAVE_PARAMS, "state": state})

        assert "saved" in result.lower()
        assert "Approve" in result
        mock_create.assert_awaited_once()
        mock_audit.assert_awaited_once()
        audit_data = mock_audit.call_args.kwargs["event_data"]
        assert audit_data["tool"] == "uw_save_risk_assessment"
        assert audit_data["dti"] == 31.2

    @pytest.mark.asyncio
    async def test_not_found(self):
        """Application not found returns error."""
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_save_risk_assessment.ainvoke({**_SAVE_PARAMS, "state": state})

        assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# uw_preliminary_recommendation (tool tests)
# ---------------------------------------------------------------------------


class TestUwPreliminaryRecommendation:
    """Tests for the uw_preliminary_recommendation tool."""

    @pytest.mark.asyncio
    async def test_recommends_approve(self):
        """All low risk -> Approve."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "Good"
        mock_borrower.last_name = "Borrower"
        mock_borrower.employment_status = MagicMock(value="w2_employee")

        mock_ab = MagicMock()
        mock_ab.borrower = mock_borrower
        mock_ab.is_primary = True

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_amount = 200000
        mock_app.property_value = 400000  # LTV = 50% (Low)
        mock_app.application_borrowers = [mock_ab]

        mock_doc = MagicMock()
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([mock_doc], 1),
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            # income=10000, debts=2000 -> DTI 20% (Low), credit=720 (Low)
            mock_session = _mock_session_with_fins(
                [_make_fin(income=10000, debts=2000, assets=100000, credit=720)]
            )
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_preliminary_recommendation.ainvoke(
                {"application_id": 1, "state": state}
            )

        assert "RECOMMENDATION: Approve" in result
        assert "Conditions" not in result.split("RECOMMENDATION:")[1].split("\n")[0]

    @pytest.mark.asyncio
    async def test_recommends_conditions_high_dti(self):
        """DTI > 43% triggers Approve with Conditions."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "Test"
        mock_borrower.last_name = "User"
        mock_borrower.employment_status = MagicMock(value="w2_employee")

        mock_ab = MagicMock()
        mock_ab.borrower = mock_borrower
        mock_ab.is_primary = True

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_amount = 300000
        mock_app.property_value = 450000  # LTV 66.7% (Medium)
        mock_app.application_borrowers = [mock_ab]

        mock_doc = MagicMock()
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([mock_doc], 1),
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            # DTI = 4500/9000 = 50% -> conditions
            mock_session = _mock_session_with_fins([_make_fin(income=9000, debts=4500, credit=720)])
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_preliminary_recommendation.ainvoke(
                {"application_id": 1, "state": state}
            )

        assert "RECOMMENDATION: Approve with Conditions" in result
        assert "DTI" in result
        assert "QM safe harbor" in result

    @pytest.mark.asyncio
    async def test_recommends_conditions_high_ltv(self):
        """LTV > 80% triggers PMI condition."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "Test"
        mock_borrower.last_name = "User"
        mock_borrower.employment_status = MagicMock(value="w2_employee")

        mock_ab = MagicMock()
        mock_ab.borrower = mock_borrower
        mock_ab.is_primary = True

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_amount = 420000
        mock_app.property_value = 450000  # LTV 93.3%
        mock_app.application_borrowers = [mock_ab]

        mock_doc = MagicMock()
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([mock_doc], 1),
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = _mock_session_with_fins(
                [_make_fin(income=10000, debts=2000, credit=720)]
            )
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_preliminary_recommendation.ainvoke(
                {"application_id": 1, "state": state}
            )

        assert "Approve with Conditions" in result
        assert "PMI" in result

    @pytest.mark.asyncio
    async def test_recommends_deny_extreme_dti(self):
        """DTI > 55% triggers Deny."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "Test"
        mock_borrower.last_name = "User"
        mock_borrower.employment_status = MagicMock(value="w2_employee")

        mock_ab = MagicMock()
        mock_ab.borrower = mock_borrower
        mock_ab.is_primary = True

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_amount = 300000
        mock_app.property_value = 450000
        mock_app.application_borrowers = [mock_ab]

        mock_doc = MagicMock()
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([mock_doc], 1),
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            # DTI = 6000/10000 = 60% -> Deny
            mock_session = _mock_session_with_fins(
                [_make_fin(income=10000, debts=6000, credit=720)]
            )
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_preliminary_recommendation.ainvoke(
                {"application_id": 1, "state": state}
            )

        assert "RECOMMENDATION: Deny" in result
        assert "55%" in result

    @pytest.mark.asyncio
    async def test_recommends_deny_low_credit(self):
        """Credit < 580 triggers Deny."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "Test"
        mock_borrower.last_name = "User"
        mock_borrower.employment_status = MagicMock(value="w2_employee")

        mock_ab = MagicMock()
        mock_ab.borrower = mock_borrower
        mock_ab.is_primary = True

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_amount = 300000
        mock_app.property_value = 450000
        mock_app.application_borrowers = [mock_ab]

        mock_doc = MagicMock()
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([mock_doc], 1),
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = _mock_session_with_fins(
                [_make_fin(income=10000, debts=2000, credit=550)]
            )
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_preliminary_recommendation.ainvoke(
                {"application_id": 1, "state": state}
            )

        assert "RECOMMENDATION: Deny" in result
        assert "580" in result

    @pytest.mark.asyncio
    async def test_recommends_conditions_self_employed(self):
        """Self-employed borrower triggers 'verify tax returns' condition."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "Test"
        mock_borrower.last_name = "User"
        mock_borrower.employment_status = MagicMock(value="self_employed")

        mock_ab = MagicMock()
        mock_ab.borrower = mock_borrower
        mock_ab.is_primary = True

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_amount = 200000
        mock_app.property_value = 400000  # LTV 50%
        mock_app.application_borrowers = [mock_ab]

        mock_doc = MagicMock()
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([mock_doc], 1),
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = _mock_session_with_fins(
                [_make_fin(income=10000, debts=2000, credit=720)]
            )
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_preliminary_recommendation.ainvoke(
                {"application_id": 1, "state": state}
            )

        assert "Approve with Conditions" in result
        assert "Self-employed" in result
        assert "tax returns" in result

    @pytest.mark.asyncio
    async def test_recommends_deny_unemployed_no_co_borrower(self):
        """Unemployed primary with no employed co-borrower triggers Deny."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "Test"
        mock_borrower.last_name = "User"
        mock_borrower.employment_status = MagicMock(value="unemployed")

        mock_ab = MagicMock()
        mock_ab.borrower = mock_borrower
        mock_ab.is_primary = True

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_amount = 200000
        mock_app.property_value = 400000
        mock_app.application_borrowers = [mock_ab]

        mock_doc = MagicMock()
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([mock_doc], 1),
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = _mock_session_with_fins(
                [_make_fin(income=10000, debts=2000, credit=720)]
            )
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_preliminary_recommendation.ainvoke(
                {"application_id": 1, "state": state}
            )

        assert "RECOMMENDATION: Deny" in result
        assert "unemployed" in result.lower()

    @pytest.mark.asyncio
    async def test_recommends_suspend_no_documents(self):
        """No documents on file triggers Suspend."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "Test"
        mock_borrower.last_name = "User"
        mock_borrower.employment_status = MagicMock(value="w2_employee")

        mock_ab = MagicMock()
        mock_ab.borrower = mock_borrower
        mock_ab.is_primary = True

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_amount = 200000
        mock_app.property_value = 400000
        mock_app.application_borrowers = [mock_ab]

        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([], 0),  # No documents
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = _mock_session_with_fins(
                [_make_fin(income=10000, debts=2000, credit=720)]
            )
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_preliminary_recommendation.ainvoke(
                {"application_id": 1, "state": state}
            )

        assert "RECOMMENDATION: Suspend" in result
        assert "No documents" in result

    @pytest.mark.asyncio
    async def test_recommends_suspend_missing_data(self):
        """No financials triggers Suspend."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "Test"
        mock_borrower.last_name = "User"
        mock_borrower.employment_status = MagicMock(value="w2_employee")

        mock_ab = MagicMock()
        mock_ab.borrower = mock_borrower
        mock_ab.is_primary = True

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_amount = 300000
        mock_app.property_value = 450000
        mock_app.application_borrowers = [mock_ab]

        mock_doc = MagicMock()
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([mock_doc], 1),
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = _mock_session_with_fins([])
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await uw_preliminary_recommendation.ainvoke(
                {"application_id": 1, "state": state}
            )

        assert "RECOMMENDATION: Suspend" in result
        assert "Missing financial data" in result

    @pytest.mark.asyncio
    async def test_audits_recommendation(self):
        """Verify audit event written with recommendation."""
        mock_borrower = MagicMock()
        mock_borrower.first_name = "Test"
        mock_borrower.last_name = "User"
        mock_borrower.employment_status = MagicMock(value="w2_employee")

        mock_ab = MagicMock()
        mock_ab.borrower = mock_borrower
        mock_ab.is_primary = True

        mock_app = MagicMock()
        mock_app.stage = ApplicationStage.UNDERWRITING
        mock_app.loan_amount = 200000
        mock_app.property_value = 400000
        mock_app.application_borrowers = [mock_ab]

        mock_doc = MagicMock()
        state = {"user_id": "uw-maria", "user_role": "underwriter"}

        with (
            patch(
                "src.agents.underwriter_tools.get_application",
                new_callable=AsyncMock,
                return_value=mock_app,
            ),
            patch(
                "src.agents.underwriter_tools.list_documents",
                new_callable=AsyncMock,
                return_value=([mock_doc], 1),
            ),
            patch(
                "src.agents.underwriter_tools.update_recommendation",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.create_risk_assessment",
                new_callable=AsyncMock,
            ),
            patch(
                "src.agents.underwriter_tools.write_audit_event",
                new_callable=AsyncMock,
            ) as mock_audit,
            patch("src.agents.underwriter_tools.SessionLocal") as mock_session_cls,
        ):
            mock_session = _mock_session_with_fins(
                [_make_fin(income=10000, debts=2000, credit=720)]
            )
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await uw_preliminary_recommendation.ainvoke({"application_id": 1, "state": state})

        mock_audit.assert_awaited_once()
        audit_data = mock_audit.call_args.kwargs["event_data"]
        assert audit_data["tool"] == "uw_preliminary_recommendation"
        assert audit_data["recommendation"] == "Approve"
