# This project was developed with assistance from AI tools.
"""Pre-qualification evaluation service.

Pure function, no DB access. Evaluates borrower financials + credit score
against product eligibility rules and returns per-product results.

Simulated for demonstration purposes -- not real financial advice.
"""

from decimal import Decimal

from pydantic import BaseModel

from .calculator import compute_monthly_payment
from .products import PRODUCTS

# Default term months per product for payment calculation
_TERM_MONTHS: dict[str, int] = {
    "conventional_30": 360,
    "conventional_15": 180,
    "fha": 360,
    "va": 360,
    "jumbo": 360,
    "usda": 360,
    "arm": 360,
}


class ProductPrequalResult(BaseModel):
    """Pre-qualification result for a single product."""

    product_id: str
    product_name: str
    is_eligible: bool
    max_loan_amount: float
    estimated_monthly_payment: float
    estimated_rate: float
    ineligibility_reasons: list[str]


class PrequalificationResult(BaseModel):
    """Complete pre-qualification evaluation across all products."""

    eligible_products: list[ProductPrequalResult]
    ineligible_products: list[ProductPrequalResult]
    recommended_product_id: str | None
    summary: str
    dti_ratio: float
    ltv_ratio: float
    down_payment_pct: float


# Product preference order for recommendation (lower index = preferred)
_PREFERENCE_ORDER = [
    "conventional_30",
    "conventional_15",
    "fha",
    "va",
    "usda",
    "arm",
    "jumbo",
]


def evaluate_prequalification(
    credit_score: int,
    gross_monthly_income: Decimal,
    monthly_debts: Decimal,
    loan_amount: Decimal,
    property_value: Decimal,
    loan_type: str | None = None,
) -> PrequalificationResult:
    """Evaluate pre-qualification eligibility across mortgage products.

    Args:
        credit_score: Bureau or self-reported credit score (300-850).
        gross_monthly_income: Gross monthly income in dollars.
        monthly_debts: Total monthly debt obligations (non-housing).
        loan_amount: Requested loan amount.
        property_value: Property value / purchase price.
        loan_type: If set, only evaluate this product. Otherwise evaluate all.

    Returns:
        PrequalificationResult with per-product eligibility and recommendation.
    """
    ltv_ratio = float(loan_amount / property_value) if property_value > 0 else 1.0
    ltv_pct = ltv_ratio * 100.0
    down_payment_pct = (1.0 - ltv_ratio) * 100.0

    products_to_evaluate = PRODUCTS
    if loan_type:
        products_to_evaluate = [p for p in PRODUCTS if p.id == loan_type]

    eligible: list[ProductPrequalResult] = []
    ineligible: list[ProductPrequalResult] = []
    product_dti: dict[str, float] = {}  # product_id -> DTI% for deterministic lookup

    for product in products_to_evaluate:
        elig = product.eligibility
        reasons: list[str] = []

        if credit_score < elig.min_credit_score:
            reasons.append(f"Credit score {credit_score} below minimum {elig.min_credit_score}")

        if ltv_pct > elig.max_ltv_pct:
            reasons.append(f"LTV {ltv_pct:.1f}% exceeds maximum {elig.max_ltv_pct:.1f}%")

        term_months = _TERM_MONTHS.get(product.id, 360)
        monthly_payment = compute_monthly_payment(
            float(loan_amount),
            product.typical_rate,
            term_months,
        )

        total_monthly_obligations = float(monthly_debts) + monthly_payment
        dti = (
            total_monthly_obligations / float(gross_monthly_income)
            if float(gross_monthly_income) > 0
            else 1.0
        )
        dti_pct = dti * 100.0
        product_dti[product.id] = dti_pct

        if dti_pct > elig.max_dti_pct:
            reasons.append(f"DTI {dti_pct:.1f}% exceeds maximum {elig.max_dti_pct:.1f}%")

        if reasons:
            ineligible.append(
                ProductPrequalResult(
                    product_id=product.id,
                    product_name=product.name,
                    is_eligible=False,
                    max_loan_amount=0,
                    estimated_monthly_payment=0,
                    estimated_rate=product.typical_rate,
                    ineligibility_reasons=reasons,
                )
            )
        else:
            # Compute max affordable loan for this product
            max_housing = float(gross_monthly_income) * (elig.max_dti_pct / 100.0) - float(
                monthly_debts
            )
            if max_housing > 0:
                monthly_rate = product.typical_rate / 100.0 / 12.0
                if monthly_rate > 0:
                    compound = (1 + monthly_rate) ** term_months
                    pmt_per_dollar = monthly_rate * compound / (compound - 1)
                else:
                    pmt_per_dollar = 1.0 / term_months
                computed_max = max_housing / pmt_per_dollar
                # Cap at the property value * max LTV
                max_by_ltv = float(property_value) * (elig.max_ltv_pct / 100.0)
                max_loan = min(computed_max, max_by_ltv)
            else:
                max_loan = 0

            eligible.append(
                ProductPrequalResult(
                    product_id=product.id,
                    product_name=product.name,
                    is_eligible=True,
                    max_loan_amount=round(max_loan, 2),
                    estimated_monthly_payment=round(monthly_payment, 2),
                    estimated_rate=product.typical_rate,
                    ineligibility_reasons=[],
                )
            )

    # Pick recommendation
    recommended = None
    if eligible:
        if loan_type:
            recommended = eligible[0].product_id
        else:
            for pref in _PREFERENCE_ORDER:
                for e in eligible:
                    if e.product_id == pref:
                        recommended = pref
                        break
                if recommended:
                    break
            if not recommended:
                recommended = eligible[0].product_id

    # Use the recommended product's DTI (or first evaluated if none eligible)
    if recommended and recommended in product_dti:
        final_dti_pct = product_dti[recommended]
    elif product_dti:
        final_dti_pct = next(iter(product_dti.values()))
    else:
        final_dti_pct = 0.0

    # Build summary
    if not eligible:
        summary = (
            f"Based on a credit score of {credit_score}, DTI of {final_dti_pct:.1f}%, "
            f"and LTV of {ltv_pct:.1f}%, no products currently meet eligibility "
            "requirements. Consider reducing the loan amount, paying down debts, "
            "or improving credit score."
        )
    else:
        rec_name = next((e.product_name for e in eligible if e.product_id == recommended), "")
        rec_max = next((e.max_loan_amount for e in eligible if e.product_id == recommended), 0)
        summary = (
            f"Pre-qualified for {len(eligible)} product(s). "
            f"Recommended: {rec_name} with max loan amount "
            f"${rec_max:,.2f}."
        )

    return PrequalificationResult(
        eligible_products=eligible,
        ineligible_products=ineligible,
        recommended_product_id=recommended,
        summary=summary,
        dti_ratio=round(final_dti_pct, 2),
        ltv_ratio=round(ltv_pct, 2),
        down_payment_pct=round(down_payment_pct, 2),
    )
