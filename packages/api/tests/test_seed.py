# This project was developed with assistance from AI tools.
"""Tests for demo data seeding service and admin endpoints."""

import json
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db import get_compliance_db, get_db
from db.enums import ApplicationStage, UserRole
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.auth import get_current_user
from src.routes.admin import router
from src.schemas.auth import DataScope, UserContext
from src.services.seed.fixtures import (
    ACTIVE_APPLICATIONS,
    BORROWERS,
    HISTORICAL_LOANS,
    HMDA_DEMOGRAPHICS,
    compute_config_hash,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ADMIN_USER = UserContext(
    user_id="admin",
    role=UserRole.ADMIN,
    email="admin@summit-cap.com",
    name="Admin User",
    data_scope=DataScope(full_pipeline=True),
)


def _make_app(user: UserContext = _ADMIN_USER):
    """Build a test app with admin routes and mocked auth."""
    app = FastAPI()
    app.include_router(router, prefix="/api/admin")

    async def fake_user():
        return user

    app.dependency_overrides[get_current_user] = fake_user
    return app


# ---------------------------------------------------------------------------
# Fixture data tests
# ---------------------------------------------------------------------------


def test_fixture_borrower_count():
    """Fixture defines 10 borrowers (1 real + 1 co-borrower + 8 fictional)."""
    assert len(BORROWERS) == 10


def test_fixture_active_application_count():
    """Fixture defines 10 active applications."""
    assert len(ACTIVE_APPLICATIONS) == 10


def test_fixture_active_stage_distribution():
    """Active applications distributed: 4 application, 3 underwriting,
    2 conditional_approval, 1 clear_to_close."""
    stages = [a["stage"] for a in ACTIVE_APPLICATIONS]
    assert stages.count(ApplicationStage.APPLICATION) == 4
    assert stages.count(ApplicationStage.UNDERWRITING) == 3
    assert stages.count(ApplicationStage.CONDITIONAL_APPROVAL) == 2
    assert stages.count(ApplicationStage.CLEAR_TO_CLOSE) == 1


def test_fixture_historical_loan_count():
    """Fixture defines 20 historical loans (16 approved + 4 denied)."""
    assert len(HISTORICAL_LOANS) == 20
    closed = [h for h in HISTORICAL_LOANS if h["stage"] == ApplicationStage.CLOSED]
    denied = [h for h in HISTORICAL_LOANS if h["stage"] == ApplicationStage.DENIED]
    assert len(closed) == 16
    assert len(denied) == 4


def test_fixture_hmda_demographics_count():
    """Fixture defines 30 HMDA demographics (10 active + 20 historical)."""
    assert len(HMDA_DEMOGRAPHICS) == 30


def test_fixture_active_apps_use_multiple_loan_officers():
    """Active applications are distributed across 3 loan officers."""
    from src.services.seed.fixtures import (
        JAMES_TORRES_ID,
        MARCUS_WILLIAMS_ID,
        SARAH_PATEL_ID,
    )

    los = {a["assigned_to"] for a in ACTIVE_APPLICATIONS}
    assert los == {JAMES_TORRES_ID, SARAH_PATEL_ID, MARCUS_WILLIAMS_ID}


def test_fixture_all_loan_types_represented():
    """All 7 loan types appear across active + historical applications."""
    from db.enums import LoanType

    all_apps = ACTIVE_APPLICATIONS + HISTORICAL_LOANS
    loan_types_used = {a["loan_type"] for a in all_apps}
    for lt in LoanType:
        assert lt in loan_types_used, f"{lt.value} not represented in seed data"


def test_fixture_hmda_protected_class_representation():
    """HMDA demographics have 30%+ protected class representation."""
    races = [d["race"] for d in HMDA_DEMOGRAPHICS]
    non_white = [r for r in races if r != "White"]
    protected_pct = len(non_white) / len(races)
    assert protected_pct >= 0.30, f"Protected class representation {protected_pct:.0%} < 30%"


def test_fixture_config_hash_stable():
    """Config hash is deterministic."""
    h1 = compute_config_hash()
    h2 = compute_config_hash()
    assert h1 == h2
    assert len(h1) == 64  # SHA-256


# ---------------------------------------------------------------------------
# Seed service tests (mocked sessions)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _mock_engine_begin():
    """Fake async context manager replacing engine.begin() in tests."""
    conn = AsyncMock()
    yield conn


@pytest.mark.asyncio
async def test_seed_creates_borrowers():
    """Seed creates borrower records with correct keycloak IDs."""
    from src.services.seed.seeder import seed_demo_data

    session = AsyncMock()
    compliance_session = AsyncMock()

    # No existing manifest
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    # Track added objects
    added_objects = []

    def track_add(obj):
        added_objects.append(obj)

    session.add = MagicMock(side_effect=track_add)

    # flush gives IDs to objects
    _flush_counter = [0]

    async def fake_flush():
        _flush_counter[0] += 1
        for obj in added_objects:
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = _flush_counter[0]
                _flush_counter[0] += 1

    session.flush = fake_flush
    compliance_session.add = MagicMock()

    # Patch engine so timestamp overrides don't open a real asyncpg connection
    mock_engine = MagicMock()
    mock_engine.begin = _mock_engine_begin
    with patch("db.database.engine", mock_engine):
        await seed_demo_data(session, compliance_session, force=False)

    # Verify borrowers were added
    from db import Borrower

    borrower_adds = [o for o in added_objects if isinstance(o, Borrower)]
    assert len(borrower_adds) == 10

    from src.services.seed.fixtures import MICHAEL_JOHNSON_ID, SARAH_MITCHELL_ID

    keycloak_ids = {b.keycloak_user_id for b in borrower_adds}
    assert SARAH_MITCHELL_ID in keycloak_ids
    assert MICHAEL_JOHNSON_ID in keycloak_ids


@pytest.mark.asyncio
async def test_seed_idempotent():
    """Second call without force returns early, no duplicates."""
    from src.services.seed.seeder import seed_demo_data

    session = AsyncMock()
    compliance_session = AsyncMock()

    # Existing manifest
    manifest = MagicMock()
    manifest.seeded_at = datetime(2026, 1, 1, 0, 0, 0)
    manifest.config_hash = "abc123"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = manifest
    session.execute = AsyncMock(return_value=mock_result)

    result = await seed_demo_data(session, compliance_session, force=False)

    assert result["status"] == "already_seeded"
    # Should not have committed
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_seed_force_reseed():
    """force=True clears and re-seeds."""
    from src.services.seed.seeder import seed_demo_data

    session = AsyncMock()
    compliance_session = AsyncMock()

    # Existing manifest on first call, then cleared
    manifest = MagicMock()
    manifest.seeded_at = datetime(2026, 1, 1, 0, 0, 0)
    manifest.config_hash = "abc123"

    call_count = [0]

    async def mock_execute(stmt):
        call_count[0] += 1
        mock_result = MagicMock()
        # First execute is the manifest check; return existing manifest
        if call_count[0] == 1:
            mock_result.scalar_one_or_none.return_value = manifest
            mock_result.scalars.return_value.all.return_value = []
        else:
            mock_result.scalar_one_or_none.return_value = None
            mock_result.scalars.return_value.all.return_value = []
        return mock_result

    session.execute = AsyncMock(side_effect=mock_execute)

    added_objects = []

    def track_add(obj):
        added_objects.append(obj)
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = len(added_objects)

    session.add = MagicMock(side_effect=track_add)

    async def fake_flush():
        for obj in added_objects:
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = len(added_objects) + 1

    session.flush = fake_flush
    compliance_session.add = MagicMock()

    mock_engine = MagicMock()
    mock_engine.begin = _mock_engine_begin
    with patch("db.database.engine", mock_engine):
        result = await seed_demo_data(session, compliance_session, force=True)

    assert result["status"] == "seeded"
    session.commit.assert_awaited_once()
    compliance_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Admin endpoint tests
# ---------------------------------------------------------------------------


def test_seed_status_endpoint_not_seeded():
    """GET /api/admin/seed/status returns seeded=false when not seeded."""
    app = _make_app()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def fake_db():
        yield mock_session

    async def fake_compliance_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_compliance_db] = fake_compliance_db

    client = TestClient(app)
    response = client.get("/api/admin/seed/status")

    assert response.status_code == 200
    assert response.json()["seeded"] is False


def test_seed_status_endpoint_seeded():
    """GET /api/admin/seed/status returns seeded=true with details."""
    app = _make_app()

    mock_session = AsyncMock()
    manifest = MagicMock()
    manifest.seeded_at = datetime(2026, 2, 24, 12, 0, 0)
    manifest.config_hash = "abc123def456"
    manifest.summary = json.dumps({"borrowers": 6, "active_applications": 8})

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = manifest
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def fake_db():
        yield mock_session

    async def fake_compliance_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_compliance_db] = fake_compliance_db

    client = TestClient(app)
    response = client.get("/api/admin/seed/status")

    assert response.status_code == 200
    data = response.json()
    assert data["seeded"] is True
    assert data["config_hash"] == "abc123def456"
    assert data["summary"]["borrowers"] == 6


def test_borrower_cannot_seed(monkeypatch):
    """Borrower role gets 403 on seed endpoint."""
    from src.core.config import settings

    monkeypatch.setattr(settings, "AUTH_DISABLED", False)

    borrower = UserContext(
        user_id="borrower-1",
        role=UserRole.BORROWER,
        email="borrower@example.com",
        name="Test Borrower",
        data_scope=DataScope(own_data_only=True, user_id="borrower-1"),
    )
    app = _make_app(user=borrower)

    async def fake_db():
        yield AsyncMock()

    async def fake_compliance_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_compliance_db] = fake_compliance_db

    client = TestClient(app)
    response = client.post("/api/admin/seed")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# HMDA seeding tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_hmda_demographics():
    """seed_hmda_demographics creates correct number of records."""
    from src.services.compliance.seed_hmda import seed_hmda_demographics

    compliance_session = AsyncMock()
    compliance_session.add = MagicMock()

    demo_data = [
        {
            "application_id": i,
            "race": "White",
            "ethnicity": "Not Hispanic or Latino",
            "sex": "Male",
            "collection_method": "self_reported",
        }
        for i in range(10)
    ]

    count = await seed_hmda_demographics(compliance_session, demo_data)
    assert count == 10
    assert compliance_session.add.call_count == 10
