# This project was developed with assistance from AI tools.
"""Schemas for risk assessment endpoints."""

from datetime import datetime

from pydantic import BaseModel


class RiskAssessmentResponse(BaseModel):
    """Response for the latest risk assessment."""

    id: int
    application_id: int
    dti_value: float | None = None
    dti_rating: str | None = None
    ltv_value: float | None = None
    ltv_rating: str | None = None
    credit_value: int | None = None
    credit_rating: str | None = None
    credit_source: str | None = None
    income_stability_value: str | None = None
    income_stability_rating: str | None = None
    asset_sufficiency_value: float | None = None
    asset_sufficiency_rating: str | None = None
    compensating_factors: list[str] | None = None
    warnings: list[str] | None = None
    overall_risk: str | None = None
    recommendation: str | None = None
    recommendation_rationale: list[str] | None = None
    recommendation_conditions: list[str] | None = None
    assessed_by: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
