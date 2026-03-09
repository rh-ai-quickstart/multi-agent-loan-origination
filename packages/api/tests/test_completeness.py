# This project was developed with assistance from AI tools.
"""Tests for document completeness service and endpoint."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from db import get_db
from db.enums import (
    ApplicationStage,
    DocumentStatus,
    DocumentType,
    EmploymentStatus,
    LoanType,
    UserRole,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.auth import get_current_user
from src.routes.documents import router
from src.schemas.auth import DataScope, UserContext
from src.services.completeness import _get_required_doc_types

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(role: UserRole = UserRole.BORROWER, **kwargs) -> UserContext:
    """Build a UserContext for the given role."""
    defaults = {
        "user_id": "test-user",
        "email": "test@example.com",
        "name": "Test User",
        "data_scope": DataScope(own_data_only=True, user_id="test-user"),
    }
    if role == UserRole.ADMIN:
        defaults["data_scope"] = DataScope(full_pipeline=True)
    defaults.update(kwargs)
    return UserContext(role=role, **defaults)


def _make_borrower(employment_status=None):
    """Build a mock Borrower with optional employment_status."""
    b = MagicMock()
    b.id = 1
    b.employment_status = employment_status
    return b


def _make_app_borrower(borrower, is_primary=True):
    """Build a mock ApplicationBorrower junction."""
    ab = MagicMock()
    ab.borrower = borrower
    ab.is_primary = is_primary
    return ab


def _make_application(
    app_id=1,
    loan_type=LoanType.CONVENTIONAL_30,
    stage=ApplicationStage.APPLICATION,
    borrower_employment_status=None,
):
    """Build a mock Application with borrowers."""
    app = MagicMock()
    app.id = app_id
    app.loan_type = loan_type
    app.stage = stage
    borrower = _make_borrower(borrower_employment_status)
    ab = _make_app_borrower(borrower, is_primary=True)
    app.application_borrowers = [ab]
    return app


def _make_document(
    doc_id=1, doc_type=DocumentType.W2, status=DocumentStatus.UPLOADED, quality_flags=None
):
    """Build a mock Document."""
    doc = MagicMock()
    doc.id = doc_id
    doc.doc_type = doc_type
    doc.status = status
    doc.quality_flags = json.dumps(quality_flags) if quality_flags else None
    doc.created_at = datetime(2026, 1, 15, tzinfo=UTC)
    return doc


# ---------------------------------------------------------------------------
# Unit tests for _get_required_doc_types
# ---------------------------------------------------------------------------


def test_get_required_doc_types_default():
    """Default fallback returns W2 employee requirements."""
    result = _get_required_doc_types(None, None)
    assert DocumentType.W2 in result
    assert DocumentType.PAY_STUB in result
    assert DocumentType.BANK_STATEMENT in result
    assert DocumentType.ID in result


def test_get_required_doc_types_self_employed():
    """Self-employed borrowers need tax returns instead of W2/pay stubs."""
    result = _get_required_doc_types(None, EmploymentStatus.SELF_EMPLOYED.value)
    assert DocumentType.TAX_RETURN in result
    assert DocumentType.W2 not in result
    assert DocumentType.PAY_STUB not in result


def test_get_required_doc_types_unemployed():
    """Unemployed borrowers need only bank statement and ID."""
    result = _get_required_doc_types(None, EmploymentStatus.UNEMPLOYED.value)
    assert DocumentType.BANK_STATEMENT in result
    assert DocumentType.ID in result
    assert DocumentType.W2 not in result
    assert DocumentType.PAY_STUB not in result
    assert DocumentType.TAX_RETURN not in result


def test_get_required_doc_types_fallback_loan_type():
    """Unknown loan type falls back to _default requirements."""
    result = _get_required_doc_types("nonexistent_loan", EmploymentStatus.W2_EMPLOYEE.value)
    assert DocumentType.W2 in result
    assert DocumentType.ID in result


def test_get_required_doc_types_fallback_employment_status():
    """Unknown employment status falls back to _default for the loan type."""
    result = _get_required_doc_types("fha", "unknown_status")
    # Should fall back to fha._default
    assert DocumentType.TAX_RETURN in result


# ---------------------------------------------------------------------------
# Unit tests for check_completeness
# ---------------------------------------------------------------------------


@patch("src.services.completeness.get_application")
async def test_check_completeness_all_provided(mock_get_app):
    """Should return is_complete=True when all required docs exist."""
    from src.services.completeness import check_completeness

    app = _make_application(
        loan_type=LoanType.CONVENTIONAL_30, borrower_employment_status=EmploymentStatus.W2_EMPLOYEE
    )
    mock_get_app.return_value = app

    docs = [
        _make_document(doc_id=1, doc_type=DocumentType.W2),
        _make_document(doc_id=2, doc_type=DocumentType.PAY_STUB),
        _make_document(doc_id=3, doc_type=DocumentType.BANK_STATEMENT),
        _make_document(doc_id=4, doc_type=DocumentType.ID),
    ]

    session = AsyncMock()
    doc_result = MagicMock()
    doc_result.scalars.return_value.all.return_value = docs
    session.execute = AsyncMock(return_value=doc_result)

    user = _make_user(UserRole.ADMIN, data_scope=DataScope(full_pipeline=True))
    result = await check_completeness(session, user, 1)

    assert result is not None
    assert result.is_complete is True
    assert result.provided_count == 4
    assert result.required_count == 4


@patch("src.services.completeness.get_application")
async def test_check_completeness_missing_docs(mock_get_app):
    """Should return is_complete=False with missing requirements listed."""
    from src.services.completeness import check_completeness

    app = _make_application(
        loan_type=LoanType.CONVENTIONAL_30, borrower_employment_status=EmploymentStatus.W2_EMPLOYEE
    )
    mock_get_app.return_value = app

    docs = [
        _make_document(doc_id=1, doc_type=DocumentType.W2),
    ]

    session = AsyncMock()
    doc_result = MagicMock()
    doc_result.scalars.return_value.all.return_value = docs
    session.execute = AsyncMock(return_value=doc_result)

    user = _make_user(UserRole.ADMIN, data_scope=DataScope(full_pipeline=True))
    result = await check_completeness(session, user, 1)

    assert result is not None
    assert result.is_complete is False
    assert result.provided_count == 1
    assert result.required_count == 4
    missing = [r for r in result.requirements if not r.is_provided]
    assert len(missing) == 3


@patch("src.services.completeness.get_application")
async def test_check_completeness_app_not_found(mock_get_app):
    """Should return None when application is not accessible."""
    from src.services.completeness import check_completeness

    mock_get_app.return_value = None

    session = AsyncMock()
    user = _make_user(UserRole.BORROWER)
    result = await check_completeness(session, user, 999)
    assert result is None


@patch("src.services.completeness.get_application")
async def test_check_completeness_quality_flags_surfaced(mock_get_app):
    """Should include quality flags from documents in requirements."""
    from src.services.completeness import check_completeness

    app = _make_application(
        loan_type=LoanType.CONVENTIONAL_30, borrower_employment_status=EmploymentStatus.W2_EMPLOYEE
    )
    mock_get_app.return_value = app

    docs = [
        _make_document(doc_id=1, doc_type=DocumentType.W2, quality_flags=["blurry"]),
        _make_document(doc_id=2, doc_type=DocumentType.PAY_STUB),
        _make_document(doc_id=3, doc_type=DocumentType.BANK_STATEMENT),
        _make_document(doc_id=4, doc_type=DocumentType.ID),
    ]

    session = AsyncMock()
    doc_result = MagicMock()
    doc_result.scalars.return_value.all.return_value = docs
    session.execute = AsyncMock(return_value=doc_result)

    user = _make_user(UserRole.ADMIN, data_scope=DataScope(full_pipeline=True))
    result = await check_completeness(session, user, 1)

    w2_req = next(r for r in result.requirements if r.doc_type == DocumentType.W2)
    assert w2_req.quality_flags == ["blurry"]


@patch("src.services.completeness.get_application")
async def test_check_completeness_null_employment_falls_back(mock_get_app):
    """NULL employment_status should fall back to _default (W2 employee reqs)."""
    from src.services.completeness import check_completeness

    app = _make_application(
        loan_type=LoanType.CONVENTIONAL_30,
        borrower_employment_status=None,
    )
    mock_get_app.return_value = app

    session = AsyncMock()
    doc_result = MagicMock()
    doc_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=doc_result)

    user = _make_user(UserRole.ADMIN, data_scope=DataScope(full_pipeline=True))
    result = await check_completeness(session, user, 1)

    # Default should require W2, pay stub, bank statement, ID
    required_types = [r.doc_type for r in result.requirements]
    assert DocumentType.W2 in required_types
    assert DocumentType.PAY_STUB in required_types


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


def test_completeness_endpoint_404_for_missing_app():
    """GET /applications/{id}/completeness returns 404 for inaccessible app."""
    user = _make_user(UserRole.ADMIN, data_scope=DataScope(full_pipeline=True))

    app_obj = FastAPI()
    app_obj.include_router(router, prefix="/api")

    async def fake_user():
        return user

    mock_session = AsyncMock()
    app_result = MagicMock()
    app_result.unique.return_value.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=app_result)

    async def fake_db():
        yield mock_session

    app_obj.dependency_overrides[get_current_user] = fake_user
    app_obj.dependency_overrides[get_db] = fake_db

    client = TestClient(app_obj)
    response = client.get("/api/applications/999/completeness")
    assert response.status_code == 404
