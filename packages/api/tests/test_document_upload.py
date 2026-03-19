# This project was developed with assistance from AI tools.
"""Tests for the document upload endpoint."""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

from db import get_db
from db.enums import DocumentStatus, DocumentType, UserRole
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.auth import get_current_user
from src.routes.documents import router
from src.schemas.auth import DataScope, UserContext

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
    if role == UserRole.BORROWER:
        defaults["data_scope"] = DataScope(own_data_only=True, user_id="test-user")
    defaults.update(kwargs)
    return UserContext(role=role, **defaults)


def _make_mock_application(app_id: int = 100):
    """Build a mock Application ORM object."""
    app = MagicMock()
    app.id = app_id
    return app


def _make_mock_document(**overrides):
    """Build a mock Document ORM object with upload-relevant fields."""
    doc = MagicMock()
    doc.id = overrides.get("id", 1)
    doc.application_id = overrides.get("application_id", 100)
    doc.doc_type = overrides.get("doc_type", DocumentType.W2)
    doc.status = overrides.get("status", DocumentStatus.PROCESSING)
    doc.file_path = overrides.get("file_path", "100/1/test.pdf")
    doc.quality_flags = None
    doc.uploaded_by = overrides.get("uploaded_by", "test-user")
    doc.created_at = overrides.get("created_at", "2026-02-24T10:00:00+00:00")
    doc.updated_at = overrides.get("updated_at", "2026-02-24T10:00:00+00:00")
    return doc


def _make_upload_app(user: UserContext, *, app_found: bool = True):
    """Build a test FastAPI app with upload route and mocked deps."""
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def fake_user():
        return user

    mock_session = AsyncMock()

    if app_found:
        mock_app = _make_mock_application()
        # First execute: app lookup (uses .unique().scalar_one_or_none())
        app_result = MagicMock()
        app_result.unique.return_value.scalar_one_or_none.return_value = mock_app
        # Second execute: primary borrower lookup (uses .scalar_one_or_none())
        borrower_result = MagicMock()
        borrower_result.scalar_one_or_none.return_value = 1  # primary borrower_id
        mock_session.execute = AsyncMock(side_effect=[app_result, borrower_result])
    else:
        mock_result = MagicMock()
        mock_result.unique.return_value.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

    # flush assigns an id to the document
    async def fake_flush():
        pass

    mock_session.flush = fake_flush
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    async def fake_db():
        yield mock_session

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db
    return app, mock_session


def _upload_file(client, content_type="application/pdf", filename="test.pdf", data=None):
    """POST a file to the upload endpoint."""
    if data is None:
        data = b"%PDF-1.4 fake content"
    return client.post(
        "/api/applications/100/documents",
        files={"file": (filename, BytesIO(data), content_type)},
        data={"doc_type": "w2"},
    )


# ---------------------------------------------------------------------------
# Upload success
# ---------------------------------------------------------------------------


@patch("src.routes.documents.get_extraction_service")
@patch("src.routes.documents.asyncio.create_task")
@patch("src.services.document.get_storage_service")
@patch("src.services.document.write_audit_event", new_callable=AsyncMock)
def test_upload_document_success(
    mock_audit, mock_get_storage, mock_create_task, mock_get_extraction
):
    """Happy path: multipart upload creates DB record and uploads to S3."""
    mock_storage = MagicMock()
    mock_storage.build_object_key.return_value = "100/1/test.pdf"
    mock_storage.upload_file = AsyncMock(return_value="100/1/test.pdf")
    mock_get_storage.return_value = mock_storage

    mock_extraction_svc = MagicMock()
    mock_extraction_svc.process_document = AsyncMock()
    mock_get_extraction.return_value = mock_extraction_svc

    user = _make_user(UserRole.BORROWER)
    app, mock_session = _make_upload_app(user)

    # After session.add and flush, the document should have an id
    original_add = mock_session.add

    def tracked_add(obj):
        obj.id = 1
        obj.created_at = "2026-02-24T10:00:00+00:00"
        obj.updated_at = "2026-02-24T10:00:00+00:00"
        original_add(obj)

    mock_session.add = tracked_add

    client = TestClient(app)
    response = _upload_file(client)

    assert response.status_code == 201
    data = response.json()
    assert data["application_id"] == 100
    assert data["doc_type"] == DocumentType.W2.value
    assert data["status"] == DocumentStatus.PROCESSING.value

    # Verify S3 was called
    mock_storage.upload_file.assert_called_once()

    # Verify background extraction was dispatched
    mock_create_task.assert_called_once()


# ---------------------------------------------------------------------------
# Validation failures
# ---------------------------------------------------------------------------


@patch("src.services.document.get_storage_service")
def test_upload_rejects_invalid_content_type(mock_get_storage):
    """Content-type validation rejects unsupported file types."""
    user = _make_user(UserRole.BORROWER)
    app, _ = _make_upload_app(user)
    client = TestClient(app)

    response = _upload_file(client, content_type="text/plain", filename="readme.txt")
    assert response.status_code == 422


@patch("src.services.document.get_storage_service")
def test_upload_rejects_oversized_file(mock_get_storage):
    """Size validation rejects files exceeding UPLOAD_MAX_SIZE_MB."""
    mock_storage = MagicMock()
    mock_storage.build_object_key.return_value = "100/1/big.pdf"
    mock_storage.upload_file = AsyncMock(return_value="100/1/big.pdf")
    mock_get_storage.return_value = mock_storage

    user = _make_user(UserRole.BORROWER)
    app, mock_session = _make_upload_app(user)

    # Patch the setting to a tiny limit for testing
    original_add = mock_session.add

    def tracked_add(obj):
        obj.id = 1
        obj.created_at = "2026-02-24T10:00:00+00:00"
        obj.updated_at = "2026-02-24T10:00:00+00:00"
        original_add(obj)

    mock_session.add = tracked_add

    client = TestClient(app)

    # Create data just over 50MB
    oversized_data = b"%PDF-1.4 " + b"x" * (50 * 1024 * 1024 + 1)
    response = _upload_file(client, data=oversized_data)
    assert response.status_code == 413


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


@patch("src.services.document.get_storage_service")
def test_upload_application_not_found(mock_get_storage):
    """Data scope filters out non-owned application -> 404."""
    mock_storage = MagicMock()
    mock_get_storage.return_value = mock_storage

    user = _make_user(UserRole.BORROWER)
    app, _ = _make_upload_app(user, app_found=False)
    client = TestClient(app)

    response = _upload_file(client)
    assert response.status_code == 404
    assert "Application not found" in response.json()["detail"]


def test_upload_prospect_denied():
    """Role check rejects prospect from uploading."""
    user = _make_user(UserRole.PROSPECT)
    app, _ = _make_upload_app(user)
    client = TestClient(app)
    response = _upload_file(client)
    assert response.status_code == 403
