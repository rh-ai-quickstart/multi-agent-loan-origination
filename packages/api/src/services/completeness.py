# This project was developed with assistance from AI tools.
"""Document completeness checking service.

Determines which documents are required for a given loan type and employment
status, then compares against uploaded documents to produce a completeness
summary.
"""

import json
import logging

from db import Document
from db.enums import DocumentStatus, DocumentType, EmploymentStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.auth import UserContext
from ..schemas.completeness import CompletenessResponse, DocumentRequirement
from ..services.application import get_application

logger = logging.getLogger(__name__)

# Human-readable labels for document types
DOC_TYPE_LABELS: dict[DocumentType, str] = {
    DocumentType.W2: "W-2 Form",
    DocumentType.PAY_STUB: "Recent Pay Stub",
    DocumentType.TAX_RETURN: "Tax Return",
    DocumentType.BANK_STATEMENT: "Bank Statement",
    DocumentType.DRIVERS_LICENSE: "Driver's License",
    DocumentType.PASSPORT: "Passport",
    DocumentType.PROPERTY_APPRAISAL: "Property Appraisal",
    DocumentType.HOMEOWNERS_INSURANCE: "Homeowner's Insurance",
    DocumentType.TITLE_INSURANCE: "Title Insurance",
    DocumentType.FLOOD_INSURANCE: "Flood Insurance",
    DocumentType.PURCHASE_AGREEMENT: "Purchase Agreement",
    DocumentType.GIFT_LETTER: "Gift Letter",
}

# Common document sets (factored for reuse)
_ID_DOCS = [DocumentType.DRIVERS_LICENSE, DocumentType.PASSPORT]
# Standard W-2 employee docs (conventional loans)
_W2_DOCS = [
    DocumentType.W2,
    DocumentType.PAY_STUB,
    DocumentType.BANK_STATEMENT,
    DocumentType.DRIVERS_LICENSE,
]
# W-2 employee + tax returns (jumbo, FHA -- higher income verification)
_W2_WITH_TAX = [
    DocumentType.W2,
    DocumentType.PAY_STUB,
    DocumentType.TAX_RETURN,
    DocumentType.BANK_STATEMENT,
    DocumentType.DRIVERS_LICENSE,
]
_SELF_EMPLOYED_DOCS = [
    DocumentType.TAX_RETURN,
    DocumentType.BANK_STATEMENT,
    DocumentType.DRIVERS_LICENSE,
]
_UNEMPLOYED_DOCS = [DocumentType.BANK_STATEMENT, DocumentType.DRIVERS_LICENSE]

# Document requirements by loan_type and employment_status.
# Key structure: DOCUMENT_REQUIREMENTS[loan_type_value][employment_status_value]
# Falls back: specific -> loan_type + "_default" -> "_default" + "_default"
DOCUMENT_REQUIREMENTS: dict[str, dict[str, list[DocumentType]]] = {
    "_default": {
        "_default": _W2_DOCS,
        EmploymentStatus.W2_EMPLOYEE.value: _W2_DOCS,
        EmploymentStatus.SELF_EMPLOYED.value: _SELF_EMPLOYED_DOCS,
        EmploymentStatus.RETIRED.value: _SELF_EMPLOYED_DOCS,
        EmploymentStatus.UNEMPLOYED.value: _UNEMPLOYED_DOCS,
        EmploymentStatus.OTHER.value: _SELF_EMPLOYED_DOCS,
    },
    "fha": {
        "_default": _W2_WITH_TAX,
        EmploymentStatus.W2_EMPLOYEE.value: _W2_WITH_TAX,
        EmploymentStatus.SELF_EMPLOYED.value: _SELF_EMPLOYED_DOCS,
        EmploymentStatus.RETIRED.value: _SELF_EMPLOYED_DOCS,
    },
    "va": {
        "_default": _W2_DOCS,
        EmploymentStatus.W2_EMPLOYEE.value: _W2_DOCS,
        EmploymentStatus.SELF_EMPLOYED.value: _SELF_EMPLOYED_DOCS,
    },
    "jumbo": {
        "_default": _W2_WITH_TAX,
        EmploymentStatus.W2_EMPLOYEE.value: _W2_WITH_TAX,
        EmploymentStatus.SELF_EMPLOYED.value: _SELF_EMPLOYED_DOCS,
        EmploymentStatus.RETIRED.value: _SELF_EMPLOYED_DOCS,
    },
    "usda": {
        "_default": _W2_WITH_TAX,
        EmploymentStatus.W2_EMPLOYEE.value: _W2_WITH_TAX,
        EmploymentStatus.SELF_EMPLOYED.value: _SELF_EMPLOYED_DOCS,
        EmploymentStatus.RETIRED.value: _SELF_EMPLOYED_DOCS,
    },
    "arm": {
        "_default": _W2_WITH_TAX,
        EmploymentStatus.W2_EMPLOYEE.value: _W2_WITH_TAX,
        EmploymentStatus.SELF_EMPLOYED.value: _SELF_EMPLOYED_DOCS,
        EmploymentStatus.RETIRED.value: _SELF_EMPLOYED_DOCS,
    },
}

# Statuses that count as "not provided" for completeness purposes
_EXCLUDED_STATUSES = {
    DocumentStatus.REJECTED,
    DocumentStatus.FLAGGED_FOR_RESUBMISSION,
    DocumentStatus.PROCESSING_FAILED,
}


def _get_required_doc_types(
    loan_type: str | None,
    employment_status: str | None,
) -> list[DocumentType]:
    """Look up required doc types using fallback chain."""
    lt = loan_type or "_default"
    es = employment_status or "_default"

    # Try specific loan_type + employment_status
    loan_reqs = DOCUMENT_REQUIREMENTS.get(lt)
    if loan_reqs:
        reqs = loan_reqs.get(es)
        if reqs:
            return reqs
        # Try loan_type + _default
        reqs = loan_reqs.get("_default")
        if reqs:
            return reqs

    # Fall back to _default + employment_status
    default_reqs = DOCUMENT_REQUIREMENTS["_default"]
    reqs = default_reqs.get(es)
    if reqs:
        return reqs

    # Ultimate fallback: _default + _default
    return default_reqs["_default"]


async def check_completeness(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
) -> CompletenessResponse | None:
    """Check document completeness for an application.

    Returns None if the application is not found or not accessible.
    """
    app = await get_application(session, user, application_id)
    if app is None:
        return None

    # Resolve primary borrower's employment status
    employment_status = None
    for ab in app.application_borrowers or []:
        if ab.is_primary and ab.borrower:
            employment_status = (
                ab.borrower.employment_status.value if ab.borrower.employment_status else None
            )
            break

    loan_type = app.loan_type.value if app.loan_type else None
    required_types = _get_required_doc_types(loan_type, employment_status)

    # Query documents for this app, excluding failed/rejected.
    # No separate scope filter needed -- get_application already verified access.
    doc_stmt = select(Document).where(
        Document.application_id == application_id,
        Document.status.notin_([s.value for s in _EXCLUDED_STATUSES]),
    )
    doc_result = await session.execute(doc_stmt)
    documents = doc_result.scalars().all()

    # Build lookup: doc_type -> best document (most recent)
    doc_by_type: dict[DocumentType, Document] = {}
    for doc in documents:
        existing = doc_by_type.get(doc.doc_type)
        if existing is None or doc.created_at > existing.created_at:
            doc_by_type[doc.doc_type] = doc

    # Build requirements list
    requirements: list[DocumentRequirement] = []
    provided_count = 0
    for dt in required_types:
        doc = doc_by_type.get(dt)
        if doc:
            flags = []
            if doc.quality_flags:
                try:
                    flags = json.loads(doc.quality_flags)
                except (json.JSONDecodeError, TypeError):
                    flags = []
            requirements.append(
                DocumentRequirement(
                    doc_type=dt,
                    label=DOC_TYPE_LABELS.get(dt, dt.value),
                    is_provided=True,
                    document_id=doc.id,
                    status=doc.status,
                    quality_flags=flags,
                )
            )
            provided_count += 1
        else:
            requirements.append(
                DocumentRequirement(
                    doc_type=dt,
                    label=DOC_TYPE_LABELS.get(dt, dt.value),
                    is_provided=False,
                )
            )

    return CompletenessResponse(
        application_id=application_id,
        is_complete=provided_count == len(required_types),
        requirements=requirements,
        provided_count=provided_count,
        required_count=len(required_types),
    )


# Statuses that indicate a document is still being processed
_UNPROCESSED_STATUSES = {
    DocumentStatus.UPLOADED,
    DocumentStatus.PROCESSING,
}


async def check_underwriting_readiness(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
) -> dict | None:
    """Check whether an application is ready for underwriting submission.

    Returns {"is_ready": bool, "blockers": list[str]} or None if the
    application is not found / out of scope.
    """
    from db.enums import ApplicationStage

    app = await get_application(session, user, application_id)
    if app is None:
        return None

    blockers: list[str] = []

    # 1. Must be in APPLICATION stage
    current_stage = app.stage or ApplicationStage.INQUIRY
    if current_stage != ApplicationStage.APPLICATION:
        blockers.append(
            f"Application is in '{current_stage.value}' stage "
            f"(must be in 'application' stage to submit)"
        )

    # 2. All required documents must be provided
    completeness = await check_completeness(session, user, application_id)
    if completeness and not completeness.is_complete:
        missing = [r.label for r in completeness.requirements if not r.is_provided]
        blockers.append(f"Missing required documents: {', '.join(missing)}")

    # 3. No documents still in processing
    if completeness:
        unprocessed = [
            r.label
            for r in completeness.requirements
            if r.is_provided and r.status in _UNPROCESSED_STATUSES
        ]
        if unprocessed:
            blockers.append(f"Documents still processing: {', '.join(unprocessed)}")

    # 4. No critical quality flags
    if completeness:
        flagged = [r.label for r in completeness.requirements if r.is_provided and r.quality_flags]
        if flagged:
            blockers.append(f"Documents with quality issues: {', '.join(flagged)}")

    return {"is_ready": len(blockers) == 0, "blockers": blockers}
