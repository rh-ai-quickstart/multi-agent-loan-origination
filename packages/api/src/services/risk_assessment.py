# This project was developed with assistance from AI tools.
"""Service for persisting and querying risk assessment results."""

from db import RiskAssessmentRecord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def create_risk_assessment(
    session: AsyncSession,
    *,
    application_id: int,
    dti_value: float | None,
    dti_rating: str | None,
    ltv_value: float | None,
    ltv_rating: str | None,
    credit_value: int | None,
    credit_rating: str | None,
    credit_source: str | None,
    income_stability_value: str | None,
    income_stability_rating: str | None,
    asset_sufficiency_value: float | None,
    asset_sufficiency_rating: str | None,
    compensating_factors: list[str] | None,
    warnings: list[str] | None,
    overall_risk: str | None,
    assessed_by: str | None,
    recommendation: str | None = None,
    recommendation_rationale: list[str] | None = None,
    recommendation_conditions: list[str] | None = None,
    predictive_model_result: str | None = None,
    predictive_model_available: bool | None = None,
) -> RiskAssessmentRecord:
    """Create a risk assessment record (add only, caller commits)."""
    record = RiskAssessmentRecord(
        application_id=application_id,
        dti_value=dti_value,
        dti_rating=dti_rating,
        ltv_value=ltv_value,
        ltv_rating=ltv_rating,
        credit_value=credit_value,
        credit_rating=credit_rating,
        credit_source=credit_source,
        income_stability_value=income_stability_value,
        income_stability_rating=income_stability_rating,
        asset_sufficiency_value=asset_sufficiency_value,
        asset_sufficiency_rating=asset_sufficiency_rating,
        compensating_factors=compensating_factors,
        warnings=warnings,
        overall_risk=overall_risk,
        assessed_by=assessed_by,
        recommendation=recommendation,
        recommendation_rationale=recommendation_rationale,
        recommendation_conditions=recommendation_conditions,
        predictive_model_result=predictive_model_result,
        predictive_model_available=predictive_model_available,
    )
    session.add(record)
    return record


async def update_recommendation(
    session: AsyncSession,
    application_id: int,
    *,
    recommendation: str,
    rationale: list[str] | None,
    conditions: list[str] | None,
    assessed_by: str | None = None,
) -> RiskAssessmentRecord:
    """Update the latest risk assessment with recommendation data (caller commits).

    If no risk assessment record exists yet, creates a minimal one with
    just the recommendation fields so the data is never silently lost.
    """
    record = await get_latest_risk_assessment(session, application_id)
    if record is None:
        record = RiskAssessmentRecord(
            application_id=application_id,
            assessed_by=assessed_by,
        )
        session.add(record)
    record.recommendation = recommendation
    record.recommendation_rationale = rationale
    record.recommendation_conditions = conditions
    return record


async def get_latest_risk_assessment(
    session: AsyncSession,
    application_id: int,
) -> RiskAssessmentRecord | None:
    """Get the most recent risk assessment for an application."""
    stmt = (
        select(RiskAssessmentRecord)
        .where(RiskAssessmentRecord.application_id == application_id)
        .order_by(RiskAssessmentRecord.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
