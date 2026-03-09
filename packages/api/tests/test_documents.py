# This project was developed with assistance from AI tools.
"""Tests for document endpoints and CEO content restriction."""

from unittest.mock import AsyncMock, MagicMock

from db import get_db
from db.enums import DocumentStatus, DocumentType, UserRole
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.auth import get_current_user
from src.routes.documents import router
from src.schemas.auth import DataScope, UserContext
from src.services.document import DocumentAccessDenied, get_document_content

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(role: UserRole, **kwargs) -> UserContext:
    """Build a UserContext for the given role."""
    defaults = {
        "user_id": "test-user",
        "email": "test@example.com",
        "name": "Test User",
        "data_scope": DataScope(full_pipeline=True),
    }
    if role == UserRole.CEO:
        defaults["data_scope"] = DataScope(
            pii_mask=True,
            document_metadata_only=True,
            full_pipeline=True,
        )
    if role == UserRole.BORROWER:
        defaults["data_scope"] = DataScope(own_data_only=True, user_id="test-user")
    defaults.update(kwargs)
    return UserContext(role=role, **defaults)


def _make_document(**overrides):
    """Build a mock Document ORM object."""
    doc = MagicMock()
    doc.id = overrides.get("id", 1)
    doc.application_id = overrides.get("application_id", 100)
    doc.doc_type = overrides.get("doc_type", DocumentType.W2)
    doc.status = overrides.get("status", DocumentStatus.UPLOADED)
    doc.quality_flags = overrides.get("quality_flags", None)
    doc.uploaded_by = overrides.get("uploaded_by", "james.torres")
    doc.file_path = overrides.get("file_path", "/uploads/w2-2024.pdf")
    doc.created_at = overrides.get("created_at", "2026-01-15T10:00:00+00:00")
    doc.updated_at = overrides.get("updated_at", "2026-01-15T10:00:00+00:00")
    return doc


def _make_app(user: UserContext, documents: list | None = None):
    """Build a test FastAPI app with document routes and mocked deps."""
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def fake_user():
        return user

    mock_session = AsyncMock()

    if documents is not None:
        mock_result = MagicMock()
        if len(documents) == 0:
            mock_result.scalar.return_value = 0
            mock_result.unique.return_value.scalar_one_or_none.return_value = None
            mock_result.unique.return_value.scalars.return_value.all.return_value = []
        elif len(documents) == 1:
            mock_result.scalar.return_value = 1
            mock_result.unique.return_value.scalar_one_or_none.return_value = documents[0]
            mock_result.unique.return_value.scalars.return_value.all.return_value = documents
        else:
            mock_result.scalar.return_value = len(documents)
            mock_result.unique.return_value.scalar_one_or_none.return_value = documents[0]
            mock_result.unique.return_value.scalars.return_value.all.return_value = documents
        mock_session.execute = AsyncMock(return_value=mock_result)

    async def fake_db():
        yield mock_session

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db
    return app


# ---------------------------------------------------------------------------
# CEO restriction tests
# ---------------------------------------------------------------------------


def test_ceo_get_document_excludes_file_path():
    """CEO gets metadata only -- no file_path in response."""
    ceo = _make_user(UserRole.CEO)
    doc = _make_document(file_path="/uploads/secret.pdf")
    app = _make_app(ceo, documents=[doc])
    client = TestClient(app)

    response = client.get("/api/applications/100/documents/1")
    assert response.status_code == 200
    data = response.json()
    assert data["file_path"] is None
    assert data["doc_type"] == DocumentType.W2.value
    assert data["status"] == DocumentStatus.UPLOADED.value


def test_ceo_content_endpoint_returns_403(monkeypatch):
    """CEO is blocked from /documents/{id}/content at route level."""
    from src.core.config import settings

    monkeypatch.setattr(settings, "AUTH_DISABLED", False)

    ceo = _make_user(UserRole.CEO)
    doc = _make_document()
    app = _make_app(ceo, documents=[doc])
    client = TestClient(app)

    response = client.get("/api/applications/100/documents/1/content")
    assert response.status_code == 403


def test_ceo_service_layer_blocks_content():
    """Service-level enforcement: get_document_content raises for CEO."""
    ceo = _make_user(UserRole.CEO)
    doc = _make_document(file_path="/uploads/w2.pdf")

    try:
        get_document_content(ceo, doc)
        assert False, "Should have raised DocumentAccessDenied"
    except DocumentAccessDenied:
        pass


# ---------------------------------------------------------------------------
# Non-CEO access tests
# ---------------------------------------------------------------------------


def test_loan_officer_gets_full_document():
    """Loan officer gets document with file_path included."""
    lo = _make_user(UserRole.LOAN_OFFICER, data_scope=DataScope(assigned_to="test-user"))
    doc = _make_document(file_path="/uploads/paystub.pdf")
    app = _make_app(lo, documents=[doc])
    client = TestClient(app)

    response = client.get("/api/applications/100/documents/1")
    assert response.status_code == 200
    data = response.json()
    assert data["file_path"] == "/uploads/paystub.pdf"


def test_loan_officer_content_endpoint_succeeds():
    """Loan officer can access /documents/{id}/content."""
    lo = _make_user(UserRole.LOAN_OFFICER, data_scope=DataScope(assigned_to="test-user"))
    doc = _make_document(file_path="/uploads/paystub.pdf")
    app = _make_app(lo, documents=[doc])
    client = TestClient(app)

    response = client.get("/api/applications/100/documents/1/content")
    assert response.status_code == 200
    assert response.json()["file_path"] == "/uploads/paystub.pdf"


def test_service_layer_allows_non_ceo_content():
    """Service-level enforcement allows non-CEO roles."""
    lo = _make_user(UserRole.LOAN_OFFICER)
    doc = _make_document(file_path="/uploads/w2.pdf")
    result = get_document_content(lo, doc)
    assert result == "/uploads/w2.pdf"


# ---------------------------------------------------------------------------
# List endpoint tests
# ---------------------------------------------------------------------------


def test_list_documents_returns_metadata_only():
    """List endpoint returns metadata schema (no file_path) for all roles."""
    admin = _make_user(UserRole.ADMIN)
    docs = [_make_document(id=i) for i in range(3)]
    app = _make_app(admin, documents=docs)
    client = TestClient(app)

    response = client.get("/api/applications/100/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 3
    assert len(data["data"]) == 3
    for item in data["data"]:
        assert "file_path" not in item


# ---------------------------------------------------------------------------
# 404 tests
# ---------------------------------------------------------------------------


def test_get_nonexistent_document_returns_404():
    """Requesting a missing document returns 404."""
    admin = _make_user(UserRole.ADMIN)
    app = _make_app(admin, documents=[])
    client = TestClient(app)

    response = client.get("/api/applications/100/documents/999")
    assert response.status_code == 404


def test_content_nonexistent_document_returns_404():
    """Requesting content of a missing document returns 404."""
    admin = _make_user(UserRole.ADMIN)
    app = _make_app(admin, documents=[])
    client = TestClient(app)

    response = client.get("/api/applications/100/documents/999/content")
    assert response.status_code == 404
