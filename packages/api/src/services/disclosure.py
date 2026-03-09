# This project was developed with assistance from AI tools.
"""Disclosure acknowledgment service.

Tracks borrower acknowledgment of required lending disclosures
(Loan Estimate, privacy notice, HMDA notice, equal opportunity notice)
via the append-only audit trail.  Each acknowledgment is a separate
audit event with event_type='disclosure_acknowledged'.
"""

from db import AuditEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings

# Canonical list of disclosures a borrower must acknowledge.
# Content is simulated for demonstration purposes.
REQUIRED_DISCLOSURES: list[dict[str, str]] = [
    {
        "id": "loan_estimate",
        "label": "Loan Estimate",
        "summary": (
            "The Loan Estimate provides an overview of your loan terms, "
            "projected payments, and estimated closing costs."
        ),
        "content": (
            "LOAN ESTIMATE DISCLOSURE\n\n"
            "Simulated for demonstration purposes.\n\n"
            "This Loan Estimate is provided to you pursuant to the "
            "Truth in Lending Act (TILA) and the Real Estate Settlement "
            "Procedures Act (RESPA), as implemented by the TILA-RESPA "
            "Integrated Disclosure (TRID) rule.\n\n"
            "PURPOSE: This document provides you with important information "
            "about your requested mortgage loan. It includes estimates of "
            "your loan terms, projected monthly payments, and estimated "
            "closing costs. Use this form to compare with offers from other "
            "lenders.\n\n"
            "LOAN TERMS: The interest rate, monthly principal and interest "
            "payment, and whether these amounts can increase after closing "
            "are described in the Loan Terms section. Review carefully "
            "whether your loan includes a prepayment penalty or a balloon "
            "payment.\n\n"
            "PROJECTED PAYMENTS: This section shows your estimated total "
            "monthly payment, including principal, interest, mortgage "
            "insurance, and estimated escrow (property taxes and "
            "homeowners insurance).\n\n"
            "CLOSING COSTS: Estimated closing costs include loan costs "
            "(origination charges, services you cannot and can shop for) "
            "and other costs (taxes, government fees, prepaids, and initial "
            "escrow payments). The Cash to Close section estimates the total "
            "amount you will need at closing.\n\n"
            "IMPORTANT: This is an estimate. Actual terms may vary. You "
            "will receive a Closing Disclosure at least three business days "
            "before closing that will reflect the final terms and costs."
        ),
    },
    {
        "id": "privacy_notice",
        "label": "Privacy Notice",
        "summary": (
            f"The Privacy Notice explains how {settings.COMPANY_NAME} collects, "
            "uses, and protects your personal information."
        ),
        "content": (
            "PRIVACY NOTICE\n\n"
            "Simulated for demonstration purposes.\n\n"
            f"{settings.COMPANY_NAME} is committed to protecting the privacy "
            "and security of your personal information. This notice describes "
            "our practices regarding the collection, use, and disclosure of "
            "nonpublic personal information (NPI) as required by the "
            "Gramm-Leach-Bliley Act (GLBA).\n\n"
            "INFORMATION WE COLLECT: We collect personal information that "
            "you provide on applications and other forms, including your "
            "name, address, Social Security number, income, employment "
            "information, and asset and debt details. We also collect "
            "information from credit reporting agencies, property appraisers, "
            "and other third parties involved in your transaction.\n\n"
            "HOW WE USE YOUR INFORMATION: We use your information to "
            "process your mortgage application, service your loan, comply "
            "with legal requirements, and communicate with you about your "
            "account.\n\n"
            "INFORMATION WE SHARE: We may share your information with "
            "service providers who assist us in processing and servicing "
            "your loan, credit reporting agencies, government agencies as "
            "required by law, and other parties with your consent. We do "
            "not sell your personal information to third parties for "
            "marketing purposes.\n\n"
            "YOUR RIGHTS: You have the right to opt out of certain "
            "information sharing, access your personal information, and "
            "request corrections. Contact us at privacy@example.com "
            "to exercise these rights.\n\n"
            "DATA SECURITY: We maintain physical, electronic, and "
            "procedural safeguards to protect your information, including "
            "encryption, access controls, and regular security assessments."
        ),
    },
    {
        "id": "hmda_notice",
        "label": "HMDA Notice",
        "summary": (
            "The Home Mortgage Disclosure Act notice explains that certain "
            "demographic information is collected for federal reporting purposes "
            "and will not affect your application."
        ),
        "content": (
            "HOME MORTGAGE DISCLOSURE ACT (HMDA) NOTICE\n\n"
            "Simulated for demonstration purposes.\n\n"
            f"The Home Mortgage Disclosure Act (HMDA) requires {settings.COMPANY_NAME} "
            "to collect and report certain information about "
            "mortgage applications and loans. This data is used by federal "
            "regulators and the public to monitor whether financial "
            "institutions are serving the housing needs of their communities "
            "and to help identify possible discriminatory lending patterns.\n\n"
            "INFORMATION COLLECTED: We are required to collect the following "
            "demographic information from you:\n"
            "  - Race and ethnicity\n"
            "  - Sex\n"
            "  - Age\n\n"
            "VOLUNTARY DISCLOSURE: Providing this information is voluntary. "
            "You are not required to furnish it. However, if you choose not "
            "to provide it and you have completed the application in person, "
            "federal regulations require the lender to note your race/ethnicity "
            "and sex based on visual observation or surname.\n\n"
            "NO EFFECT ON APPLICATION: This information will NOT be used in "
            "evaluating your mortgage application or in any credit decision. "
            "It has no bearing on whether your loan is approved or denied, "
            "or on the terms of your loan.\n\n"
            "DATA PROTECTION: Demographic information is collected and "
            "stored separately from your loan application data to prevent "
            "any influence on lending decisions. It is reported to regulators "
            "in aggregate, anonymized form.\n\n"
            "FEDERAL REQUIREMENT: This collection is mandated by 12 CFR "
            "Part 1003 (Regulation C), as implemented by the Consumer "
            "Financial Protection Bureau (CFPB)."
        ),
    },
    {
        "id": "equal_opportunity_notice",
        "label": "Equal Credit Opportunity Notice",
        "summary": (
            "The Equal Credit Opportunity Act prohibits discrimination in "
            "lending. This notice confirms your rights under federal law."
        ),
        "content": (
            "EQUAL CREDIT OPPORTUNITY ACT (ECOA) NOTICE\n\n"
            "Simulated for demonstration purposes.\n\n"
            "The Equal Credit Opportunity Act (ECOA) prohibits creditors "
            "from discriminating against credit applicants on the basis of "
            "race, color, religion, national origin, sex, marital status, "
            "age (provided the applicant has the capacity to contract), "
            "because all or part of the applicant's income derives from "
            "any public assistance program, or because the applicant has "
            "in good faith exercised any right under the Consumer Credit "
            "Protection Act.\n\n"
            "YOUR RIGHTS UNDER ECOA:\n\n"
            "1. RIGHT TO FAIR EVALUATION: Your creditworthiness will be "
            "evaluated based on your financial qualifications, not on "
            "prohibited factors listed above.\n\n"
            "2. RIGHT TO KNOW: If your application is denied, you have "
            f"the right to know the specific reasons for the denial. {settings.COMPANY_NAME} "
            "will provide a written notice of adverse action "
            "within 30 days of the decision.\n\n"
            "3. RIGHT TO INCOME CONSIDERATION: All reliable income must "
            "be considered, including part-time employment, retirement "
            "benefits, alimony, and child support, if you choose to "
            "disclose them.\n\n"
            "4. RIGHT TO JOINT APPLICATION: You have the right to apply "
            "for credit jointly with another person or individually.\n\n"
            "5. RIGHT TO FILE A COMPLAINT: If you believe you have been "
            "discriminated against, you may file a complaint with the "
            "Consumer Financial Protection Bureau (CFPB) at "
            "www.consumerfinance.gov or call (855) 411-2372.\n\n"
            "FEDERAL ENFORCEMENT: ECOA is codified at 15 U.S.C. 1691 "
            "et seq. and implemented by Regulation B (12 CFR Part 1002)."
        ),
    },
]

_DISCLOSURE_IDS = {d["id"] for d in REQUIRED_DISCLOSURES}
DISCLOSURE_BY_ID = {d["id"]: d for d in REQUIRED_DISCLOSURES}


async def get_disclosure_status(
    session: AsyncSession,
    application_id: int,
) -> dict:
    """Return disclosure acknowledgment status for an application.

    Queries audit_events for event_type='disclosure_acknowledged' rows
    linked to the given application_id.

    Returns:
        {
            "application_id": int,
            "all_acknowledged": bool,
            "acknowledged": ["loan_estimate", ...],
            "pending": ["privacy_notice", ...],
        }
    """
    stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.event_type == "disclosure_acknowledged",
            AuditEvent.application_id == application_id,
        )
        .order_by(AuditEvent.timestamp.asc())
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    acknowledged_ids: set[str] = set()
    for event in events:
        if event.event_data and isinstance(event.event_data, dict):
            disc_id = event.event_data.get("disclosure_id")
            if disc_id in _DISCLOSURE_IDS:
                acknowledged_ids.add(disc_id)

    pending = [d_id for d_id in _DISCLOSURE_IDS if d_id not in acknowledged_ids]

    return {
        "application_id": application_id,
        "all_acknowledged": len(pending) == 0,
        "acknowledged": sorted(acknowledged_ids),
        "pending": sorted(pending),
    }
