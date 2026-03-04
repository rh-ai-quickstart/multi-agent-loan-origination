# This project was developed with assistance from AI tools.
"""Tests for loan officer pre-qualification tools.

Tests lo_pull_credit, lo_prequalification_check, and lo_issue_prequalification.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db.enums import ApplicationStage

from src.agents.loan_officer_tools import (
    lo_issue_prequalification,
    lo_prequalification_check,
    lo_pull_credit,
)
from src.schemas.credit import HardPullResult, SoftPullResult, TradeLineDetail

_STATE = {"user_id": "lo-james", "user_role": "loan_officer"}


def _mock_session_ctx():
    """Build a mock SessionLocal context manager."""
    mock_session_cls = MagicMock()
    mock_session = AsyncMock()
    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_session_cls, mock_session


def _mock_app(stage=ApplicationStage.INQUIRY, loan_amount=300000, property_value=400000):
    """Build a mock Application with a primary borrower."""
    mock_borrower = MagicMock()
    mock_borrower.id = 1
    mock_borrower.keycloak_user_id = "kc-sarah"
    mock_borrower.first_name = "Sarah"
    mock_borrower.last_name = "Mitchell"

    mock_ab = MagicMock()
    mock_ab.is_primary = True
    mock_ab.borrower = mock_borrower

    app = MagicMock()
    app.stage = stage
    app.loan_amount = loan_amount
    app.property_value = property_value
    app.loan_type = MagicMock(value="conventional_30")
    app.application_borrowers = [mock_ab]
    return app


# ---------------------------------------------------------------------------
# lo_pull_credit
# ---------------------------------------------------------------------------


class TestLoPullCredit:
    """Credit pull tool: calls bureau, stores CreditReport, writes audit."""

    @pytest.mark.asyncio
    async def test_soft_pull_stores_correct_report(self):
        """Verify the CreditReport object has correct pull_type, borrower_id, and 30-day expiry."""
        mock_result = SoftPullResult(
            credit_score=742,
            outstanding_accounts=4,
            total_outstanding_debt=Decimal("45200.00"),
            derogatory_marks=0,
            oldest_account_years=12,
        )
        mock_bureau = MagicMock()
        mock_bureau.soft_pull.return_value = mock_result

        mock_session_cls, mock_session = _mock_session_ctx()

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=_mock_app(),
            ),
            patch(
                "src.agents.loan_officer_tools.get_credit_bureau_service", return_value=mock_bureau
            ),
            patch(
                "src.agents.loan_officer_tools.write_audit_event", new_callable=AsyncMock
            ) as mock_audit,
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            result = await lo_pull_credit.ainvoke(
                {"application_id": 101, "pull_type": "soft", "state": _STATE}
            )

        # Verify the CreditReport passed to session.add
        report = mock_session.add.call_args[0][0]
        assert report.pull_type == "soft"
        assert report.borrower_id == 1
        assert report.application_id == 101
        assert report.credit_score == 742
        assert report.trade_lines is None  # soft pull has no trade lines
        # Soft pull expires in 30 days
        days_until_expiry = (report.expires_at - report.pulled_at).days
        assert days_until_expiry == 30

        # Audit event records the pull type and score
        audit_data = mock_audit.call_args.kwargs["event_data"]
        assert audit_data["pull_type"] == "soft"
        assert audit_data["credit_score"] == 742
        assert audit_data["borrower_id"] == 1

        assert "742" in result

    @pytest.mark.asyncio
    async def test_hard_pull_stores_trade_lines_and_120_day_expiry(self):
        """Hard pull serializes trade lines and uses 120-day expiry."""
        mock_result = HardPullResult(
            credit_score=742,
            outstanding_accounts=4,
            total_outstanding_debt=Decimal("45200.00"),
            derogatory_marks=0,
            oldest_account_years=12,
            trade_lines=[
                TradeLineDetail(
                    account_type="credit_card",
                    balance=Decimal("5000"),
                    credit_limit=Decimal("10000"),
                    monthly_payment=Decimal("150"),
                    status="current",
                    opened_years_ago=5,
                ),
            ],
            collections_count=0,
            bankruptcy_flag=False,
            public_records_count=0,
        )
        mock_bureau = MagicMock()
        mock_bureau.hard_pull.return_value = mock_result

        mock_session_cls, mock_session = _mock_session_ctx()

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=_mock_app(),
            ),
            patch(
                "src.agents.loan_officer_tools.get_credit_bureau_service", return_value=mock_bureau
            ),
            patch("src.agents.loan_officer_tools.write_audit_event", new_callable=AsyncMock),
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            result = await lo_pull_credit.ainvoke(
                {"application_id": 101, "pull_type": "hard", "state": _STATE}
            )

        report = mock_session.add.call_args[0][0]
        assert report.pull_type == "hard"
        assert report.trade_lines is not None
        assert len(report.trade_lines) == 1
        assert report.trade_lines[0]["account_type"] == "credit_card"
        assert report.collections_count == 0
        assert report.bankruptcy_flag is False
        days_until_expiry = (report.expires_at - report.pulled_at).days
        assert days_until_expiry == 120

        # Hard pull output includes extra fields
        assert "Trade lines: 1" in result
        assert "Collections: 0" in result
        assert "Bankruptcy flag: False" in result

    @pytest.mark.asyncio
    async def test_invalid_pull_type(self):
        result = await lo_pull_credit.ainvoke(
            {"application_id": 101, "pull_type": "medium", "state": _STATE}
        )
        assert "Invalid pull_type" in result

    @pytest.mark.asyncio
    async def test_no_primary_borrower(self):
        app = _mock_app()
        app.application_borrowers = []

        mock_session_cls, _ = _mock_session_ctx()
        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=app,
            ),
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            result = await lo_pull_credit.ainvoke(
                {"application_id": 101, "pull_type": "soft", "state": _STATE}
            )
        assert "No primary borrower" in result


# ---------------------------------------------------------------------------
# lo_prequalification_check
# ---------------------------------------------------------------------------


class TestLoPrequalificationCheck:
    """Pre-qual check: loads credit report + financials, runs evaluation."""

    @pytest.mark.asyncio
    async def test_passes_bureau_score_not_self_reported(self):
        """The critical behavior: evaluate_prequalification receives the bureau
        credit score from the CreditReport, not the self-reported one."""
        mock_cr = MagicMock()
        mock_cr.credit_score = 742  # bureau score
        mock_cr.pulled_at = datetime(2026, 3, 1, tzinfo=UTC)
        mock_cr.expires_at = datetime(2026, 4, 1, tzinfo=UTC)

        mock_fin = MagicMock()
        mock_fin.gross_monthly_income = Decimal("10000")
        mock_fin.monthly_debts = Decimal("1500")

        mock_session_cls, mock_session = _mock_session_ctx()
        mock_exec_result = MagicMock()
        mock_exec_result.scalar_one_or_none.return_value = mock_cr
        mock_session.execute = AsyncMock(return_value=mock_exec_result)

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=_mock_app(),
            ),
            patch(
                "src.agents.loan_officer_tools.get_financials",
                new_callable=AsyncMock,
                return_value=[mock_fin],
            ),
            patch("src.agents.loan_officer_tools.evaluate_prequalification") as mock_eval,
            patch("src.agents.loan_officer_tools.write_audit_event", new_callable=AsyncMock),
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            # Need mock_eval to return something valid
            mock_eval.return_value = MagicMock(
                eligible_products=[],
                ineligible_products=[],
                recommended_product_id=None,
                summary="No products.",
                dti_ratio=33.0,
                ltv_ratio=75.0,
                down_payment_pct=25.0,
            )
            await lo_prequalification_check.ainvoke({"application_id": 101, "state": _STATE})

        # The key assertion: bureau score (742) was passed, not self-reported
        call_kwargs = mock_eval.call_args.kwargs
        assert call_kwargs["credit_score"] == 742
        assert call_kwargs["gross_monthly_income"] == Decimal("10000")
        assert call_kwargs["monthly_debts"] == Decimal("1500")
        assert call_kwargs["loan_amount"] == 300000  # from _mock_app
        assert call_kwargs["property_value"] == 400000
        assert call_kwargs["loan_type"] == "conventional_30"

    @pytest.mark.asyncio
    async def test_no_credit_pull_on_file(self):
        mock_session_cls, mock_session = _mock_session_ctx()
        mock_exec_result = MagicMock()
        mock_exec_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_exec_result)

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=_mock_app(),
            ),
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            result = await lo_prequalification_check.ainvoke(
                {"application_id": 101, "state": _STATE}
            )

        assert "No soft credit pull on file" in result
        assert "lo_pull_credit" in result

    @pytest.mark.asyncio
    async def test_no_financials(self):
        mock_cr = MagicMock()
        mock_cr.credit_score = 742
        mock_cr.pulled_at = datetime(2026, 3, 1, tzinfo=UTC)
        mock_cr.expires_at = datetime(2026, 4, 1, tzinfo=UTC)

        mock_session_cls, mock_session = _mock_session_ctx()
        mock_exec_result = MagicMock()
        mock_exec_result.scalar_one_or_none.return_value = mock_cr
        mock_session.execute = AsyncMock(return_value=mock_exec_result)

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=_mock_app(),
            ),
            patch(
                "src.agents.loan_officer_tools.get_financials",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            result = await lo_prequalification_check.ainvoke(
                {"application_id": 101, "state": _STATE}
            )

        assert "No financial data" in result

    @pytest.mark.asyncio
    async def test_expired_credit_report_warns(self):
        mock_cr = MagicMock()
        mock_cr.credit_score = 742
        mock_cr.pulled_at = datetime(2026, 1, 1, tzinfo=UTC)
        mock_cr.expires_at = datetime(2026, 1, 31, tzinfo=UTC)  # expired

        mock_fin = MagicMock()
        mock_fin.gross_monthly_income = Decimal("10000")
        mock_fin.monthly_debts = Decimal("1500")

        mock_session_cls, mock_session = _mock_session_ctx()
        mock_exec_result = MagicMock()
        mock_exec_result.scalar_one_or_none.return_value = mock_cr
        mock_session.execute = AsyncMock(return_value=mock_exec_result)

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=_mock_app(),
            ),
            patch(
                "src.agents.loan_officer_tools.get_financials",
                new_callable=AsyncMock,
                return_value=[mock_fin],
            ),
            patch("src.agents.loan_officer_tools.evaluate_prequalification") as mock_eval,
            patch("src.agents.loan_officer_tools.write_audit_event", new_callable=AsyncMock),
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            mock_eval.return_value = MagicMock(
                eligible_products=[],
                ineligible_products=[],
                recommended_product_id=None,
                summary="No products.",
                dti_ratio=50.0,
                ltv_ratio=75.0,
                down_payment_pct=25.0,
            )
            result = await lo_prequalification_check.ainvoke(
                {"application_id": 101, "state": _STATE}
            )

        assert "WARNING" in result
        assert "2026-01-31" in result


# ---------------------------------------------------------------------------
# lo_issue_prequalification
# ---------------------------------------------------------------------------


class TestLoIssuePrequalification:
    """Issue pre-qual: upserts decision, transitions INQUIRY -> PREQUALIFICATION."""

    @pytest.mark.asyncio
    async def test_happy_path_stores_decision_and_transitions(self):
        """Verify the PrequalificationDecision fields, transition target, and audit."""
        mock_cr = MagicMock()
        mock_cr.credit_score = 742

        mock_fin = MagicMock()
        mock_fin.gross_monthly_income = Decimal("10000")
        mock_fin.monthly_debts = Decimal("1500")

        mock_session_cls, mock_session = _mock_session_ctx()
        mock_exec_result = MagicMock()
        mock_exec_result.scalar_one_or_none.return_value = mock_cr
        mock_session.execute = AsyncMock(return_value=mock_exec_result)

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=_mock_app(),
            ),
            patch(
                "src.agents.loan_officer_tools.get_financials",
                new_callable=AsyncMock,
                return_value=[mock_fin],
            ),
            patch(
                "src.agents.loan_officer_tools.transition_stage",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ) as mock_transition,
            patch(
                "src.agents.loan_officer_tools.write_audit_event", new_callable=AsyncMock
            ) as mock_audit,
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            result = await lo_issue_prequalification.ainvoke(
                {
                    "application_id": 101,
                    "product_id": "conventional_30",
                    "max_amount": 350000.0,
                    "state": _STATE,
                }
            )

        # Verify the PrequalificationDecision object
        decision = mock_session.add.call_args[0][0]
        assert decision.application_id == 101
        assert decision.product_id == "conventional_30"
        assert decision.max_loan_amount == Decimal("350000.0")
        assert decision.credit_score_at_decision == 742
        assert decision.issued_by == "lo-james"
        # DTI = 1500/10000 = 0.15
        assert float(decision.dti_at_decision) == 0.15
        # LTV = 300000/400000 = 0.75
        assert float(decision.ltv_at_decision) == 0.75
        # Expires in 90 days
        days_until_expiry = (decision.expires_at - decision.issued_at).days
        assert days_until_expiry == 90

        # Verify transition_stage was called with PREQUALIFICATION
        transition_args = mock_transition.call_args
        assert transition_args.args[3] == ApplicationStage.PREQUALIFICATION

        # Audit records the right event
        assert mock_audit.call_args.kwargs["event_type"] == "prequalification_issued"
        assert mock_audit.call_args.kwargs["event_data"]["product_id"] == "conventional_30"

        assert "Pre-qualification issued" in result
        assert "$350,000.00" in result

    @pytest.mark.asyncio
    async def test_invalid_product_id(self):
        result = await lo_issue_prequalification.ainvoke(
            {
                "application_id": 101,
                "product_id": "nonexistent",
                "max_amount": 300000.0,
                "state": _STATE,
            }
        )
        assert "Invalid product_id" in result

    @pytest.mark.asyncio
    async def test_wrong_stage_rejects(self):
        app = _mock_app(stage=ApplicationStage.APPLICATION)

        mock_session_cls, _ = _mock_session_ctx()
        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=app,
            ),
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            result = await lo_issue_prequalification.ainvoke(
                {
                    "application_id": 101,
                    "product_id": "conventional_30",
                    "max_amount": 300000.0,
                    "state": _STATE,
                }
            )

        assert "application" in result.lower()
        assert "INQUIRY" in result

    @pytest.mark.asyncio
    async def test_no_credit_pull_rejects(self):
        mock_session_cls, mock_session = _mock_session_ctx()
        mock_exec_result = MagicMock()
        mock_exec_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_exec_result)

        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=_mock_app(),
            ),
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            result = await lo_issue_prequalification.ainvoke(
                {
                    "application_id": 101,
                    "product_id": "fha",
                    "max_amount": 250000.0,
                    "state": _STATE,
                }
            )

        assert "No soft credit pull" in result
