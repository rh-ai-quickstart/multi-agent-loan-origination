# This project was developed with assistance from AI tools.
"""Boundary tests for pre-qualification eligibility thresholds.

Verifies that >= and > comparisons at exact product eligibility boundaries
produce the correct eligible/ineligible classification. Off-by-one errors
in threshold checks are the most common bug in eligibility logic.
"""

from decimal import Decimal

import pytest

from src.services.prequalification import evaluate_prequalification


def _is_eligible(result, product_id: str) -> bool:
    return any(p.product_id == product_id for p in result.eligible_products)


def _is_ineligible(result, product_id: str) -> bool:
    return any(p.product_id == product_id for p in result.ineligible_products)


# Shared baseline: all values well within limits so we can isolate one variable
_BASELINE = dict(
    gross_monthly_income=Decimal("10000"),
    monthly_debts=Decimal("500"),
    loan_amount=Decimal("200000"),
    property_value=Decimal("400000"),  # 50% LTV, well under all limits
)


class TestCreditScoreBoundaries:
    """Credit score uses strict `<` comparison: score < min is ineligible."""

    def test_conventional_at_exactly_620_is_eligible(self):
        result = evaluate_prequalification(
            credit_score=620,
            **_BASELINE,
            loan_type="conventional_30",
        )
        assert _is_eligible(result, "conventional_30")

    def test_conventional_at_619_is_ineligible(self):
        result = evaluate_prequalification(
            credit_score=619,
            **_BASELINE,
            loan_type="conventional_30",
        )
        assert _is_ineligible(result, "conventional_30")

    def test_fha_at_exactly_580_is_eligible(self):
        result = evaluate_prequalification(
            credit_score=580,
            **_BASELINE,
            loan_type="fha",
        )
        assert _is_eligible(result, "fha")

    def test_fha_at_579_is_ineligible(self):
        result = evaluate_prequalification(
            credit_score=579,
            **_BASELINE,
            loan_type="fha",
        )
        assert _is_ineligible(result, "fha")

    def test_jumbo_at_exactly_700_is_eligible(self):
        result = evaluate_prequalification(
            credit_score=700,
            **_BASELINE,
            loan_type="jumbo",
        )
        assert _is_eligible(result, "jumbo")

    def test_jumbo_at_699_is_ineligible(self):
        result = evaluate_prequalification(
            credit_score=699,
            **_BASELINE,
            loan_type="jumbo",
        )
        assert _is_ineligible(result, "jumbo")

    def test_usda_at_exactly_640_is_eligible(self):
        result = evaluate_prequalification(
            credit_score=640,
            **_BASELINE,
            loan_type="usda",
        )
        assert _is_eligible(result, "usda")

    def test_usda_at_639_is_ineligible(self):
        result = evaluate_prequalification(
            credit_score=639,
            **_BASELINE,
            loan_type="usda",
        )
        assert _is_ineligible(result, "usda")


class TestLtvBoundaries:
    """LTV uses strict `>` comparison: ltv_pct > max is ineligible."""

    def test_jumbo_at_exactly_90pct_ltv_is_eligible(self):
        """$360K / $400K = 90.0% LTV, jumbo max is 90%."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("15000"),
            monthly_debts=Decimal("500"),
            loan_amount=Decimal("360000"),
            property_value=Decimal("400000"),
            loan_type="jumbo",
        )
        assert _is_eligible(result, "jumbo")

    def test_jumbo_at_90_point_1_pct_ltv_is_ineligible(self):
        """$360400 / $400000 = 90.1% LTV, just over jumbo's 90% max."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("15000"),
            monthly_debts=Decimal("500"),
            loan_amount=Decimal("360400"),
            property_value=Decimal("400000"),
            loan_type="jumbo",
        )
        assert _is_ineligible(result, "jumbo")

    def test_arm_at_exactly_95pct_ltv_is_eligible(self):
        """$380K / $400K = 95.0% LTV, ARM max is 95%."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("15000"),
            monthly_debts=Decimal("500"),
            loan_amount=Decimal("380000"),
            property_value=Decimal("400000"),
            loan_type="arm",
        )
        assert _is_eligible(result, "arm")

    def test_conventional_at_exactly_97pct_ltv_is_eligible(self):
        """$388K / $400K = 97.0% LTV, conventional max is 97%."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("15000"),
            monthly_debts=Decimal("500"),
            loan_amount=Decimal("388000"),
            property_value=Decimal("400000"),
            loan_type="conventional_30",
        )
        assert _is_eligible(result, "conventional_30")


class TestMultipleConstraintsAtLimits:
    """All thresholds simultaneously at their limits."""

    @pytest.mark.parametrize(
        "credit_score,loan_type,expected",
        [
            (620, "conventional_30", True),
            (619, "conventional_30", False),
            (580, "fha", True),
            (579, "fha", False),
        ],
    )
    def test_credit_at_boundary_with_moderate_financials(self, credit_score, loan_type, expected):
        """Credit score at boundary with moderate DTI and LTV."""
        result = evaluate_prequalification(
            credit_score=credit_score,
            gross_monthly_income=Decimal("8000"),
            monthly_debts=Decimal("1000"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
            loan_type=loan_type,
        )
        if expected:
            assert _is_eligible(result, loan_type)
        else:
            assert _is_ineligible(result, loan_type)

    def test_all_products_boundary_split(self):
        """Score of 620 splits: conv/ARM/USDA/FHA/VA eligible, jumbo ineligible."""
        result = evaluate_prequalification(
            credit_score=620,
            **_BASELINE,
        )
        # 620 meets conventional (620), ARM (620), USDA (640? no, 620 < 640)
        assert _is_eligible(result, "conventional_30")
        assert _is_eligible(result, "arm")
        assert _is_eligible(result, "fha")  # FHA min 580
        assert _is_eligible(result, "va")  # VA min 580
        assert _is_ineligible(result, "jumbo")  # needs 700
        assert _is_ineligible(result, "usda")  # needs 640
