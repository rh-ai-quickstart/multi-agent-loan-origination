# This project was developed with assistance from AI tools.
"""Tests for the borrower prequalification_estimate tool."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db.enums import LoanType

from src.agents.borrower_tools import prequalification_estimate


def _state(user_id="borrower-sarah"):
    return {"user_id": user_id, "user_role": "borrower"}


def _make_app(*, loan_amount=350000, property_value=450000, loan_type=LoanType.CONVENTIONAL_30):
    app = MagicMock()
    app.loan_amount = loan_amount
    app.property_value = property_value
    app.loan_type = loan_type
    return app


def _make_fin(*, credit_score=720, income=8000, debts=1200, assets=60000):
    fin = MagicMock()
    fin.credit_score = credit_score
    fin.gross_monthly_income = Decimal(str(income))
    fin.monthly_debts = Decimal(str(debts))
    fin.total_assets = Decimal(str(assets))
    return fin


class TestPrequalificationEstimate:
    """Tests for prequalification_estimate tool."""

    @pytest.mark.asyncio
    async def test_not_found_returns_error(self):
        """Application not found or no access returns error."""
        with (
            patch(
                "src.agents.borrower_tools.app_service.get_application",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("src.agents.borrower_tools.SessionLocal") as mock_cls,
        ):
            mock_session = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await prequalification_estimate.ainvoke(
                {"application_id": 1, "state": _state()}
            )

        assert "not found" in result

    @pytest.mark.asyncio
    async def test_no_financials_asks_for_info(self):
        """Missing financials prompts borrower for data."""
        app = _make_app()
        with (
            patch(
                "src.agents.borrower_tools.app_service.get_application",
                new_callable=AsyncMock,
                return_value=app,
            ),
            patch(
                "src.agents.borrower_tools.app_service.get_financials",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("src.agents.borrower_tools.SessionLocal") as mock_cls,
        ):
            mock_session = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await prequalification_estimate.ainvoke(
                {"application_id": 1, "state": _state()}
            )

        assert "financial information" in result.lower()

    @pytest.mark.asyncio
    async def test_missing_credit_score_lists_needed_fields(self):
        """Partial financials lists what's still needed."""
        app = _make_app()
        fin = _make_fin()
        fin.credit_score = None

        with (
            patch(
                "src.agents.borrower_tools.app_service.get_application",
                new_callable=AsyncMock,
                return_value=app,
            ),
            patch(
                "src.agents.borrower_tools.app_service.get_financials",
                new_callable=AsyncMock,
                return_value=[fin],
            ),
            patch("src.agents.borrower_tools.SessionLocal") as mock_cls,
        ):
            mock_session = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await prequalification_estimate.ainvoke(
                {"application_id": 1, "state": _state()}
            )

        assert "credit score" in result

    @pytest.mark.asyncio
    async def test_happy_path_shows_eligible_products(self):
        """Complete financials produce an estimate with eligible products."""
        app = _make_app()
        fin = _make_fin()

        with (
            patch(
                "src.agents.borrower_tools.app_service.get_application",
                new_callable=AsyncMock,
                return_value=app,
            ),
            patch(
                "src.agents.borrower_tools.app_service.get_financials",
                new_callable=AsyncMock,
                return_value=[fin],
            ),
            patch("src.agents.borrower_tools.SessionLocal") as mock_cls,
            patch(
                "src.agents.borrower_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
        ):
            mock_session = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await prequalification_estimate.ainvoke(
                {"application_id": 1, "state": _state()}
            )

        assert "Preliminary Pre-Qualification Estimate" in result
        assert "Eligible Products" in result
        assert "preliminary estimate" in result.lower()
        assert "DTI Ratio" in result
        assert "LTV Ratio" in result

    @pytest.mark.asyncio
    async def test_passes_self_reported_data_to_evaluator(self):
        """Verify evaluate_prequalification receives the borrower's self-reported values."""
        app = _make_app(loan_amount=300000, property_value=400000)
        fin = _make_fin(credit_score=680, income=7000, debts=1000)

        with (
            patch(
                "src.agents.borrower_tools.app_service.get_application",
                new_callable=AsyncMock,
                return_value=app,
            ),
            patch(
                "src.agents.borrower_tools.app_service.get_financials",
                new_callable=AsyncMock,
                return_value=[fin],
            ),
            patch("src.agents.borrower_tools.SessionLocal") as mock_cls,
            patch(
                "src.agents.borrower_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.services.prequalification.evaluate_prequalification") as mock_eval,
        ):
            # Return a real-looking result from the mock
            mock_result = MagicMock()
            mock_result.eligible_products = []
            mock_result.ineligible_products = []
            mock_result.recommended_product_id = None
            mock_result.summary = "No products eligible."
            mock_result.dti_ratio = 14.3
            mock_result.ltv_ratio = 75.0
            mock_result.down_payment_pct = 25.0
            mock_eval.return_value = mock_result

            mock_session = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await prequalification_estimate.ainvoke({"application_id": 1, "state": _state()})

        mock_eval.assert_called_once_with(
            credit_score=680,
            gross_monthly_income=Decimal("7000"),
            monthly_debts=Decimal("1000"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
            loan_type="conventional_30",
        )

    @pytest.mark.asyncio
    async def test_writes_audit_event(self):
        """Audit event logged with eligible count and recommendation."""
        app = _make_app()
        fin = _make_fin()

        with (
            patch(
                "src.agents.borrower_tools.app_service.get_application",
                new_callable=AsyncMock,
                return_value=app,
            ),
            patch(
                "src.agents.borrower_tools.app_service.get_financials",
                new_callable=AsyncMock,
                return_value=[fin],
            ),
            patch("src.agents.borrower_tools.SessionLocal") as mock_cls,
            patch(
                "src.agents.borrower_tools.write_audit_event",
                new_callable=AsyncMock,
            ) as mock_audit,
        ):
            mock_session = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await prequalification_estimate.ainvoke({"application_id": 1, "state": _state()})

        mock_audit.assert_awaited_once()
        audit_data = mock_audit.call_args.kwargs["event_data"]
        assert "eligible_count" in audit_data
        assert "recommended" in audit_data
        assert mock_audit.call_args.kwargs["event_type"] == "prequalification_estimate_viewed"

    @pytest.mark.asyncio
    async def test_disclaimer_present(self):
        """Output includes the preliminary estimate disclaimer."""
        app = _make_app()
        fin = _make_fin()

        with (
            patch(
                "src.agents.borrower_tools.app_service.get_application",
                new_callable=AsyncMock,
                return_value=app,
            ),
            patch(
                "src.agents.borrower_tools.app_service.get_financials",
                new_callable=AsyncMock,
                return_value=[fin],
            ),
            patch("src.agents.borrower_tools.SessionLocal") as mock_cls,
            patch(
                "src.agents.borrower_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
        ):
            mock_session = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await prequalification_estimate.ainvoke(
                {"application_id": 1, "state": _state()}
            )

        assert "loan officer will review" in result.lower()
        assert "credit check" in result.lower()

    @pytest.mark.asyncio
    async def test_no_loan_type_passes_none(self):
        """When application has no loan_type, evaluator receives loan_type=None."""
        app = _make_app()
        app.loan_type = None
        fin = _make_fin()

        with (
            patch(
                "src.agents.borrower_tools.app_service.get_application",
                new_callable=AsyncMock,
                return_value=app,
            ),
            patch(
                "src.agents.borrower_tools.app_service.get_financials",
                new_callable=AsyncMock,
                return_value=[fin],
            ),
            patch("src.agents.borrower_tools.SessionLocal") as mock_cls,
            patch(
                "src.agents.borrower_tools.write_audit_event",
                new_callable=AsyncMock,
            ),
            patch("src.services.prequalification.evaluate_prequalification") as mock_eval,
        ):
            mock_result = MagicMock()
            mock_result.eligible_products = []
            mock_result.ineligible_products = []
            mock_result.recommended_product_id = None
            mock_result.summary = "No eligible products."
            mock_result.dti_ratio = 15.0
            mock_result.ltv_ratio = 77.8
            mock_result.down_payment_pct = 22.2
            mock_eval.return_value = mock_result

            mock_session = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await prequalification_estimate.ainvoke({"application_id": 1, "state": _state()})

        assert mock_eval.call_args.kwargs["loan_type"] is None
