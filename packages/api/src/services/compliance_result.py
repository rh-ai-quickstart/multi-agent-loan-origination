# This project was developed with assistance from AI tools.
"""Service for persisting and querying compliance check results."""

from db import ComplianceResult
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def create_compliance_result(
    session: AsyncSession,
    *,
    application_id: int,
    ecoa_status: str | None,
    ecoa_rationale: str | None,
    ecoa_details: list[str] | None,
    atr_qm_status: str | None,
    atr_qm_rationale: str | None,
    atr_qm_details: list[str] | None,
    trid_status: str | None,
    trid_rationale: str | None,
    trid_details: list[str] | None,
    overall_status: str | None,
    can_proceed: bool | None,
    checked_by: str | None,
) -> ComplianceResult:
    """Create a compliance result record (add only, caller commits)."""
    record = ComplianceResult(
        application_id=application_id,
        ecoa_status=ecoa_status,
        ecoa_rationale=ecoa_rationale,
        ecoa_details=ecoa_details,
        atr_qm_status=atr_qm_status,
        atr_qm_rationale=atr_qm_rationale,
        atr_qm_details=atr_qm_details,
        trid_status=trid_status,
        trid_rationale=trid_rationale,
        trid_details=trid_details,
        overall_status=overall_status,
        can_proceed=can_proceed,
        checked_by=checked_by,
    )
    session.add(record)
    return record


async def get_latest_compliance_result(
    session: AsyncSession,
    application_id: int,
) -> ComplianceResult | None:
    """Get the most recent compliance result for an application."""
    stmt = (
        select(ComplianceResult)
        .where(ComplianceResult.application_id == application_id)
        .order_by(ComplianceResult.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
