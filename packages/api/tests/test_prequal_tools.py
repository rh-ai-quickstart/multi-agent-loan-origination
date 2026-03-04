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
from src.schemas.credit import SoftPullResult
from src.services.prequalification import PrequalificationResult, ProductPrequalResult

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
    async def test_soft_pull_stores_report_and_audits(self):
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

        assert "742" in result
        assert "Sarah Mitchell" in result
        assert "mock_equifax" in result
        mock_session.add.assert_called_once()
        mock_audit.assert_awaited_once()
        assert mock_audit.call_args.kwargs["event_type"] == "credit_pull"
        assert mock_audit.call_args.kwargs["event_data"]["pull_type"] == "soft"

    @pytest.mark.asyncio
    async def test_invalid_pull_type(self):
        result = await lo_pull_credit.ainvoke(
            {"application_id": 101, "pull_type": "medium", "state": _STATE}
        )
        assert "Invalid pull_type" in result

    @pytest.mark.asyncio
    async def test_app_not_found(self):
        mock_session_cls, _ = _mock_session_ctx()
        with (
            patch(
                "src.agents.loan_officer_tools.get_application",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            result = await lo_pull_credit.ainvoke(
                {"application_id": 999, "pull_type": "soft", "state": _STATE}
            )
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_no_primary_borrower(self):
        app = _mock_app()
        app.application_borrowers = []  # no borrowers

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
    async def test_happy_path_formats_results(self):
        mock_cr = MagicMock()
        mock_cr.credit_score = 742
        mock_cr.pulled_at = datetime(2026, 3, 1, tzinfo=UTC)
        mock_cr.expires_at = datetime(2026, 4, 1, tzinfo=UTC)

        mock_fin = MagicMock()
        mock_fin.gross_monthly_income = Decimal("10000")
        mock_fin.monthly_debts = Decimal("1500")

        prequal_result = PrequalificationResult(
            eligible_products=[
                ProductPrequalResult(
                    product_id="conventional_30",
                    product_name="30-Year Fixed Conventional",
                    is_eligible=True,
                    max_loan_amount=388000.0,
                    estimated_monthly_payment=1896.20,
                    estimated_rate=6.5,
                    ineligibility_reasons=[],
                )
            ],
            ineligible_products=[],
            recommended_product_id="conventional_30",
            summary="Pre-qualified for 1 product(s).",
            dti_ratio=33.96,
            ltv_ratio=75.0,
            down_payment_pct=25.0,
        )

        mock_session_cls, mock_session = _mock_session_ctx()
        # Mock session.execute for the CreditReport query
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
                "src.agents.loan_officer_tools.evaluate_prequalification",
                return_value=prequal_result,
            ),
            patch(
                "src.agents.loan_officer_tools.write_audit_event", new_callable=AsyncMock
            ) as mock_audit,
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            result = await lo_prequalification_check.ainvoke(
                {"application_id": 101, "state": _STATE}
            )

        assert "742" in result
        assert "ELIGIBLE (1)" in result
        assert "30-Year Fixed Conventional" in result
        assert "RECOMMENDED" in result
        assert "prequalification_reviewed" == mock_audit.call_args.kwargs["event_type"]

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

        prequal_result = PrequalificationResult(
            eligible_products=[],
            ineligible_products=[],
            recommended_product_id=None,
            summary="No products eligible.",
            dti_ratio=50.0,
            ltv_ratio=75.0,
            down_payment_pct=25.0,
        )

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
                "src.agents.loan_officer_tools.evaluate_prequalification",
                return_value=prequal_result,
            ),
            patch("src.agents.loan_officer_tools.write_audit_event", new_callable=AsyncMock),
            patch("src.agents.loan_officer_tools.SessionLocal", mock_session_cls),
        ):
            result = await lo_prequalification_check.ainvoke(
                {"application_id": 101, "state": _STATE}
            )

        assert "WARNING" in result
        assert "expired" in result.lower()


# ---------------------------------------------------------------------------
# lo_issue_prequalification
# ---------------------------------------------------------------------------


class TestLoIssuePrequalification:
    """Issue pre-qual: upserts decision, transitions INQUIRY -> PREQUALIFICATION."""

    @pytest.mark.asyncio
    async def test_happy_path_issues_and_transitions(self):
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
            ),
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

        assert "Pre-qualification issued" in result
        assert "30-Year Fixed Conventional" in result
        assert "$350,000.00" in result
        assert "PREQUALIFICATION" in result
        mock_session.add.assert_called_once()
        assert mock_audit.call_args.kwargs["event_type"] == "prequalification_issued"

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
