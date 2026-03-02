# This project was developed with assistance from AI tools.
"""LE and CD document generation helpers for underwriting decisions.

Pure functions for generating Loan Estimate and Closing Disclosure documents.
Called by decision_tools.py tool implementations.
"""

from datetime import UTC, datetime

from db import ApplicationBorrower, Borrower
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.calculator import compute_monthly_payment
from ..services.rate_lock import get_rate_lock_status
from .shared import format_enum_label


async def get_primary_borrower_name(session: AsyncSession, application_id: int) -> str:
    """Fetch the primary borrower's name for an application.

    Returns "Borrower" if not found.
    """
    ab_stmt = select(ApplicationBorrower).where(
        ApplicationBorrower.application_id == application_id,
        ApplicationBorrower.is_primary.is_(True),
    )
    ab_result = await session.execute(ab_stmt)
    ab = ab_result.scalar_one_or_none()
    if ab:
        b_stmt = select(Borrower).where(Borrower.id == ab.borrower_id)
        b_result = await session.execute(b_stmt)
        borrower = b_result.scalar_one_or_none()
        if borrower:
            return f"{borrower.first_name} {borrower.last_name}"
    return "Borrower"


async def generate_le_text(session, user, app, application_id: int) -> str:
    """Generate Loan Estimate document text.

    Args:
        session: Database session
        user: UserContext
        app: Application model instance
        application_id: Application ID

    Returns:
        Formatted LE document text
    """
    borrower_name = await get_primary_borrower_name(session, application_id)
    rate_lock = await get_rate_lock_status(session, user, application_id)

    # Compute simulated values
    loan_amount = float(app.loan_amount) if app.loan_amount else 0
    property_value = float(app.property_value) if app.property_value else 0
    rate = 6.875  # default simulated rate
    if rate_lock and rate_lock.get("locked_rate"):
        rate = float(rate_lock["locked_rate"])

    loan_type = app.loan_type.value if app.loan_type else "conventional_30"
    term_years = 15 if loan_type == "conventional_15" else 30
    num_payments = term_years * 12

    monthly_payment = compute_monthly_payment(loan_amount, rate, num_payments)

    # Simulated closing costs
    origination_fee = loan_amount * 0.01
    appraisal = 550.0
    title_insurance = loan_amount * 0.003
    recording_fees = 150.0
    total_closing = origination_fee + appraisal + title_insurance + recording_fees

    today = datetime.now(UTC).strftime("%B %d, %Y")
    lines = [
        "LOAN ESTIMATE (SIMULATED)",
        "=========================",
        f"Date Issued: {today}",
        f"Borrower: {borrower_name}",
        f"Application: #{application_id}",
        f"Property: {app.property_address or 'N/A'}",
        "",
        "LOAN TERMS:",
        f"  Loan Amount: ${loan_amount:,.2f}",
        f"  Interest Rate: {rate:.3f}%",
        f"  Loan Type: {format_enum_label(loan_type)}",
        f"  Term: {term_years} years ({num_payments} payments)",
        f"  Monthly P&I: ${monthly_payment:,.2f}",
        "",
        "PROJECTED PAYMENTS:",
        f"  Principal & Interest: ${monthly_payment:,.2f}/month",
        "  Estimated taxes & insurance: Varies by location",
        "",
        "ESTIMATED CLOSING COSTS:",
        f"  Origination fee (1%): ${origination_fee:,.2f}",
        f"  Appraisal: ${appraisal:,.2f}",
        f"  Title insurance: ${title_insurance:,.2f}",
        f"  Recording fees: ${recording_fees:,.2f}",
        f"  Total estimated: ${total_closing:,.2f}",
    ]

    if property_value > 0:
        down_payment = property_value - loan_amount
        ltv = loan_amount / property_value * 100
        lines.extend(
            [
                "",
                "CASH TO CLOSE:",
                f"  Property Value: ${property_value:,.2f}",
                f"  Down Payment: ${down_payment:,.2f}",
                f"  Estimated Closing Costs: ${total_closing:,.2f}",
                f"  Total Cash to Close: ${down_payment + total_closing:,.2f}",
                f"  LTV: {ltv:.1f}%",
            ]
        )

    lines.extend(
        [
            "",
            "DISCLAIMER: This Loan Estimate is simulated for demonstration",
            "purposes and does not constitute an actual TRID Loan Estimate.",
        ]
    )

    return "\n".join(lines)


async def generate_cd_text(session, user, app, application_id: int) -> str:
    """Generate Closing Disclosure document text.

    Args:
        session: Database session
        user: UserContext
        app: Application model instance
        application_id: Application ID

    Returns:
        Formatted CD document text
    """
    borrower_name = await get_primary_borrower_name(session, application_id)
    rate_lock = await get_rate_lock_status(session, user, application_id)

    # Compute values
    loan_amount = float(app.loan_amount) if app.loan_amount else 0
    property_value = float(app.property_value) if app.property_value else 0
    rate = 6.875
    if rate_lock and rate_lock.get("locked_rate"):
        rate = float(rate_lock["locked_rate"])

    loan_type = app.loan_type.value if app.loan_type else "conventional_30"
    term_years = 15 if loan_type == "conventional_15" else 30
    num_payments = term_years * 12

    monthly_payment = compute_monthly_payment(loan_amount, rate, num_payments)

    # Final closing costs (slightly different from LE for realism)
    origination_fee = loan_amount * 0.01
    appraisal = 550.0
    title_insurance = loan_amount * 0.003
    recording_fees = 175.0
    transfer_tax = property_value * 0.001 if property_value else 0
    total_closing = origination_fee + appraisal + title_insurance + recording_fees + transfer_tax

    today = datetime.now(UTC).strftime("%B %d, %Y")
    closing_date = app.closing_date.strftime("%B %d, %Y") if app.closing_date else today

    lines = [
        "CLOSING DISCLOSURE (SIMULATED)",
        "==============================",
        f"Date Issued: {today}",
        f"Closing Date: {closing_date}",
        f"Borrower: {borrower_name}",
        f"Application: #{application_id}",
        f"Property: {app.property_address or 'N/A'}",
        "",
        "LOAN TERMS:",
        f"  Loan Amount: ${loan_amount:,.2f}",
        f"  Interest Rate: {rate:.3f}%",
        f"  Loan Type: {format_enum_label(loan_type)}",
        f"  Term: {term_years} years ({num_payments} payments)",
        f"  Monthly P&I: ${monthly_payment:,.2f}",
        "",
        "CLOSING COST DETAILS:",
        f"  Origination fee (1%): ${origination_fee:,.2f}",
        f"  Appraisal: ${appraisal:,.2f}",
        f"  Title insurance: ${title_insurance:,.2f}",
        f"  Recording fees: ${recording_fees:,.2f}",
        f"  Transfer tax: ${transfer_tax:,.2f}",
        f"  Total closing costs: ${total_closing:,.2f}",
    ]

    if property_value > 0:
        down_payment = property_value - loan_amount
        lines.extend(
            [
                "",
                "CASH TO CLOSE:",
                f"  Purchase Price: ${property_value:,.2f}",
                f"  Down Payment: ${down_payment:,.2f}",
                f"  Total Closing Costs: ${total_closing:,.2f}",
                f"  Total Cash to Close: ${down_payment + total_closing:,.2f}",
            ]
        )

    lines.extend(
        [
            "",
            "DISCLAIMER: This Closing Disclosure is simulated for demonstration",
            "purposes and does not constitute an actual TRID Closing Disclosure.",
        ]
    )

    return "\n".join(lines)
