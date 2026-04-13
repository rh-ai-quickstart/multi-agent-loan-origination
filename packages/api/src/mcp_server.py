# This project was developed with assistance from AI tools.
"""MCP server exposing risk assessment tools over Streamable HTTP.

Six pure-computation tools for mortgage risk assessment, designed to be
called by the underwriter LangGraph agent via langchain-mcp-adapters.
No database access -- all inputs are simple primitives passed by the LLM.
"""

import json

from mcp.server.fastmcp import FastMCP

from .agents.risk_tools import (
    _RISK_HIGH,
    _RISK_LOW,
    _RISK_MEDIUM,
    Recommendation,
    RiskAssessment,
    compute_recommendation,
)

mcp = FastMCP("risk-assessment", host="0.0.0.0", port=8081)


# Health endpoint for K8s probes (MCP's /mcp only accepts POST, returns 406 on GET)
@mcp.custom_route("/health", methods=["GET"])
async def health(request):  # noqa: ARG001
    """Liveness/readiness probe for K8s."""
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "healthy"})


# Threshold constants (mirrored from risk_tools.py for tool descriptions)
_DTI_LOW = 36
_DTI_MEDIUM = 43
_LTV_LOW = 60
_LTV_MEDIUM = 80
_CREDIT_LOW = 680
_CREDIT_MEDIUM = 620
_ASSET_LOW = 20
_ASSET_MEDIUM = 10


@mcp.tool()
def calculate_dti(monthly_income: float, monthly_debts: float) -> str:
    """Calculate Debt-to-Income ratio and risk rating.

    DTI = monthly_debts / monthly_income * 100.
    Ratings: <36% Low, 36-43% Medium, >43% High.
    """
    if monthly_income <= 0:
        return json.dumps(
            {
                "value": None,
                "rating": None,
                "warning": "Missing or zero income -- DTI cannot be computed",
            }
        )

    dti_pct = round(monthly_debts / monthly_income * 100, 1)
    if dti_pct < _DTI_LOW:
        rating = _RISK_LOW
        guidance = "Well within conventional guidelines"
    elif dti_pct <= _DTI_MEDIUM:
        rating = _RISK_MEDIUM
        guidance = "Within QM safe harbor limits"
    else:
        rating = _RISK_HIGH
        guidance = "Exceeds QM safe harbor; requires compensating factors or exception"

    return json.dumps({"value": dti_pct, "rating": rating, "guidance": guidance})


@mcp.tool()
def calculate_ltv(loan_amount: float, property_value: float) -> str:
    """Calculate Loan-to-Value ratio and risk rating.

    LTV = loan_amount / property_value * 100.
    Ratings: <60% Low, 60-80% Medium, >80% High.
    """
    if property_value <= 0 or loan_amount <= 0:
        return json.dumps(
            {
                "value": None,
                "rating": None,
                "warning": "Missing loan amount or property value -- LTV cannot be computed",
            }
        )

    ltv_pct = round(loan_amount / property_value * 100, 1)
    if ltv_pct < _LTV_LOW:
        rating = _RISK_LOW
    elif ltv_pct <= _LTV_MEDIUM:
        rating = _RISK_MEDIUM
    else:
        rating = _RISK_HIGH

    result = {"value": ltv_pct, "rating": rating}
    if ltv_pct > 80:
        result["note"] = "PMI likely required"
    return json.dumps(result)


@mcp.tool()
def evaluate_credit_risk(credit_score: int, source: str = "self_reported") -> str:
    """Evaluate credit risk from a credit score.

    Ratings: >680 Low, 620-680 Medium, <620 High.
    Source should be 'bureau_hard_pull' or 'self_reported'.
    """
    if credit_score <= 0:
        return json.dumps(
            {
                "value": None,
                "rating": None,
                "warning": "No credit score available",
            }
        )

    if credit_score > _CREDIT_LOW:
        rating = _RISK_LOW
    elif credit_score >= _CREDIT_MEDIUM:
        rating = _RISK_MEDIUM
    else:
        rating = _RISK_HIGH

    return json.dumps(
        {
            "value": credit_score,
            "rating": rating,
            "source": source,
        }
    )


@mcp.tool()
def assess_income_stability(employment_statuses: list[str]) -> str:
    """Assess income stability from borrower employment statuses.

    Each status should be one of: w2_employee, self_employed, retired,
    unemployed, other. Returns the worst-case rating across all borrowers.
    """
    if not employment_statuses:
        return json.dumps(
            {
                "value": None,
                "rating": None,
                "warning": "No employment status on file",
            }
        )

    stability_map = {
        "w2_employee": _RISK_LOW,
        "retired": _RISK_LOW,
        "self_employed": _RISK_MEDIUM,
        "other": _RISK_MEDIUM,
        "unemployed": _RISK_HIGH,
    }

    ratings = [stability_map.get(e, _RISK_MEDIUM) for e in employment_statuses]
    risk_order = {_RISK_LOW: 0, _RISK_MEDIUM: 1, _RISK_HIGH: 2}
    worst_rating = max(ratings, key=lambda r: risk_order.get(r, 1))

    return json.dumps(
        {
            "value": ", ".join(employment_statuses),
            "rating": worst_rating,
        }
    )


@mcp.tool()
def assess_asset_sufficiency(total_assets: float, loan_amount: float) -> str:
    """Assess asset sufficiency as a percentage of loan amount.

    Ratio = total_assets / loan_amount * 100.
    Ratings: >20% Low, 10-20% Medium, <10% High.
    """
    if loan_amount <= 0 or total_assets <= 0:
        warning = "No asset data on file" if total_assets <= 0 else "Missing loan amount"
        return json.dumps({"value": None, "rating": None, "warning": warning})

    asset_ratio = round(total_assets / loan_amount * 100, 1)
    if asset_ratio > _ASSET_LOW:
        rating = _RISK_LOW
    elif asset_ratio >= _ASSET_MEDIUM:
        rating = _RISK_MEDIUM
    else:
        rating = _RISK_HIGH

    return json.dumps({"value": asset_ratio, "rating": rating})


@mcp.tool()
def generate_risk_recommendation(
    dti_value: float | None,
    dti_rating: str | None,
    ltv_value: float | None,
    ltv_rating: str | None,
    credit_score: int | None,
    credit_rating: str | None,
    income_stability_rating: str | None,
    income_stability_value: str | None,
    asset_sufficiency_value: float | None,
    asset_sufficiency_rating: str | None,
    employment_statuses: list[str],
    has_financials: bool,
    doc_count: int,
    predictive_model_result: str | None = None,
) -> str:
    """Generate a preliminary underwriting recommendation from all risk factors.

    Takes the outputs of the 5 individual risk tools, an optional ML model
    prediction, and context flags.
    Returns Approve, Approve with Conditions, Suspend, or Deny.
    """
    # Build compensating factors
    compensating_factors: list[str] = []
    if credit_score is not None and credit_score > 740 and dti_rating == _RISK_HIGH:
        compensating_factors.append("Strong credit (>740) offsets elevated DTI")
    if ltv_value is not None and ltv_value < 60 and credit_rating == _RISK_HIGH:
        compensating_factors.append("Low LTV (<60%) offsets weak credit")
    if asset_sufficiency_value is not None and asset_sufficiency_value > 50:
        compensating_factors.append("High reserves (>50% of loan amount)")
    if predictive_model_result and "approved" in predictive_model_result.lower():
        compensating_factors.append("Predictive model supports approval")

    # Build warnings
    warnings: list[str] = []
    if dti_value is None:
        warnings.append("Missing income data -- DTI cannot be computed")
    if ltv_value is None:
        warnings.append("Missing loan amount or property value -- LTV cannot be computed")
    if credit_score is None:
        warnings.append("No credit score on file")
    if not employment_statuses:
        warnings.append("No employment status on file")
    if asset_sufficiency_value is None:
        warnings.append("No asset data on file")

    # Build RiskAssessment and borrower info for compute_recommendation
    risk = RiskAssessment(
        dti={"value": dti_value, "rating": dti_rating},
        ltv={"value": ltv_value, "rating": ltv_rating},
        credit={"value": credit_score, "rating": credit_rating},
        income_stability={"value": income_stability_value, "rating": income_stability_rating},
        asset_sufficiency={"value": asset_sufficiency_value, "rating": asset_sufficiency_rating},
        compensating_factors=compensating_factors,
        warnings=warnings,
    )

    borrowers = [{"employment_status": e} for e in employment_statuses]

    rec: Recommendation = compute_recommendation(
        risk,
        borrowers,
        has_financials=has_financials,
        doc_total=doc_count,
    )

    # Factor in predictive model rejection
    if predictive_model_result and "rejected" in predictive_model_result.lower():
        warnings.append("Predictive model flags elevated risk -- review recommended")
        if rec.recommendation == "Approve":
            rec = Recommendation(
                recommendation="Approve with Conditions",
                rationale=[
                    "Predictive model indicates elevated risk despite passing rule-based checks"
                ],
                conditions=["Review predictive model risk flag before final approval"],
            )

    # Compute overall risk
    ratings = [
        dti_rating,
        ltv_rating,
        credit_rating,
        income_stability_rating,
        asset_sufficiency_rating,
    ]
    valid_ratings = [r for r in ratings if r is not None]
    risk_order = {_RISK_LOW: 0, _RISK_MEDIUM: 1, _RISK_HIGH: 2}
    overall_risk = max(valid_ratings, key=lambda r: risk_order.get(r, 1)) if valid_ratings else None

    return json.dumps(
        {
            "recommendation": rec.recommendation,
            "rationale": rec.rationale,
            "conditions": rec.conditions,
            "overall_risk": overall_risk,
            "compensating_factors": compensating_factors,
            "warnings": warnings,
        }
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
