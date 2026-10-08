# This project was developed with assistance from AI tools.
"""Full seeder against real DB + real S4.

Uses truncate_all fixture because the seeder commits independently via its
own sessions, incompatible with savepoint isolation.
"""

import pytest
from sqlalchemy import func, select

pytestmark = pytest.mark.integration


async def test_seed_creates_borrowers(async_engine, truncate_all):
    """10 borrowers after seed."""
    from db.database import ComplianceSessionLocal, SessionLocal
    from db.models import Borrower

    from src.services.seed.seeder import seed_demo_data

    async with SessionLocal() as session, ComplianceSessionLocal() as compliance_session:
        await seed_demo_data(session, compliance_session, force=True)

    async with SessionLocal() as session:
        count = (await session.execute(select(func.count(Borrower.id)))).scalar()
        assert count == 10


async def test_seed_creates_applications(async_engine, truncate_all):
    """Expected total apps (10 active + 20 historical = 30)."""
    from db.database import ComplianceSessionLocal, SessionLocal
    from db.models import Application

    from src.services.seed.seeder import seed_demo_data

    async with SessionLocal() as session, ComplianceSessionLocal() as compliance_session:
        result = await seed_demo_data(session, compliance_session, force=True)

    async with SessionLocal() as session:
        count = (await session.execute(select(func.count(Application.id)))).scalar()
        expected = result.get("active_applications", 0) + result.get("historical_loans", 0)
        assert count == expected


async def test_seed_creates_coborrower_junctions(async_engine, truncate_all):
    """Co-borrower junction rows exist after seed."""
    from db.database import ComplianceSessionLocal, SessionLocal
    from db.models import ApplicationBorrower

    from src.services.seed.seeder import seed_demo_data

    async with SessionLocal() as session, ComplianceSessionLocal() as compliance_session:
        await seed_demo_data(session, compliance_session, force=True)

    async with SessionLocal() as session:
        non_primary = (
            await session.execute(
                select(func.count(ApplicationBorrower.id)).where(
                    ApplicationBorrower.is_primary.is_(False),
                )
            )
        ).scalar()
        assert non_primary >= 2  # At least 2 co-borrower pairs


async def test_seed_idempotent(async_engine, truncate_all):
    """Second call without force returns already_seeded."""
    from db.database import ComplianceSessionLocal, SessionLocal

    from src.services.seed.seeder import seed_demo_data

    async with SessionLocal() as session, ComplianceSessionLocal() as compliance_session:
        await seed_demo_data(session, compliance_session, force=True)

    async with SessionLocal() as session, ComplianceSessionLocal() as compliance_session:
        result = await seed_demo_data(session, compliance_session, force=False)
        assert result["status"] == "already_seeded"


async def test_seed_hmda_demographics(async_engine, truncate_all):
    """HMDA rows exist for seeded apps."""
    from db.database import ComplianceSessionLocal, SessionLocal
    from db.models import HmdaDemographic

    from src.services.seed.seeder import seed_demo_data

    async with SessionLocal() as session, ComplianceSessionLocal() as compliance_session:
        await seed_demo_data(session, compliance_session, force=True)

    async with ComplianceSessionLocal() as session:
        count = (await session.execute(select(func.count(HmdaDemographic.id)))).scalar()
        assert count > 0
