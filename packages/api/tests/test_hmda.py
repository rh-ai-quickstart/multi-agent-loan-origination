# This project was developed with assistance from AI tools.
"""Tests for HMDA demographic data collection, loan data snapshot, and isolation lint."""

import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db import get_compliance_db, get_db
from db.enums import LoanType, UserRole
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.auth import get_current_user
from src.routes.hmda import router
from src.schemas.auth import DataScope, UserContext

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BORROWER = UserContext(
    user_id="borrower-1",
    role=UserRole.BORROWER,
    email="borrower@example.com",
    name="Test Borrower",
    data_scope=DataScope(own_data_only=True, user_id="borrower-1"),
)


def _make_app(user: UserContext = _BORROWER):
    """Build a test app with mocked auth and db dependencies."""
    app = FastAPI()
    app.include_router(router, prefix="/api/hmda")

    async def fake_user():
        return user

    app.dependency_overrides[get_current_user] = fake_user
    return app


def _mock_sessions(
    application_exists: bool = True,
    primary_borrower_id: int | None = 10,
):
    """Create mocked lending and compliance sessions.

    Returns (app, client, lending_session, compliance_session).
    """
    app = _make_app()

    # Mock lending session -- used to verify application exists + resolve primary borrower
    lending_session = AsyncMock()

    call_count = [0]

    async def mock_execute(stmt):
        call_count[0] += 1
        mock_result = MagicMock()
        if call_count[0] == 1:
            # First call: application existence check
            mock_result.scalar_one_or_none.return_value = 1 if application_exists else None
        else:
            # Second call: primary borrower lookup
            mock_result.scalar_one_or_none.return_value = primary_borrower_id
        return mock_result

    lending_session.execute = AsyncMock(side_effect=mock_execute)

    # Mock compliance session -- used to write demographic + audit
    compliance_session = AsyncMock()
    # session.add() is synchronous in SQLAlchemy, use MagicMock to avoid warnings
    compliance_session.add = MagicMock()

    # _upsert_demographics does a SELECT -- return None (no existing row)
    upsert_result = MagicMock()
    upsert_result.scalar_one_or_none.return_value = None
    compliance_session.execute = AsyncMock(return_value=upsert_result)

    # After commit + refresh, the demographic gets an id and collected_at
    async def fake_refresh(obj):
        obj.id = 42
        obj.collected_at = datetime(2026, 2, 24, 12, 0, 0)
        if not hasattr(obj, "borrower_id") or obj.borrower_id is None:
            obj.borrower_id = primary_borrower_id

    compliance_session.refresh = fake_refresh

    async def fake_lending_db():
        yield lending_session

    async def fake_compliance_db():
        yield compliance_session

    app.dependency_overrides[get_db] = fake_lending_db
    app.dependency_overrides[get_compliance_db] = fake_compliance_db

    client = TestClient(app)
    return app, client, lending_session, compliance_session


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------


def test_collect_hmda_success():
    """POST /api/hmda/collect returns 201 with valid data."""
    _, client, _, compliance_session = _mock_sessions(application_exists=True)

    response = client.post(
        "/api/hmda/collect",
        json={
            "application_id": 1,
            "race": "White",
            "ethnicity": "Not Hispanic or Latino",
            "sex": "Female",
            "age": "35-44",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 42
    assert data["application_id"] == 1
    assert data["status"] == "collected"
    assert "collected_at" in data

    # Verify compliance session committed
    compliance_session.commit.assert_awaited_once()


def test_collect_hmda_missing_application():
    """POST /api/hmda/collect returns 404 when application doesn't exist."""
    _, client, _, _ = _mock_sessions(application_exists=False)

    response = client.post(
        "/api/hmda/collect",
        json={"application_id": 9999},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_collect_hmda_validation_error():
    """POST /api/hmda/collect returns 422 for missing required fields."""
    _, client, _, _ = _mock_sessions()

    response = client.post(
        "/api/hmda/collect",
        json={},
    )

    assert response.status_code == 422


def test_collect_hmda_partial_demographics():
    """POST /api/hmda/collect accepts partial data (only race, no ethnicity/sex)."""
    _, client, _, _ = _mock_sessions(application_exists=True)

    response = client.post(
        "/api/hmda/collect",
        json={
            "application_id": 1,
            "race": "Asian",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["application_id"] == 1
    assert data["status"] == "collected"


def test_prospect_cannot_collect_hmda(monkeypatch):
    """Prospect role gets 403 on HMDA collection."""
    from src.core.config import settings

    monkeypatch.setattr(settings, "AUTH_DISABLED", False)

    prospect = UserContext(
        user_id="prospect-1",
        role=UserRole.PROSPECT,
        email="visitor@example.com",
        name="Visitor",
        data_scope=DataScope(),
    )
    app = _make_app(user=prospect)

    async def fake_lending_db():
        yield AsyncMock()

    async def fake_compliance_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_lending_db
    app.dependency_overrides[get_compliance_db] = fake_compliance_db

    client = TestClient(app)
    response = client.post(
        "/api/hmda/collect",
        json={"application_id": 1},
    )
    assert response.status_code == 403


def test_collect_hmda_with_age():
    """POST /api/hmda/collect stores age in demographics record."""
    _, client, _, compliance_session = _mock_sessions(application_exists=True)

    response = client.post(
        "/api/hmda/collect",
        json={
            "application_id": 1,
            "race": "Asian",
            "age": "25-34",
        },
    )

    assert response.status_code == 201

    # Check the HmdaDemographic was created with age
    # First add call is from _upsert_demographics (the new record)
    hmda_call = compliance_session.add.call_args_list[0]
    hmda_obj = hmda_call[0][0]
    assert hmda_obj.age == "25-34"
    assert hmda_obj.race == "Asian"


def test_collect_hmda_with_borrower_id():
    """POST /api/hmda/collect persists borrower_id when provided."""
    _, client, _, compliance_session = _mock_sessions(application_exists=True)

    response = client.post(
        "/api/hmda/collect",
        json={
            "application_id": 1,
            "borrower_id": 99,
            "race": "White",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["borrower_id"] == 99


def test_collect_hmda_resolves_primary_borrower():
    """When borrower_id omitted, collect resolves primary borrower from junction table."""
    _, client, lending_session, _ = _mock_sessions(application_exists=True, primary_borrower_id=42)

    response = client.post(
        "/api/hmda/collect",
        json={
            "application_id": 1,
            "race": "Asian",
        },
    )

    assert response.status_code == 201
    # lending_session.execute should have been called twice (app check + primary borrower)
    assert lending_session.execute.await_count == 2


# ---------------------------------------------------------------------------
# Ownership & borrower validation tests (D9, D19)
# ---------------------------------------------------------------------------


def test_hmda_ownership_blocks_other_borrower():
    """Borrower A cannot submit HMDA data for Borrower B's application."""
    # Application existence check returns None (scoped query filters it out)
    _, client, _, _ = _mock_sessions(application_exists=False)

    response = client.post(
        "/api/hmda/collect",
        json={
            "application_id": 1,
            "race": "White",
        },
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_hmda_admin_bypasses_ownership():
    """Admin user can submit HMDA data for any application."""
    admin = UserContext(
        user_id="admin-1",
        role=UserRole.ADMIN,
        email="admin@example.com",
        name="Admin",
        data_scope=DataScope(full_pipeline=True),
    )
    app = _make_app(user=admin)
    _, client, lending_session, compliance_session = _mock_sessions(application_exists=True)

    # Override auth to use admin user
    async def fake_admin():
        return admin

    app.dependency_overrides[get_current_user] = fake_admin

    async def fake_lending_db():
        yield lending_session

    async def fake_compliance_db():
        yield compliance_session

    app.dependency_overrides[get_db] = fake_lending_db
    app.dependency_overrides[get_compliance_db] = fake_compliance_db

    client = TestClient(app)
    response = client.post(
        "/api/hmda/collect",
        json={
            "application_id": 1,
            "race": "Asian",
        },
    )

    assert response.status_code == 201


def test_hmda_invalid_borrower_id_rejected():
    """Providing a borrower_id not linked to the application returns 404."""
    app = _make_app()

    lending_session = AsyncMock()
    call_count = [0]

    async def mock_execute(stmt):
        call_count[0] += 1
        mock_result = MagicMock()
        if call_count[0] == 1:
            # First call: scoped application check -- app exists
            mock_result.scalar_one_or_none.return_value = 1
        elif call_count[0] == 2:
            # Second call: borrower_id junction validation -- not linked
            mock_result.scalar_one_or_none.return_value = None
        else:
            mock_result.scalar_one_or_none.return_value = None
        return mock_result

    lending_session.execute = AsyncMock(side_effect=mock_execute)

    compliance_session = AsyncMock()
    compliance_session.add = MagicMock()

    async def fake_lending_db():
        yield lending_session

    async def fake_compliance_db():
        yield compliance_session

    app.dependency_overrides[get_db] = fake_lending_db
    app.dependency_overrides[get_compliance_db] = fake_compliance_db

    client = TestClient(app)
    response = client.post(
        "/api/hmda/collect",
        json={
            "application_id": 1,
            "borrower_id": 999,
            "race": "White",
        },
    )

    assert response.status_code == 404
    assert "not linked" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Upsert logic tests (unit)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_no_conflict():
    """Same values twice produces 1 row and no conflicts."""
    from src.services.compliance.hmda import _upsert_demographics

    compliance_session = AsyncMock()
    compliance_session.add = MagicMock()

    # First call: no existing row
    empty_result = MagicMock()
    empty_result.scalar_one_or_none.return_value = None
    compliance_session.execute = AsyncMock(return_value=empty_result)

    methods = {"race": "self_reported", "sex": "self_reported"}
    record1, conflicts1 = await _upsert_demographics(
        compliance_session, 1, 10, {"race": "White", "sex": "Female"}, methods
    )
    assert conflicts1 == []
    assert record1.race == "White"

    # Second call: existing row returned
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = record1
    compliance_session.execute = AsyncMock(return_value=existing_result)

    record2, conflicts2 = await _upsert_demographics(
        compliance_session, 1, 10, {"race": "White", "sex": "Female"}, methods
    )
    assert conflicts2 == []
    assert record2 is record1  # same object updated in place


@pytest.mark.asyncio
async def test_upsert_with_conflict():
    """Different values produce conflicts in response."""
    from db import HmdaDemographic

    from src.services.compliance.hmda import _upsert_demographics

    compliance_session = AsyncMock()
    compliance_session.add = MagicMock()

    existing = HmdaDemographic(
        application_id=1,
        borrower_id=10,
        race="White",
        sex="Female",
        race_method="self_reported",
        sex_method="self_reported",
    )
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing
    compliance_session.execute = AsyncMock(return_value=existing_result)

    methods = {"race": "self_reported", "sex": "self_reported"}
    _, conflicts = await _upsert_demographics(
        compliance_session, 1, 10, {"race": "Asian", "sex": "Male"}, methods
    )
    assert len(conflicts) == 2
    assert conflicts[0]["field"] == "race"
    assert conflicts[0]["resolution"] == "overwritten"
    assert existing.race == "Asian"


@pytest.mark.asyncio
async def test_self_reported_overwrites_extraction():
    """self_reported has higher precedence than document_extraction."""
    from db import HmdaDemographic

    from src.services.compliance.hmda import _upsert_demographics

    compliance_session = AsyncMock()
    compliance_session.add = MagicMock()

    existing = HmdaDemographic(
        application_id=1,
        borrower_id=10,
        race="Asian",
        race_method="document_extraction",
    )
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing
    compliance_session.execute = AsyncMock(return_value=existing_result)

    _, conflicts = await _upsert_demographics(
        compliance_session, 1, 10, {"race": "White"}, {"race": "self_reported"}
    )
    assert len(conflicts) == 1
    assert conflicts[0]["resolution"] == "overwritten"
    assert existing.race == "White"
    assert existing.race_method == "self_reported"


@pytest.mark.asyncio
async def test_extraction_does_not_overwrite_self_reported():
    """document_extraction cannot overwrite self_reported values."""
    from db import HmdaDemographic

    from src.services.compliance.hmda import _upsert_demographics

    compliance_session = AsyncMock()
    compliance_session.add = MagicMock()

    existing = HmdaDemographic(
        application_id=1,
        borrower_id=10,
        race="White",
        race_method="self_reported",
    )
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing
    compliance_session.execute = AsyncMock(return_value=existing_result)

    _, conflicts = await _upsert_demographics(
        compliance_session, 1, 10, {"race": "Asian"}, {"race": "document_extraction"}
    )
    assert len(conflicts) == 1
    assert conflicts[0]["resolution"] == "kept_existing"
    assert existing.race == "White"  # unchanged
    assert existing.race_method == "self_reported"  # unchanged


@pytest.mark.asyncio
async def test_null_fields_filled_without_conflict():
    """Filling in None fields is not a conflict."""
    from db import HmdaDemographic

    from src.services.compliance.hmda import _upsert_demographics

    compliance_session = AsyncMock()
    compliance_session.add = MagicMock()

    existing = HmdaDemographic(
        application_id=1,
        borrower_id=10,
        race="White",
        ethnicity=None,
        sex=None,
        age=None,
        race_method="document_extraction",
        ethnicity_method=None,
        sex_method=None,
        age_method=None,
    )
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing
    compliance_session.execute = AsyncMock(return_value=existing_result)

    methods = {"ethnicity": "self_reported", "sex": "self_reported"}
    _, conflicts = await _upsert_demographics(
        compliance_session, 1, 10, {"ethnicity": "Not Hispanic", "sex": "Male"}, methods
    )
    assert conflicts == []
    assert existing.ethnicity == "Not Hispanic"
    assert existing.sex == "Male"


@pytest.mark.asyncio
async def test_per_field_methods_stored():
    """Each demographic field stores its collection method independently."""
    from src.services.compliance.hmda import _upsert_demographics

    compliance_session = AsyncMock()
    compliance_session.add = MagicMock()

    empty_result = MagicMock()
    empty_result.scalar_one_or_none.return_value = None
    compliance_session.execute = AsyncMock(return_value=empty_result)

    fields = {"race": "Asian", "ethnicity": "Not Hispanic", "sex": "Male", "age": "35-44"}
    methods = {
        "race": "self_reported",
        "ethnicity": "self_reported",
        "sex": "document_extraction",
        "age": "self_reported",
    }
    record, conflicts = await _upsert_demographics(compliance_session, 1, 10, fields, methods)
    assert conflicts == []
    assert record.race_method == "self_reported"
    assert record.ethnicity_method == "self_reported"
    assert record.sex_method == "document_extraction"
    assert record.age_method == "self_reported"


@pytest.mark.asyncio
async def test_mixed_method_upsert():
    """Per-field precedence: self_reported race kept, doc_extraction ethnicity overwritten."""
    from db import HmdaDemographic

    from src.services.compliance.hmda import _upsert_demographics

    compliance_session = AsyncMock()
    compliance_session.add = MagicMock()

    existing = HmdaDemographic(
        application_id=1,
        borrower_id=10,
        race="White",
        ethnicity="Hispanic",
        race_method="self_reported",
        ethnicity_method="document_extraction",
    )
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing
    compliance_session.execute = AsyncMock(return_value=existing_result)

    # Incoming: both via document_extraction
    fields = {"race": "Asian", "ethnicity": "Not Hispanic"}
    methods = {"race": "document_extraction", "ethnicity": "document_extraction"}
    _, conflicts = await _upsert_demographics(compliance_session, 1, 10, fields, methods)

    # Race: self_reported > document_extraction -> kept_existing
    # Ethnicity: document_extraction >= document_extraction -> overwritten
    assert len(conflicts) == 2
    race_conflict = next(c for c in conflicts if c["field"] == "race")
    eth_conflict = next(c for c in conflicts if c["field"] == "ethnicity")
    assert race_conflict["resolution"] == "kept_existing"
    assert eth_conflict["resolution"] == "overwritten"
    assert existing.race == "White"  # unchanged
    assert existing.ethnicity == "Not Hispanic"  # overwritten


@pytest.mark.asyncio
async def test_audit_event_data_is_dict():
    """Audit event_data is stored as a dict (JSONB), not a JSON string."""
    from src.schemas.hmda import HmdaCollectionRequest
    from src.services.compliance.hmda import collect_demographics

    lending_session = AsyncMock()
    compliance_session = AsyncMock()
    compliance_session.add = MagicMock()

    # Application exists (scoped check)
    app_result = MagicMock()
    app_result.scalar_one_or_none.return_value = 1
    # Primary borrower
    primary_result = MagicMock()
    primary_result.scalar_one_or_none.return_value = 10

    call_count = [0]

    async def mock_lending_execute(stmt):
        call_count[0] += 1
        if call_count[0] == 1:
            return app_result
        return primary_result

    lending_session.execute = AsyncMock(side_effect=mock_lending_execute)

    empty_result = MagicMock()
    empty_result.scalar_one_or_none.return_value = None
    compliance_session.execute = AsyncMock(return_value=empty_result)

    async def fake_refresh(obj):
        obj.id = 1
        obj.collected_at = datetime(2026, 2, 25, 12, 0, 0)

    compliance_session.refresh = fake_refresh

    user = UserContext(
        user_id="borrower-1",
        role=UserRole.BORROWER,
        email="b@test.com",
        name="Test",
        data_scope=DataScope(own_data_only=True, user_id="borrower-1"),
    )
    request = HmdaCollectionRequest(application_id=1, race="White")

    await collect_demographics(lending_session, compliance_session, user, request)

    # Audit event_data should be a dict, not a string
    audit_call = compliance_session.add.call_args_list[1]
    audit_obj = audit_call[0][0]
    assert isinstance(audit_obj.event_data, dict)
    assert "race_method" in audit_obj.event_data
    assert "age_method" in audit_obj.event_data


@pytest.mark.asyncio
async def test_conflicts_in_audit_trail():
    """Audit event_data includes conflicts when they occur."""
    from src.schemas.hmda import HmdaCollectionRequest
    from src.services.compliance.hmda import collect_demographics

    lending_session = AsyncMock()
    compliance_session = AsyncMock()
    compliance_session.add = MagicMock()

    # Application exists
    app_result = MagicMock()
    app_result.scalar_one_or_none.return_value = 1
    # Primary borrower
    primary_result = MagicMock()
    primary_result.scalar_one_or_none.return_value = 10

    call_count = [0]

    async def mock_lending_execute(stmt):
        call_count[0] += 1
        if call_count[0] == 1:
            return app_result
        return primary_result

    lending_session.execute = AsyncMock(side_effect=mock_lending_execute)

    # No existing demographics row
    empty_result = MagicMock()
    empty_result.scalar_one_or_none.return_value = None
    compliance_session.execute = AsyncMock(return_value=empty_result)

    async def fake_refresh(obj):
        obj.id = 1
        obj.collected_at = datetime(2026, 2, 25, 12, 0, 0)

    compliance_session.refresh = fake_refresh

    user = UserContext(
        user_id="borrower-1",
        role=UserRole.BORROWER,
        email="b@test.com",
        name="Test",
        data_scope=DataScope(own_data_only=True, user_id="borrower-1"),
    )
    request = HmdaCollectionRequest(application_id=1, race="White")

    demographic, conflicts = await collect_demographics(
        lending_session, compliance_session, user, request
    )

    assert demographic.id == 1
    assert conflicts == []

    # Audit event should include conflicts key (event_data is a dict, not JSON string)
    audit_call = compliance_session.add.call_args_list[1]
    audit_obj = audit_call[0][0]
    assert isinstance(audit_obj.event_data, dict)
    assert "conflicts" in audit_obj.event_data
    assert "borrower_id" in audit_obj.event_data


# ---------------------------------------------------------------------------
# Snapshot loan data tests
# ---------------------------------------------------------------------------


def _mock_application(
    app_id=1,
    loan_type=LoanType.CONVENTIONAL_30,
    property_address="123 Main St, Denver, CO",
):
    """Build a mock Application ORM object."""
    app = MagicMock()
    app.id = app_id
    app.loan_type = loan_type
    app.property_address = property_address
    return app


def _mock_financials(
    app_id=1,
    gross_monthly_income=Decimal("8500.00"),
    dti_ratio=0.282,
    credit_score=742,
):
    """Build a mock ApplicationFinancials ORM object."""
    fin = MagicMock()
    fin.application_id = app_id
    fin.gross_monthly_income = gross_monthly_income
    fin.dti_ratio = dti_ratio
    fin.credit_score = credit_score
    return fin


@pytest.mark.asyncio
async def test_snapshot_loan_data():
    """snapshot_loan_data copies lending data to hmda.loan_data."""
    from src.services.compliance.hmda import snapshot_loan_data

    mock_app = _mock_application()
    mock_fin = _mock_financials()

    mock_lending_session = AsyncMock()
    # First execute returns Application, second returns Financials
    app_result = MagicMock()
    app_result.scalar_one_or_none.return_value = mock_app
    fin_result = MagicMock()
    fin_result.scalar_one_or_none.return_value = mock_fin
    mock_lending_session.execute = AsyncMock(side_effect=[app_result, fin_result])

    mock_compliance_session = AsyncMock()
    mock_compliance_session.add = MagicMock()
    # No existing loan_data row
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None
    mock_compliance_session.execute = AsyncMock(return_value=existing_result)

    with (
        patch("src.services.compliance.hmda.SessionLocal") as mock_lending_cls,
        patch("src.services.compliance.hmda.ComplianceSessionLocal") as mock_compliance_cls,
    ):
        mock_lending_cls.return_value.__aenter__ = AsyncMock(return_value=mock_lending_session)
        mock_lending_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_compliance_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_compliance_session
        )
        mock_compliance_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await snapshot_loan_data(1)

    # Should have added HmdaLoanData + AuditEvent
    assert mock_compliance_session.add.call_count == 2
    mock_compliance_session.commit.assert_called_once()

    # Check the HmdaLoanData object
    loan_data_call = mock_compliance_session.add.call_args_list[0]
    loan_data_obj = loan_data_call[0][0]
    assert loan_data_obj.application_id == 1
    assert loan_data_obj.gross_monthly_income == Decimal("8500.00")
    assert loan_data_obj.credit_score == 742
    assert loan_data_obj.loan_type == "conventional_30"
    assert loan_data_obj.property_location == "123 Main St, Denver, CO"


@pytest.mark.asyncio
async def test_snapshot_loan_data_audit_event():
    """snapshot_loan_data logs an audit event with snapshot details."""
    from src.services.compliance.hmda import snapshot_loan_data

    mock_app = _mock_application()
    mock_fin = _mock_financials()

    mock_lending_session = AsyncMock()
    app_result = MagicMock()
    app_result.scalar_one_or_none.return_value = mock_app
    fin_result = MagicMock()
    fin_result.scalar_one_or_none.return_value = mock_fin
    mock_lending_session.execute = AsyncMock(side_effect=[app_result, fin_result])

    mock_compliance_session = AsyncMock()
    mock_compliance_session.add = MagicMock()
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None
    mock_compliance_session.execute = AsyncMock(return_value=existing_result)

    with (
        patch("src.services.compliance.hmda.SessionLocal") as mock_lending_cls,
        patch("src.services.compliance.hmda.ComplianceSessionLocal") as mock_compliance_cls,
    ):
        mock_lending_cls.return_value.__aenter__ = AsyncMock(return_value=mock_lending_session)
        mock_lending_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_compliance_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_compliance_session
        )
        mock_compliance_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await snapshot_loan_data(1)

    # Second add call is the AuditEvent
    audit_call = mock_compliance_session.add.call_args_list[1]
    audit_obj = audit_call[0][0]
    assert audit_obj.event_type == "hmda_loan_data_snapshot"
    assert audit_obj.application_id == 1
    assert isinstance(audit_obj.event_data, dict)
    assert "loan_type" in audit_obj.event_data["captured_fields"]
    assert "credit_score" in audit_obj.event_data["captured_fields"]
    assert "loan_purpose" in audit_obj.event_data["null_fields"]
    assert "interest_rate" in audit_obj.event_data["null_fields"]
    assert "total_fees" in audit_obj.event_data["null_fields"]
    assert audit_obj.event_data["is_update"] is False


@pytest.mark.asyncio
async def test_snapshot_loan_data_upserts():
    """Second snapshot call updates rather than duplicates."""
    from src.services.compliance.hmda import snapshot_loan_data

    mock_app = _mock_application()
    mock_fin = _mock_financials(credit_score=780)

    mock_lending_session = AsyncMock()
    app_result = MagicMock()
    app_result.scalar_one_or_none.return_value = mock_app
    fin_result = MagicMock()
    fin_result.scalar_one_or_none.return_value = mock_fin
    mock_lending_session.execute = AsyncMock(side_effect=[app_result, fin_result])

    # Simulate existing loan_data row
    existing_loan_data = MagicMock()
    existing_loan_data.application_id = 1
    existing_loan_data.credit_score = 742

    mock_compliance_session = AsyncMock()
    mock_compliance_session.add = MagicMock()
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing_loan_data
    mock_compliance_session.execute = AsyncMock(return_value=existing_result)

    with (
        patch("src.services.compliance.hmda.SessionLocal") as mock_lending_cls,
        patch("src.services.compliance.hmda.ComplianceSessionLocal") as mock_compliance_cls,
    ):
        mock_lending_cls.return_value.__aenter__ = AsyncMock(return_value=mock_lending_session)
        mock_lending_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_compliance_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_compliance_session
        )
        mock_compliance_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await snapshot_loan_data(1)

    # Should only add the AuditEvent (not a new HmdaLoanData)
    assert mock_compliance_session.add.call_count == 1
    # Existing object should have been updated
    assert existing_loan_data.credit_score == 780

    # Audit event should mark this as an update
    audit_call = mock_compliance_session.add.call_args_list[0]
    audit_obj = audit_call[0][0]
    assert isinstance(audit_obj.event_data, dict)
    assert audit_obj.event_data["is_update"] is True


@pytest.mark.asyncio
async def test_snapshot_loan_data_app_not_found():
    """snapshot_loan_data returns early when application doesn't exist."""
    from src.services.compliance.hmda import snapshot_loan_data

    mock_lending_session = AsyncMock()
    app_result = MagicMock()
    app_result.scalar_one_or_none.return_value = None  # app not found
    mock_lending_session.execute = AsyncMock(return_value=app_result)

    mock_compliance_session = AsyncMock()
    mock_compliance_session.add = MagicMock()

    with (
        patch("src.services.compliance.hmda.SessionLocal") as mock_lending_cls,
        patch("src.services.compliance.hmda.ComplianceSessionLocal") as mock_compliance_cls,
    ):
        mock_lending_cls.return_value.__aenter__ = AsyncMock(return_value=mock_lending_session)
        mock_lending_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_compliance_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_compliance_session
        )
        mock_compliance_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await snapshot_loan_data(9999)

    # Should NOT have committed anything to compliance schema
    mock_compliance_session.commit.assert_not_called()
    mock_compliance_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_snapshot_loan_data_no_financials():
    """snapshot_loan_data handles missing financials gracefully (null financial fields)."""
    from src.services.compliance.hmda import snapshot_loan_data

    mock_app = _mock_application()

    mock_lending_session = AsyncMock()
    app_result = MagicMock()
    app_result.scalar_one_or_none.return_value = mock_app
    fin_result = MagicMock()
    fin_result.scalar_one_or_none.return_value = None  # no financials
    mock_lending_session.execute = AsyncMock(side_effect=[app_result, fin_result])

    mock_compliance_session = AsyncMock()
    mock_compliance_session.add = MagicMock()
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None
    mock_compliance_session.execute = AsyncMock(return_value=existing_result)

    with (
        patch("src.services.compliance.hmda.SessionLocal") as mock_lending_cls,
        patch("src.services.compliance.hmda.ComplianceSessionLocal") as mock_compliance_cls,
    ):
        mock_lending_cls.return_value.__aenter__ = AsyncMock(return_value=mock_lending_session)
        mock_lending_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_compliance_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_compliance_session
        )
        mock_compliance_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await snapshot_loan_data(1)

    # Should still commit -- loan data with null financial fields
    mock_compliance_session.commit.assert_called_once()
    assert mock_compliance_session.add.call_count == 2  # HmdaLoanData + AuditEvent

    # HmdaLoanData should have nulls for financial fields
    loan_data_call = mock_compliance_session.add.call_args_list[0]
    loan_data_obj = loan_data_call[0][0]
    assert loan_data_obj.application_id == 1
    assert loan_data_obj.loan_type == "conventional_30"  # from Application
    assert (
        not hasattr(loan_data_obj, "gross_monthly_income")
        or getattr(loan_data_obj, "gross_monthly_income", None) is None
    )

    # Audit event should list financial fields as null
    audit_call = mock_compliance_session.add.call_args_list[1]
    audit_obj = audit_call[0][0]
    assert isinstance(audit_obj.event_data, dict)
    assert "gross_monthly_income" in audit_obj.event_data["null_fields"]
    assert "dti_ratio" in audit_obj.event_data["null_fields"]
    assert "credit_score" in audit_obj.event_data["null_fields"]


# ---------------------------------------------------------------------------
# Lint check test
# ---------------------------------------------------------------------------


def test_lint_hmda_isolation():
    """The HMDA isolation lint script passes on a clean codebase."""
    result = subprocess.run(
        ["bash", "scripts/lint-hmda-isolation.sh"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[3]),
    )
    assert result.returncode == 0, f"HMDA isolation lint failed:\n{result.stdout}\n{result.stderr}"
