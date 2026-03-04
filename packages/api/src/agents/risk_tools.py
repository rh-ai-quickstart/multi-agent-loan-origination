# This project was developed with assistance from AI tools.
"""Risk assessment helpers for underwriting.

Pure functions for computing risk factors from application data.
Called by underwriter_tools.py.
"""

from dataclasses import dataclass

from db.enums import EmploymentStatus


@dataclass
class RiskAssessment:
    """Risk assessment result with typed factor fields."""

    dti: dict[str, float | str | None]
    ltv: dict[str, float | str | None]
    credit: dict[str, int | str | None]
    income_stability: dict[str, str | None]
    asset_sufficiency: dict[str, float | str | None]
    compensating_factors: list[str]
    warnings: list[str]


_RISK_LOW = "Low"
_RISK_MEDIUM = "Medium"
_RISK_HIGH = "High"


def compute_risk_factors(
    app, financials_rows, borrowers, *, bureau_credit_score: int | None = None
) -> RiskAssessment:
    """Compute risk factors from application data.

    Pure function -- no DB access.  Returns a RiskAssessment dataclass with:
      dti, ltv, credit, income_stability, asset_sufficiency,
      compensating_factors, warnings
    Each factor has: value, rating, notes.

    If ``bureau_credit_score`` is provided (from a hard-pull CreditReport),
    it takes precedence over self-reported scores in financials_rows.
    """
    warnings: list[str] = []

    # --- DTI ---
    total_income = sum(float(f.gross_monthly_income or 0) for f in financials_rows)
    total_debts = sum(float(f.monthly_debts or 0) for f in financials_rows)
    if total_income > 0:
        dti_pct = total_debts / total_income * 100
        if dti_pct < 36:
            dti_rating = _RISK_LOW
        elif dti_pct <= 43:
            dti_rating = _RISK_MEDIUM
        else:
            dti_rating = _RISK_HIGH
        dti = {"value": round(dti_pct, 1), "rating": dti_rating}
    else:
        dti = {"value": None, "rating": None}
        warnings.append("Missing income data -- DTI cannot be computed")

    # --- LTV ---
    loan_amount = float(app.loan_amount or 0)
    property_value = float(app.property_value or 0)
    if property_value > 0 and loan_amount > 0:
        ltv_pct = loan_amount / property_value * 100
        if ltv_pct < 60:
            ltv_rating = _RISK_LOW
        elif ltv_pct <= 80:
            ltv_rating = _RISK_MEDIUM
        else:
            ltv_rating = _RISK_HIGH
        ltv = {"value": round(ltv_pct, 1), "rating": ltv_rating}
    else:
        ltv = {"value": None, "rating": None}
        warnings.append("Missing loan amount or property value -- LTV cannot be computed")

    # --- Credit score ---
    # Prefer bureau score from hard-pull CreditReport over self-reported
    if bureau_credit_score is not None:
        min_score = bureau_credit_score
    else:
        credit_scores = [f.credit_score for f in financials_rows if f.credit_score]
        min_score = min(credit_scores) if credit_scores else None

    if min_score is not None:
        if min_score > 680:
            credit_rating = _RISK_LOW
        elif min_score >= 620:
            credit_rating = _RISK_MEDIUM
        else:
            credit_rating = _RISK_HIGH
        credit = {"value": min_score, "rating": credit_rating}
    else:
        credit = {"value": None, "rating": None}
        warnings.append("No credit score on file")

    # --- Income stability ---
    emp_statuses = []
    for b_info in borrowers:
        emp = b_info.get("employment_status")
        if emp:
            emp_statuses.append(emp)

    if emp_statuses:
        stability_map = {
            EmploymentStatus.W2_EMPLOYEE.value: _RISK_LOW,
            EmploymentStatus.RETIRED.value: _RISK_LOW,
            EmploymentStatus.SELF_EMPLOYED.value: _RISK_MEDIUM,
            EmploymentStatus.OTHER.value: _RISK_MEDIUM,
            EmploymentStatus.UNEMPLOYED.value: _RISK_HIGH,
        }
        ratings = [stability_map.get(e, _RISK_MEDIUM) for e in emp_statuses]
        risk_order = {_RISK_LOW: 0, _RISK_MEDIUM: 1, _RISK_HIGH: 2}
        worst_rating = max(ratings, key=lambda r: risk_order.get(r, 1))
        income_stability = {"value": ", ".join(emp_statuses), "rating": worst_rating}
    else:
        income_stability = {"value": None, "rating": None}
        warnings.append("No employment status on file")

    # --- Asset sufficiency ---
    total_assets = sum(float(f.total_assets or 0) for f in financials_rows)
    if loan_amount > 0 and total_assets > 0:
        asset_ratio = total_assets / loan_amount * 100
        if asset_ratio > 20:
            asset_rating = _RISK_LOW
        elif asset_ratio >= 10:
            asset_rating = _RISK_MEDIUM
        else:
            asset_rating = _RISK_HIGH
        asset_sufficiency = {"value": round(asset_ratio, 1), "rating": asset_rating}
    else:
        asset_sufficiency = {"value": None, "rating": None}
        if total_assets == 0:
            warnings.append("No asset data on file")

    # --- Compensating factors ---
    comp_factors: list[str] = []
    if credit.get("value") and credit["value"] > 740 and dti.get("rating") == _RISK_HIGH:
        comp_factors.append("Strong credit (>740) offsets elevated DTI")
    if ltv.get("value") and ltv["value"] < 60 and credit.get("rating") == _RISK_HIGH:
        comp_factors.append("Low LTV (<60%) offsets weak credit")
    if asset_sufficiency.get("value") and asset_sufficiency["value"] > 50:
        comp_factors.append("High reserves (>50% of loan amount)")

    return RiskAssessment(
        dti=dti,
        ltv=ltv,
        credit=credit,
        income_stability=income_stability,
        asset_sufficiency=asset_sufficiency,
        compensating_factors=comp_factors,
        warnings=warnings,
    )


def extract_borrower_info(app) -> list[dict]:
    """Extract borrower employment info from an application's borrowers."""
    borrowers = []
    for ab in app.application_borrowers or []:
        if ab.borrower:
            b = ab.borrower
            emp = (
                b.employment_status.value
                if b.employment_status and hasattr(b.employment_status, "value")
                else str(b.employment_status)
                if b.employment_status
                else None
            )
            borrowers.append(
                {
                    "name": f"{b.first_name} {b.last_name}",
                    "is_primary": ab.is_primary,
                    "employment_status": emp,
                }
            )
    return borrowers
