# This project was developed with assistance from AI tools.
"""Tests for application intake service (S-2-F3-01 through S-2-F3-04)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.middleware.pii import mask_ssn
from src.services.intake import start_application


def _make_user(user_id="borrower-1", role="borrower"):
    """Build a mock UserContext."""
    from db.enums import UserRole

    from src.middleware.auth import build_data_scope
    from src.schemas.auth import UserContext

    r = UserRole(role)
    return UserContext(
        user_id=user_id,
        role=r,
        email=f"{user_id}@example.com",
        name=user_id,
        data_scope=build_data_scope(r, user_id),
    )


def _make_application(app_id=1, stage="application"):
    """Build a mock Application object."""
    from db.enums import ApplicationStage

    app = MagicMock()
    app.id = app_id
    app.stage = ApplicationStage(stage)
    return app


@pytest.mark.asyncio
async def test_start_application_creates_new():
    """When no active application exists, start_application creates one."""
    user = _make_user()
    new_app = _make_application(app_id=42, stage="inquiry")

    session = AsyncMock()

    with (
        patch(
            "src.services.intake.find_active_application",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "src.services.intake.create_application",
            new_callable=AsyncMock,
            return_value=new_app,
        ),
    ):
        result = await start_application(session, user)

    assert result["application_id"] == 42
    assert result["is_new"] is True
    assert result["stage"] == "inquiry"


@pytest.mark.asyncio
async def test_start_application_finds_existing():
    """When an active application exists, start_application returns it."""
    user = _make_user()
    existing_app = _make_application(app_id=10, stage="processing")

    session = AsyncMock()

    with patch(
        "src.services.intake.find_active_application",
        new_callable=AsyncMock,
        return_value=existing_app,
    ):
        result = await start_application(session, user)

    assert result["application_id"] == 10
    assert result["is_new"] is False
    assert result["stage"] == "processing"


@pytest.mark.asyncio
async def test_start_application_tool_creates_new():
    """The start_application tool creates a new app and writes an audit event."""
    from src.agents.borrower_tools import start_application as start_app_tool

    state = {"user_id": "borrower-1", "user_role": "borrower"}
    mock_session = AsyncMock()

    service_result = {
        "application_id": 99,
        "stage": "inquiry",
        "is_new": True,
    }

    with (
        patch("src.agents.borrower_tools.SessionLocal") as mock_sl,
        patch(
            "src.agents.borrower_tools.start_application_service",
            new_callable=AsyncMock,
            return_value=service_result,
        ),
        patch(
            "src.agents.borrower_tools.write_audit_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await start_app_tool.ainvoke({"state": state})

    assert "99" in response
    assert "Created new application" in response
    mock_audit.assert_called_once()
    audit_kwargs = mock_audit.call_args
    assert audit_kwargs.kwargs["event_type"] == "application_started"
    assert audit_kwargs.kwargs["application_id"] == 99
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_start_application_tool_returns_existing():
    """The start_application tool returns existing app without creating a new one."""
    from src.agents.borrower_tools import start_application as start_app_tool

    state = {"user_id": "borrower-1", "user_role": "borrower"}
    mock_session = AsyncMock()

    service_result = {
        "application_id": 10,
        "stage": "processing",
        "is_new": False,
    }

    with (
        patch("src.agents.borrower_tools.SessionLocal") as mock_sl,
        patch(
            "src.agents.borrower_tools.start_application_service",
            new_callable=AsyncMock,
            return_value=service_result,
        ),
        patch(
            "src.agents.borrower_tools.write_audit_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await start_app_tool.ainvoke({"state": state})

    assert "10" in response
    assert "already have an active application" in response
    mock_audit.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_update_tool_formats_success():
    """The update_application_data tool formats updated + remaining fields."""
    from src.agents.borrower_tools import update_application_data

    state = {"user_id": "borrower-1", "user_role": "borrower"}
    mock_session = AsyncMock()

    service_result = {
        "updated": ["gross_monthly_income", "employment_status"],
        "errors": {},
        "remaining": ["ssn", "date_of_birth"],
        "corrections": {},
    }

    with (
        patch("src.agents.borrower_tools.SessionLocal") as mock_sl,
        patch(
            "src.agents.borrower_tools.update_application_fields",
            new_callable=AsyncMock,
            return_value=service_result,
        ),
        patch("src.agents.borrower_tools.write_audit_event", new_callable=AsyncMock),
    ):
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await update_application_data.ainvoke(
            {
                "application_id": 42,
                "fields": '{"gross_monthly_income": "6250", "employment_status": "w2"}',
                "state": state,
            }
        )

    assert "gross_monthly_income" in response
    assert "employment_status" in response
    assert "Still needed" in response
    assert "ssn" in response


@pytest.mark.asyncio
async def test_update_tool_formats_validation_errors():
    """The update_application_data tool reports validation errors per field."""
    from src.agents.borrower_tools import update_application_data

    state = {"user_id": "borrower-1", "user_role": "borrower"}
    mock_session = AsyncMock()

    service_result = {
        "updated": ["email"],
        "errors": {"ssn": "SSN must be 9 digits (XXX-XX-XXXX)"},
        "remaining": ["ssn"],
        "corrections": {},
    }

    with (
        patch("src.agents.borrower_tools.SessionLocal") as mock_sl,
        patch(
            "src.agents.borrower_tools.update_application_fields",
            new_callable=AsyncMock,
            return_value=service_result,
        ),
        patch("src.agents.borrower_tools.write_audit_event", new_callable=AsyncMock),
    ):
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await update_application_data.ainvoke(
            {
                "application_id": 42,
                "fields": '{"email": "test@example.com", "ssn": "123"}',
                "state": state,
            }
        )

    assert "email" in response
    assert "Could not save ssn" in response
    assert "9 digits" in response


@pytest.mark.asyncio
async def test_update_tool_rejects_bad_json():
    """The update_application_data tool handles unparseable JSON input."""
    from src.agents.borrower_tools import update_application_data

    state = {"user_id": "borrower-1", "user_role": "borrower"}

    response = await update_application_data.ainvoke(
        {"application_id": 42, "fields": "not json at all", "state": state}
    )

    assert "Could not parse" in response


@pytest.mark.asyncio
async def test_update_tool_all_fields_complete():
    """When all fields are filled, the tool reports completion."""
    from src.agents.borrower_tools import update_application_data

    state = {"user_id": "borrower-1", "user_role": "borrower"}
    mock_session = AsyncMock()

    service_result = {
        "updated": ["credit_score"],
        "errors": {},
        "remaining": [],
        "corrections": {},
    }

    with (
        patch("src.agents.borrower_tools.SessionLocal") as mock_sl,
        patch(
            "src.agents.borrower_tools.update_application_fields",
            new_callable=AsyncMock,
            return_value=service_result,
        ),
        patch("src.agents.borrower_tools.write_audit_event", new_callable=AsyncMock),
    ):
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await update_application_data.ainvoke(
            {"application_id": 42, "fields": '{"credit_score": "750"}', "state": state}
        )

    assert "All required fields are complete" in response


# -- SSN masking --


def test_mask_ssn_full():
    """should mask all but last 4 digits of a full SSN."""
    assert mask_ssn("078-05-1120") == "***-**-1120"


def test_mask_ssn_digits_only():
    """should handle SSNs without dashes."""
    assert mask_ssn("078051120") == "***-**-1120"


def test_mask_ssn_none():
    """should return None for None, masked placeholder for empty."""
    assert mask_ssn(None) is None
    assert mask_ssn("") == "***-**-****"


# -- Field section consistency --


def test_field_sections_cover_all_required_fields():
    """_FIELD_SECTIONS must cover every field in REQUIRED_FIELDS so nothing
    silently disappears from the summary."""
    from src.services.intake import _FIELD_SECTIONS, REQUIRED_FIELDS

    section_fields = {fname for fields in _FIELD_SECTIONS.values() for fname, _ in fields}
    assert section_fields == set(REQUIRED_FIELDS.keys())


# -- get_application_progress --


@pytest.mark.asyncio
async def test_get_application_progress_partial():
    """should report correct completed/remaining counts for partial data."""
    from decimal import Decimal

    from db.enums import ApplicationStage, EmploymentStatus

    from src.services.intake import get_application_progress

    session = AsyncMock()
    user = _make_user()

    # Mock application with some fields set
    app = MagicMock()
    app.id = 42
    app.stage = ApplicationStage.APPLICATION
    app.loan_type = None
    app.property_address = "123 Main St"
    app.loan_amount = None
    app.property_value = Decimal("450000")
    app.financials = None

    borrower = MagicMock()
    borrower.first_name = "John"
    borrower.last_name = "Smith"
    borrower.email = "john@example.com"
    borrower.ssn = "078-05-1120"
    borrower.dob = None
    borrower.employment_status = EmploymentStatus.W2_EMPLOYEE

    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = app
    session.execute.return_value = mock_result

    with patch(
        "src.services.intake._get_borrower_for_app",
        new_callable=AsyncMock,
        return_value=borrower,
    ):
        progress = await get_application_progress(session, user, 42)

    assert progress is not None
    assert progress["application_id"] == 42
    assert progress["completed"] == 7  # 4 borrower + 2 property + 1 employment
    assert progress["total"] == 14
    assert "date_of_birth" in progress["remaining"]
    assert "loan_type" in progress["remaining"]

    # SSN should be masked
    personal = progress["sections"]["Personal Information"]
    assert personal["SSN"] == "***-**-1120"
    assert personal["First Name"] == "John"
    assert personal["Date of Birth"] is None


# -- get_application_summary tool --


@pytest.mark.asyncio
async def test_summary_tool_writes_audit_event():
    """The summary tool should write a data_access audit event."""
    from src.agents.borrower_tools import get_application_summary

    state = {"user_id": "borrower-1", "user_role": "borrower"}
    mock_session = AsyncMock()

    progress_result = {
        "application_id": 42,
        "stage": "application",
        "sections": {"Personal Information": {"First Name": "John"}},
        "completed": 14,
        "total": 14,
        "remaining": [],
    }

    with (
        patch("src.agents.borrower_tools.SessionLocal") as mock_sl,
        patch(
            "src.agents.borrower_tools.get_application_progress",
            new_callable=AsyncMock,
            return_value=progress_result,
        ),
        patch(
            "src.agents.borrower_tools.write_audit_event",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await get_application_summary.ainvoke({"application_id": 42, "state": state})

    # Verify audit event
    mock_audit.assert_called_once()
    audit_kwargs = mock_audit.call_args
    assert audit_kwargs.kwargs["event_type"] == "data_access"
    assert audit_kwargs.kwargs["event_data"]["action"] == "review"
    mock_session.commit.assert_called_once()
    # Verify output formatting
    assert "Application #42" in response
    assert "100%" in response
    assert "All required fields are complete" in response
