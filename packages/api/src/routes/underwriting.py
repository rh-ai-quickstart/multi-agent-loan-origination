# This project was developed with assistance from AI tools.
"""Underwriting REST endpoints for risk assessment and compliance results."""

from db import get_db
from db.enums import UserRole
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import CurrentUser, require_roles
from ..schemas.compliance_result import ComplianceResultResponse
from ..schemas.risk_assessment import RiskAssessmentResponse
from ..services.compliance_result import get_latest_compliance_result
from ..services.risk_assessment import get_latest_risk_assessment

router = APIRouter()

_UW_ROLES = [
    UserRole.ADMIN,
    UserRole.UNDERWRITER,
    UserRole.LOAN_OFFICER,
    UserRole.CEO,
]


@router.get(
    "/{application_id}/risk-assessment",
    response_model=RiskAssessmentResponse,
    dependencies=[Depends(require_roles(*_UW_ROLES))],
)
async def get_risk_assessment(
    application_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> RiskAssessmentResponse:
    """Get the latest risk assessment for an application.

    Returns 404 if no risk assessment has been run yet.
    """
    record = await get_latest_risk_assessment(session, application_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No risk assessment found for this application",
        )
    return RiskAssessmentResponse.model_validate(record)


@router.get(
    "/{application_id}/compliance-result",
    response_model=ComplianceResultResponse,
    dependencies=[Depends(require_roles(*_UW_ROLES))],
)
async def get_compliance_result(
    application_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> ComplianceResultResponse:
    """Get the latest compliance check result for an application.

    Returns 404 if no compliance check has been run yet.
    """
    record = await get_latest_compliance_result(session, application_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No compliance result found for this application",
        )
    return ComplianceResultResponse.model_validate(record)
