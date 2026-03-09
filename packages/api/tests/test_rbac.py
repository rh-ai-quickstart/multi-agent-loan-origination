# This project was developed with assistance from AI tools.
"""Tests for RBAC enforcement on application routes and PII masking."""

from src.middleware.pii import mask_application_pii, mask_dob, mask_ssn

# ---------------------------------------------------------------------------
# PII masking
# ---------------------------------------------------------------------------


def test_mask_ssn_standard_format():
    """SSN masked to ***-**-NNNN with last 4 visible."""
    assert mask_ssn("123-45-6789") == "***-**-6789"


def test_mask_dob_iso_datetime():
    """DOB masked to YYYY-**-** with only year visible."""
    assert mask_dob("1990-03-15T00:00:00") == "1990-**-**"


def test_mask_application_pii_masks_borrowers_list():
    """Application-level masking applies to borrowers list."""
    app_dict = {
        "id": 1,
        "borrowers": [
            {
                "id": 10,
                "first_name": "Sarah",
                "last_name": "Mitchell",
                "ssn": "123-45-6789",
                "dob": "1990-03-15T00:00:00",
                "email": "sarah@example.com",
                "is_primary": True,
            },
            {
                "id": 11,
                "first_name": "Jennifer",
                "last_name": "Mitchell",
                "ssn": "987-65-4321",
                "dob": "1992-08-22T00:00:00",
                "email": "jennifer@example.com",
                "is_primary": False,
            },
        ],
        "stage": "inquiry",
    }
    masked = mask_application_pii(app_dict)
    # Names stay visible
    assert masked["borrowers"][0]["first_name"] == "Sarah"
    assert masked["borrowers"][1]["first_name"] == "Jennifer"
    # PII is masked
    assert masked["borrowers"][0]["ssn"] == "***-**-6789"
    assert masked["borrowers"][0]["dob"] == "1990-**-**"
    assert masked["borrowers"][1]["ssn"] == "***-**-4321"
    assert masked["borrowers"][1]["dob"] == "1992-**-**"
    # Original not mutated
    assert app_dict["borrowers"][0]["ssn"] == "123-45-6789"


# ---------------------------------------------------------------------------
# Route-level RBAC
# ---------------------------------------------------------------------------


def test_prospect_cannot_access_applications(monkeypatch):
    """Prospect role gets 403 on application routes."""
    from db.enums import UserRole
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.core.config import settings
    from src.middleware.auth import get_current_user
    from src.schemas.auth import DataScope, UserContext

    monkeypatch.setattr(settings, "AUTH_DISABLED", False)

    app = FastAPI()

    prospect = UserContext(
        user_id="prospect-1",
        role=UserRole.PROSPECT,
        email="visitor@example.com",
        name="Visitor",
        data_scope=DataScope(),
    )

    async def fake_user():
        return prospect

    from src.routes.applications import router

    app.include_router(router, prefix="/api/applications")
    app.dependency_overrides[get_current_user] = fake_user

    client = TestClient(app)
    resp = client.get("/api/applications/")
    assert resp.status_code == 403


def test_co_borrower_sees_shared_application(monkeypatch):
    """Co-borrower (non-primary) sees application via junction table scope."""
    from unittest.mock import AsyncMock, MagicMock

    from db import get_db
    from db.enums import ApplicationStage, LoanType, UserRole
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.core.config import settings
    from src.middleware.auth import get_current_user
    from src.routes.applications import router
    from src.schemas.auth import DataScope, UserContext

    monkeypatch.setattr(settings, "AUTH_DISABLED", False)

    # Co-borrower (not the primary on this app)
    co_borrower = UserContext(
        user_id="coborrower-1",
        role=UserRole.BORROWER,
        email="coborrower@example.com",
        name="Co-Borrower",
        data_scope=DataScope(own_data_only=True, user_id="coborrower-1"),
    )

    app = FastAPI()
    app.include_router(router, prefix="/api/applications")

    async def fake_user():
        return co_borrower

    mock_session = AsyncMock()

    # Build mock application with both primary and co-borrower in junction table
    mock_app = MagicMock()
    mock_app.id = 101
    mock_app.stage = ApplicationStage.APPLICATION
    mock_app.loan_type = LoanType.CONVENTIONAL_30
    mock_app.property_address = "123 Test St"
    mock_app.loan_amount = 300000
    mock_app.property_value = 400000
    mock_app.assigned_to = None
    mock_app.created_at = "2026-01-01T00:00:00+00:00"
    mock_app.updated_at = "2026-01-01T00:00:00+00:00"

    # Junction entries: primary + co-borrower
    primary_borrower = MagicMock()
    primary_borrower.id = 1
    primary_borrower.first_name = "Primary"
    primary_borrower.last_name = "Borrower"
    primary_borrower.email = "primary@example.com"
    primary_borrower.ssn = None
    primary_borrower.dob = None
    primary_borrower.employment_status = None

    co_borrower_obj = MagicMock()
    co_borrower_obj.id = 2
    co_borrower_obj.first_name = "Co"
    co_borrower_obj.last_name = "Borrower"
    co_borrower_obj.email = "coborrower@example.com"
    co_borrower_obj.ssn = None
    co_borrower_obj.dob = None
    co_borrower_obj.employment_status = None

    ab_primary = MagicMock()
    ab_primary.borrower = primary_borrower
    ab_primary.is_primary = True

    ab_co = MagicMock()
    ab_co.borrower = co_borrower_obj
    ab_co.is_primary = False

    mock_app.application_borrowers = [ab_primary, ab_co]
    mock_app.financials = None

    # Mock session returns: count=1, then the app
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    list_result = MagicMock()
    list_result.unique.return_value.scalars.return_value.all.return_value = [mock_app]
    mock_session.execute = AsyncMock(side_effect=[count_result, list_result])

    async def fake_db():
        yield mock_session

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db

    client = TestClient(app)
    resp = client.get("/api/applications/")
    assert resp.status_code == 200

    data = resp.json()
    assert data["pagination"]["total"] == 1
    apps = data["data"]
    assert len(apps) == 1
    assert apps[0]["id"] == 101
    # Both borrowers in list with correct is_primary flags
    borrowers = apps[0]["borrowers"]
    assert len(borrowers) == 2
    primary_list = [b for b in borrowers if b["is_primary"]]
    co_list = [b for b in borrowers if not b["is_primary"]]
    assert len(primary_list) == 1
    assert len(co_list) == 1
    assert co_list[0]["first_name"] == "Co"


def test_borrower_cannot_patch_application(monkeypatch):
    """Borrowers can view but not update applications."""
    from db.enums import UserRole
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.core.config import settings
    from src.middleware.auth import get_current_user
    from src.schemas.auth import DataScope, UserContext

    monkeypatch.setattr(settings, "AUTH_DISABLED", False)

    app = FastAPI()

    borrower = UserContext(
        user_id="borrower-1",
        role=UserRole.BORROWER,
        email="borrower@example.com",
        name="Test Borrower",
        data_scope=DataScope(own_data_only=True, user_id="borrower-1"),
    )

    async def fake_user():
        return borrower

    from src.routes.applications import router

    app.include_router(router, prefix="/api/applications")
    app.dependency_overrides[get_current_user] = fake_user

    client = TestClient(app)
    resp = client.patch("/api/applications/1", json={"property_address": "123 Main St"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Co-borrower management endpoints
# ---------------------------------------------------------------------------


def _make_coborrower_test_app(user, mock_session):
    """Build a test app with mocked auth + db for co-borrower endpoint tests."""
    from db import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.middleware.auth import get_current_user
    from src.routes.applications import router

    app = FastAPI()
    app.include_router(router, prefix="/api/applications")

    async def fake_user():
        return user

    async def fake_db():
        yield mock_session

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db

    return TestClient(app)


def test_add_borrower_to_application(monkeypatch):
    """Loan officer can add a co-borrower to an application."""
    from unittest.mock import AsyncMock, MagicMock

    from db.enums import ApplicationStage, LoanType, UserRole

    from src.core.config import settings
    from src.schemas.auth import DataScope, UserContext

    monkeypatch.setattr(settings, "AUTH_DISABLED", False)

    loan_officer = UserContext(
        user_id="lo-1",
        role=UserRole.LOAN_OFFICER,
        email="lo@example.com",
        name="Loan Officer",
        data_scope=DataScope(assigned_to="lo-1"),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    # Build a mock app with one existing borrower
    mock_borrower = MagicMock()
    mock_borrower.id = 1
    mock_borrower.first_name = "Primary"
    mock_borrower.last_name = "Borrower"
    mock_borrower.email = "primary@example.com"
    mock_borrower.ssn = None
    mock_borrower.dob = None
    mock_borrower.employment_status = None

    ab_primary = MagicMock()
    ab_primary.borrower = mock_borrower
    ab_primary.is_primary = True

    mock_app = MagicMock()
    mock_app.id = 1
    mock_app.stage = ApplicationStage.APPLICATION
    mock_app.loan_type = LoanType.CONVENTIONAL_30
    mock_app.property_address = "123 Test St"
    mock_app.loan_amount = 300000
    mock_app.property_value = 400000
    mock_app.assigned_to = "lo-1"
    mock_app.created_at = "2026-01-01T00:00:00+00:00"
    mock_app.updated_at = "2026-01-01T00:00:00+00:00"
    mock_app.application_borrowers = [ab_primary]

    # New borrower to add
    new_borrower = MagicMock()
    new_borrower.id = 2
    new_borrower.first_name = "Co"
    new_borrower.last_name = "Borrower"
    new_borrower.email = "co@example.com"
    new_borrower.ssn = None
    new_borrower.dob = None
    new_borrower.employment_status = None

    ab_co = MagicMock()
    ab_co.borrower = new_borrower
    ab_co.is_primary = False

    mock_app_after = MagicMock()
    mock_app_after.id = 1
    mock_app_after.stage = ApplicationStage.APPLICATION
    mock_app_after.loan_type = LoanType.CONVENTIONAL_30
    mock_app_after.property_address = "123 Test St"
    mock_app_after.loan_amount = 300000
    mock_app_after.property_value = 400000
    mock_app_after.assigned_to = "lo-1"
    mock_app_after.created_at = "2026-01-01T00:00:00+00:00"
    mock_app_after.updated_at = "2026-01-01T00:00:00+00:00"
    mock_app_after.application_borrowers = [ab_primary, ab_co]

    call_count = [0]

    async def mock_execute(stmt):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # get_application query
            result.unique.return_value.scalar_one_or_none.return_value = mock_app
        elif call_count[0] == 2:
            # borrower existence check
            result.scalar_one_or_none.return_value = new_borrower
        elif call_count[0] == 3:
            # duplicate junction check
            result.scalar_one_or_none.return_value = None
        else:
            # post-commit get_application
            result.unique.return_value.scalar_one_or_none.return_value = mock_app_after
        return result

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    client = _make_coborrower_test_app(loan_officer, mock_session)
    resp = client.post(
        "/api/applications/1/borrowers",
        json={"borrower_id": 2, "is_primary": False},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["borrowers"]) == 2


def test_remove_borrower_from_application(monkeypatch):
    """Loan officer can remove a non-primary co-borrower."""
    from unittest.mock import AsyncMock, MagicMock

    from db.enums import ApplicationStage, LoanType, UserRole

    from src.core.config import settings
    from src.schemas.auth import DataScope, UserContext

    monkeypatch.setattr(settings, "AUTH_DISABLED", False)

    loan_officer = UserContext(
        user_id="lo-1",
        role=UserRole.LOAN_OFFICER,
        email="lo@example.com",
        name="Loan Officer",
        data_scope=DataScope(assigned_to="lo-1"),
    )

    mock_session = AsyncMock()

    mock_borrower = MagicMock()
    mock_borrower.id = 1
    mock_borrower.first_name = "Primary"
    mock_borrower.last_name = "Borrower"
    mock_borrower.email = "primary@example.com"
    mock_borrower.ssn = None
    mock_borrower.dob = None
    mock_borrower.employment_status = None

    ab_primary = MagicMock()
    ab_primary.borrower = mock_borrower
    ab_primary.is_primary = True

    mock_app = MagicMock()
    mock_app.id = 1
    mock_app.stage = ApplicationStage.APPLICATION
    mock_app.loan_type = LoanType.CONVENTIONAL_30
    mock_app.property_address = "123 Test St"
    mock_app.loan_amount = 300000
    mock_app.property_value = 400000
    mock_app.assigned_to = "lo-1"
    mock_app.created_at = "2026-01-01T00:00:00+00:00"
    mock_app.updated_at = "2026-01-01T00:00:00+00:00"
    mock_app.application_borrowers = [ab_primary]

    # Junction row for co-borrower to remove
    junction = MagicMock()
    junction.is_primary = False

    call_count = [0]

    async def mock_execute(stmt):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # get_application
            result.unique.return_value.scalar_one_or_none.return_value = mock_app
        elif call_count[0] == 2:
            # find junction row
            result.scalar_one_or_none.return_value = junction
        elif call_count[0] == 3:
            # count borrowers (2 before removal)
            result.scalar.return_value = 2
        else:
            # post-delete get_application
            result.unique.return_value.scalar_one_or_none.return_value = mock_app
        return result

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    client = _make_coborrower_test_app(loan_officer, mock_session)
    resp = client.delete("/api/applications/1/borrowers/2")
    assert resp.status_code == 200


def test_cannot_remove_last_borrower(monkeypatch):
    """Attempting to remove the sole remaining borrower returns 400."""
    from unittest.mock import AsyncMock, MagicMock

    from db.enums import ApplicationStage, UserRole

    from src.core.config import settings
    from src.schemas.auth import DataScope, UserContext

    monkeypatch.setattr(settings, "AUTH_DISABLED", False)

    admin = UserContext(
        user_id="admin-1",
        role=UserRole.ADMIN,
        email="admin@example.com",
        name="Admin",
        data_scope=DataScope(full_pipeline=True),
    )

    mock_session = AsyncMock()

    mock_app = MagicMock()
    mock_app.id = 1
    mock_app.stage = ApplicationStage.INQUIRY
    mock_app.loan_type = None
    mock_app.property_address = None
    mock_app.loan_amount = None
    mock_app.property_value = None
    mock_app.assigned_to = None
    mock_app.created_at = "2026-01-01T00:00:00+00:00"
    mock_app.updated_at = "2026-01-01T00:00:00+00:00"
    mock_app.application_borrowers = []

    junction = MagicMock()
    junction.is_primary = False

    call_count = [0]

    async def mock_execute(stmt):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.unique.return_value.scalar_one_or_none.return_value = mock_app
        elif call_count[0] == 2:
            result.scalar_one_or_none.return_value = junction
        elif call_count[0] == 3:
            # Only 1 borrower remaining
            result.scalar.return_value = 1
        return result

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    client = _make_coborrower_test_app(admin, mock_session)
    resp = client.delete("/api/applications/1/borrowers/5")
    assert resp.status_code == 400
    assert "last borrower" in resp.json()["detail"].lower()


def test_borrower_cannot_manage_coborrowers(monkeypatch):
    """Borrower role gets 403 on co-borrower management endpoints."""
    from unittest.mock import AsyncMock

    from db.enums import UserRole

    from src.core.config import settings
    from src.schemas.auth import DataScope, UserContext

    monkeypatch.setattr(settings, "AUTH_DISABLED", False)

    borrower = UserContext(
        user_id="borrower-1",
        role=UserRole.BORROWER,
        email="borrower@example.com",
        name="Test Borrower",
        data_scope=DataScope(own_data_only=True, user_id="borrower-1"),
    )

    mock_session = AsyncMock()

    client = _make_coborrower_test_app(borrower, mock_session)

    resp = client.post(
        "/api/applications/1/borrowers",
        json={"borrower_id": 2},
    )
    assert resp.status_code == 403

    resp = client.delete("/api/applications/1/borrowers/2")
    assert resp.status_code == 403
