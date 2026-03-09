# This project was developed with assistance from AI tools.
"""LangGraph tools for the public assistant agent.

These wrap existing business logic so the agent can call them
as tool invocations during a conversation.
"""

from datetime import date

from langchain_core.tools import tool

from ..schemas.calculator import AffordabilityRequest
from ..services.calculator import calculate_affordability
from ..services.products import PRODUCTS


@tool
def current_date() -> str:
    """Return today's date. Use this when you need the current date for due dates, timelines, or any date calculations."""
    return date.today().isoformat()


@tool
def product_info() -> str:
    """Retrieve available mortgage product information."""
    lines = []
    for p in PRODUCTS:
        lines.append(
            f"- **{p.name}** ({p.id}): {p.description} "
            f"Min down payment: {p.min_down_payment_pct}%, typical rate: {p.typical_rate}%"
        )
    return "\n".join(lines)


@tool
def affordability_calc(
    gross_annual_income: float,
    monthly_debts: float = 0,
    down_payment: float = 0,
    interest_rate: float = 6.5,
    loan_term_years: int = 30,
) -> str:
    """Calculate mortgage affordability estimate.

    Args:
        gross_annual_income: Borrower's total annual income before taxes.
        monthly_debts: Total monthly debt obligations (car, student loans, etc.).
        down_payment: Amount available for down payment.
        interest_rate: Expected interest rate (default 6.5%).
        loan_term_years: Loan term in years (default 30).
    """
    req = AffordabilityRequest(
        gross_annual_income=gross_annual_income,
        monthly_debts=monthly_debts,
        down_payment=down_payment,
        interest_rate=interest_rate,
        loan_term_years=loan_term_years,
    )
    result = calculate_affordability(req)

    parts = [
        f"Max loan amount: ${result.max_loan_amount:,.2f}",
        f"Estimated monthly payment: ${result.estimated_monthly_payment:,.2f}",
        f"Estimated purchase price: ${result.estimated_purchase_price:,.2f}",
        f"DTI ratio: {result.dti_ratio}%",
    ]
    if result.dti_warning:
        parts.append(f"Warning: {result.dti_warning}")
    if result.pmi_warning:
        parts.append(f"Note: {result.pmi_warning}")
    return "\n".join(parts)
