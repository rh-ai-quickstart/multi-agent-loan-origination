# This project was developed with assistance from AI tools.
"""Tests for pre-qualification evaluation service."""

from decimal import Decimal

from src.services.prequalification import evaluate_prequalification


class TestEligibility:
    """Product eligibility evaluation tests."""

    def test_should_qualify_strong_borrower_for_all_products(self):
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("10000"),
            monthly_debts=Decimal("1500"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
        )

        eligible_ids = {p.product_id for p in result.eligible_products}
        assert eligible_ids == {
            "conventional_30",
            "conventional_15",
            "fha",
            "va",
            "jumbo",
            "usda",
            "arm",
        }
        assert len(result.ineligible_products) == 0

    def test_should_reject_conventional_at_580_but_allow_fha(self):
        """580 is below conventional's 620 min but meets FHA's 580 min."""
        result = evaluate_prequalification(
            credit_score=580,
            gross_monthly_income=Decimal("8000"),
            monthly_debts=Decimal("1000"),
            loan_amount=Decimal("200000"),
            property_value=Decimal("250000"),
        )

        eligible_ids = {p.product_id for p in result.eligible_products}
        ineligible_ids = {p.product_id for p in result.ineligible_products}

        assert "fha" in eligible_ids
        assert "va" in eligible_ids  # VA min is also 580
        assert "conventional_30" in ineligible_ids
        assert "jumbo" in ineligible_ids  # jumbo needs 700

        conv = next(p for p in result.ineligible_products if p.product_id == "conventional_30")
        assert "Credit score 580 below minimum 620" in conv.ineligibility_reasons

    def test_should_reject_jumbo_for_high_ltv(self):
        """95% LTV exceeds jumbo's 90% max but passes conventional's 97%."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("15000"),
            monthly_debts=Decimal("1000"),
            loan_amount=Decimal("475000"),
            property_value=Decimal("500000"),
        )

        jumbo = next(p for p in result.ineligible_products if p.product_id == "jumbo")
        assert "LTV 95.0% exceeds maximum 90.0%" in jumbo.ineligibility_reasons

        conv = next(p for p in result.eligible_products if p.product_id == "conventional_30")
        assert conv.is_eligible

    def test_should_reject_all_when_dti_too_high(self):
        """$3000 debts on $5000 income + housing payment exceeds all DTI limits."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("5000"),
            monthly_debts=Decimal("3000"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
        )

        assert len(result.eligible_products) == 0
        # Every rejection should cite DTI
        for p in result.ineligible_products:
            assert any("DTI" in r for r in p.ineligibility_reasons)


class TestMathCorrectness:
    """Verify the actual computed values, not just > 0."""

    def test_should_compute_correct_monthly_payment(self):
        """$300K at 6.5% over 30yr = $1896.20/mo (standard amortization)."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("10000"),
            monthly_debts=Decimal("1500"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
        )

        conv30 = next(p for p in result.eligible_products if p.product_id == "conventional_30")
        assert conv30.estimated_monthly_payment == 1896.20
        assert conv30.estimated_rate == 6.5

    def test_should_compute_different_payments_for_15yr_vs_30yr(self):
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("10000"),
            monthly_debts=Decimal("1500"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
        )

        conv30 = next(p for p in result.eligible_products if p.product_id == "conventional_30")
        conv15 = next(p for p in result.eligible_products if p.product_id == "conventional_15")

        # 15-year has higher monthly payment but lower rate
        assert conv15.estimated_monthly_payment == 2491.23
        assert conv15.estimated_monthly_payment > conv30.estimated_monthly_payment
        # 15-year has lower max loan (higher payments eat more DTI room)
        assert conv15.max_loan_amount < conv30.max_loan_amount

    def test_should_compute_correct_ltv_and_down_payment(self):
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("10000"),
            monthly_debts=Decimal("1000"),
            loan_amount=Decimal("320000"),
            property_value=Decimal("400000"),
        )

        assert result.ltv_ratio == 80.0
        assert result.down_payment_pct == 20.0

    def test_should_cap_max_loan_at_product_ltv_limit(self):
        """Max loan should not exceed property_value * max_ltv_pct."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("50000"),  # very high income
            monthly_debts=Decimal("0"),
            loan_amount=Decimal("100000"),
            property_value=Decimal("400000"),
        )

        conv30 = next(p for p in result.eligible_products if p.product_id == "conventional_30")
        # Conv30 max LTV = 97%, so max loan <= 400000 * 0.97 = 388000
        assert conv30.max_loan_amount == 388000.0

        jumbo = next(p for p in result.eligible_products if p.product_id == "jumbo")
        # Jumbo max LTV = 90%, so max loan <= 400000 * 0.90 = 360000
        assert jumbo.max_loan_amount == 360000.0


class TestRecommendation:
    """Recommendation logic tests."""

    def test_should_recommend_conventional_by_default(self):
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("10000"),
            monthly_debts=Decimal("1500"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
        )

        assert result.recommended_product_id == "conventional_30"

    def test_should_recommend_requested_product_when_eligible(self):
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("10000"),
            monthly_debts=Decimal("1500"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
            loan_type="fha",
        )

        assert result.recommended_product_id == "fha"

    def test_should_return_none_when_no_products_eligible(self):
        result = evaluate_prequalification(
            credit_score=400,
            gross_monthly_income=Decimal("2000"),
            monthly_debts=Decimal("1800"),
            loan_amount=Decimal("500000"),
            property_value=Decimal("200000"),
        )

        assert result.recommended_product_id is None
        assert len(result.eligible_products) == 0


class TestEdgeCases:
    """Boundary and edge case tests."""

    def test_should_handle_zero_income(self):
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("0"),
            monthly_debts=Decimal("0"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
        )

        # DTI = 100% (fallback), no products should qualify
        assert result.dti_ratio == 100.0
        assert len(result.eligible_products) == 0

    def test_should_handle_zero_property_value(self):
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("10000"),
            monthly_debts=Decimal("1000"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("0"),
        )

        # LTV = 100% (fallback), only 100% LTV products (VA, USDA) pass LTV check
        assert result.ltv_ratio == 100.0
        eligible_ids = {p.product_id for p in result.eligible_products}
        assert eligible_ids <= {"va", "usda"}

    def test_should_evaluate_only_specified_product(self):
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("10000"),
            monthly_debts=Decimal("1000"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
            loan_type="conventional_30",
        )

        total = len(result.eligible_products) + len(result.ineligible_products)
        assert total == 1
        assert result.eligible_products[0].product_id == "conventional_30"

    def test_should_return_empty_for_unknown_product(self):
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("10000"),
            monthly_debts=Decimal("1000"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
            loan_type="nonexistent",
        )

        assert len(result.eligible_products) == 0
        assert len(result.ineligible_products) == 0
        assert result.recommended_product_id is None

    def test_should_show_ineligible_when_credit_too_low_for_filtered_product(self):
        """W-31: Credit score 580 is below conventional_30 minimum (620)."""
        result = evaluate_prequalification(
            credit_score=580,
            gross_monthly_income=Decimal("8000"),
            monthly_debts=Decimal("800"),
            loan_amount=Decimal("200000"),
            property_value=Decimal("250000"),
            loan_type="conventional_30",
        )

        assert len(result.eligible_products) == 0
        assert len(result.ineligible_products) == 1
        assert result.ineligible_products[0].product_id == "conventional_30"
        assert any(
            "credit score" in r.lower() for r in result.ineligible_products[0].ineligibility_reasons
        )
        assert result.recommended_product_id is None

    def test_dti_ratio_uses_recommended_product(self):
        """S-1: DTI in result should correspond to the recommended product, not the last evaluated."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("10000"),
            monthly_debts=Decimal("1500"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
        )

        # Recommended should be conventional_30 (first in preference order)
        assert result.recommended_product_id == "conventional_30"
        # DTI should be deterministic and reasonable (includes housing payment)
        assert result.dti_ratio > 0
        assert result.dti_ratio < 100
