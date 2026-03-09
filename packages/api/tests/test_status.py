# This project was developed with assistance from AI tools.
"""Tests for application status service and endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

from db.enums import (
    ApplicationStage,
    DocumentType,
    EmploymentStatus,
    LoanType,
    UserRole,
)

from src.schemas.auth import DataScope, UserContext
from src.services.status import STAGE_INFO, get_application_status


def _make_user(role: UserRole = UserRole.ADMIN) -> UserContext:
    return UserContext(
        user_id="test-user",
        email="test@example.com",
        name="Test User",
        role=role,
        data_scope=DataScope(full_pipeline=True),
    )


def _make_borrower():
    b = MagicMock()
    b.id = 1
    b.employment_status = EmploymentStatus.W2_EMPLOYEE
    b.is_primary = True
    return b


def _make_app_borrower(borrower):
    ab = MagicMock()
    ab.borrower = borrower
    ab.borrower_id = borrower.id
    ab.is_primary = True
    return ab


def _make_application(stage=ApplicationStage.APPLICATION, loan_type=LoanType.CONVENTIONAL_30):
    app = MagicMock()
    app.id = 1
    app.stage = stage
    app.loan_type = loan_type
    borrower = _make_borrower()
    app.application_borrowers = [_make_app_borrower(borrower)]
    return app


# ---------------------------------------------------------------------------
# STAGE_INFO coverage
# ---------------------------------------------------------------------------


def test_all_stages_have_info():
    """Every ApplicationStage value has a STAGE_INFO entry."""
    for stage in ApplicationStage:
        assert stage.value in STAGE_INFO, f"Missing STAGE_INFO for {stage.value}"


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


@patch("src.services.status.get_application")
@patch("src.services.status.check_completeness")
async def test_status_with_missing_docs(mock_completeness, mock_get_app):
    """Status includes pending actions for missing documents."""
    from src.schemas.completeness import CompletenessResponse, DocumentRequirement

    mock_completeness.return_value = CompletenessResponse(
        application_id=1,
        is_complete=False,
        requirements=[
            DocumentRequirement(doc_type=DocumentType.W2, label="W-2 Form", is_provided=True),
            DocumentRequirement(
                doc_type=DocumentType.BANK_STATEMENT, label="Bank Statement", is_provided=False
            ),
        ],
        provided_count=1,
        required_count=2,
    )

    app = _make_application()
    mock_get_app.return_value = app

    session = AsyncMock()
    # Conditions count query
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    session.execute = AsyncMock(return_value=count_result)

    user = _make_user()
    result = await get_application_status(session, user, 1)

    assert result is not None
    assert result.is_document_complete is False
    assert result.provided_doc_count == 1
    assert result.required_doc_count == 2
    assert result.stage == "application"
    assert result.stage_info.label == "Application"

    upload_actions = [a for a in result.pending_actions if a.action_type == "upload_document"]
    assert len(upload_actions) == 1
    assert "Bank Statement" in upload_actions[0].description


@patch("src.services.status.get_application")
@patch("src.services.status.check_completeness")
async def test_status_with_open_conditions(mock_completeness, mock_get_app):
    """Status includes pending action for open conditions."""
    from src.schemas.completeness import CompletenessResponse

    mock_completeness.return_value = CompletenessResponse(
        application_id=1,
        is_complete=True,
        requirements=[],
        provided_count=4,
        required_count=4,
    )

    app = _make_application(stage=ApplicationStage.CONDITIONAL_APPROVAL)
    mock_get_app.return_value = app

    session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 3
    session.execute = AsyncMock(return_value=count_result)

    user = _make_user()
    result = await get_application_status(session, user, 1)

    assert result is not None
    assert result.open_condition_count == 3
    assert result.stage == "conditional_approval"

    cond_actions = [a for a in result.pending_actions if a.action_type == "clear_conditions"]
    assert len(cond_actions) == 1
    assert "3" in cond_actions[0].description


@patch("src.services.status.get_application")
@patch("src.services.status.check_completeness")
async def test_status_terminal_stage_no_actions(mock_completeness, mock_get_app):
    """Terminal stages (closed/denied/withdrawn) have no pending actions."""
    from src.schemas.completeness import CompletenessResponse

    mock_completeness.return_value = CompletenessResponse(
        application_id=1,
        is_complete=True,
        requirements=[],
        provided_count=4,
        required_count=4,
    )

    app = _make_application(stage=ApplicationStage.CLOSED)
    mock_get_app.return_value = app

    session = AsyncMock()
    user = _make_user()
    result = await get_application_status(session, user, 1)

    assert result is not None
    assert result.stage == "closed"
    assert result.pending_actions == []
    assert result.open_condition_count == 0


@patch("src.services.status.check_completeness")
async def test_status_app_not_found(mock_completeness):
    """Returns None when completeness returns None (app not accessible)."""
    mock_completeness.return_value = None

    session = AsyncMock()
    user = _make_user(UserRole.BORROWER)
    result = await get_application_status(session, user, 999)

    assert result is None


@patch("src.services.status.get_application")
@patch("src.services.status.check_completeness")
async def test_status_quality_flags_generate_resubmit_action(mock_completeness, mock_get_app):
    """Documents with quality flags produce resubmit pending actions."""
    from src.schemas.completeness import CompletenessResponse, DocumentRequirement

    mock_completeness.return_value = CompletenessResponse(
        application_id=1,
        is_complete=True,
        requirements=[
            DocumentRequirement(
                doc_type=DocumentType.W2,
                label="W-2 Form",
                is_provided=True,
                quality_flags=["blurry"],
            ),
        ],
        provided_count=1,
        required_count=1,
    )

    app = _make_application()
    mock_get_app.return_value = app

    session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    session.execute = AsyncMock(return_value=count_result)

    user = _make_user()
    result = await get_application_status(session, user, 1)

    resubmit = [a for a in result.pending_actions if a.action_type == "resubmit_document"]
    assert len(resubmit) == 1
    assert "blurry" in resubmit[0].description
