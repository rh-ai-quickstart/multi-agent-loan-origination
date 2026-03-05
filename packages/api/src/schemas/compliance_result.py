# This project was developed with assistance from AI tools.
"""Schemas for compliance result endpoints."""

from datetime import datetime

from pydantic import BaseModel


class ComplianceResultResponse(BaseModel):
    """Response for the latest compliance check result."""

    id: int
    application_id: int
    ecoa_status: str | None = None
    ecoa_rationale: str | None = None
    ecoa_details: list[str] | None = None
    atr_qm_status: str | None = None
    atr_qm_rationale: str | None = None
    atr_qm_details: list[str] | None = None
    trid_status: str | None = None
    trid_rationale: str | None = None
    trid_details: list[str] | None = None
    overall_status: str | None = None
    can_proceed: bool | None = None
    checked_by: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
