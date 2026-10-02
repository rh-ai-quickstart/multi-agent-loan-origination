# This project was developed with assistance from AI tools.
"""Document upload/list/get with real S4 storage."""

import io

import pytest

pytestmark = pytest.mark.integration


def _make_pdf_bytes() -> bytes:
    """Minimal valid PDF for upload tests."""
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
    )


async def test_upload_writes_to_s4(client_factory, seed_data):
    """POST upload -> Document row in DB + file retrievable from S4."""
    from unittest.mock import patch

    from src.services.storage import get_storage_service
    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    pdf = _make_pdf_bytes()

    # Patch create_task to prevent background extraction from running
    with patch("src.routes.documents.asyncio.create_task"):
        resp = await client.post(
            f"/api/applications/{seed_data.sarah_app1.id}/documents",
            files={"file": ("test.pdf", io.BytesIO(pdf), "application/pdf")},
            data={"doc_type": "w2"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["file_path"] is not None

    # Verify file exists in S4
    storage = get_storage_service()
    downloaded = await storage.download_file(data["file_path"])
    assert downloaded == pdf
    await client.aclose()


async def test_upload_resolves_primary_borrower(client_factory, seed_data):
    """Document.borrower_id = primary borrower from junction table."""
    from unittest.mock import patch

    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    pdf = _make_pdf_bytes()

    with patch("src.routes.documents.asyncio.create_task"):
        resp = await client.post(
            f"/api/applications/{seed_data.sarah_app1.id}/documents",
            files={"file": ("test.pdf", io.BytesIO(pdf), "application/pdf")},
            data={"doc_type": "bank_statement"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["borrower_id"] == seed_data.sarah.id
    await client.aclose()


async def test_upload_validates_content_type(client_factory, seed_data):
    """Upload with content_type=text/plain -> 422."""
    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.post(
        f"/api/applications/{seed_data.sarah_app1.id}/documents",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        data={"doc_type": "w2"},
    )
    assert resp.status_code == 422
    await client.aclose()


async def test_upload_validates_file_size(client_factory, seed_data):
    """Upload >50MB -> 413."""
    from unittest.mock import patch

    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    big_data = b"x" * (51 * 1024 * 1024)

    with patch("src.routes.documents.asyncio.create_task"):
        resp = await client.post(
            f"/api/applications/{seed_data.sarah_app1.id}/documents",
            files={"file": ("big.pdf", io.BytesIO(big_data), "application/pdf")},
            data={"doc_type": "w2"},
        )

    assert resp.status_code == 413
    await client.aclose()


async def test_list_documents_for_application(client_factory, seed_data):
    """Seed data has 2 docs on sarah_app1."""
    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    resp = await client.get(f"/api/applications/{seed_data.sarah_app1.id}/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pagination"]["total"] == 2
    assert len(data["data"]) == 2
    await client.aclose()


async def test_upload_nonexistent_app_returns_404(client_factory, seed_data):
    """Upload to application_id=99999 -> 404."""
    from unittest.mock import patch

    from tests.functional.personas import borrower_sarah

    client = await client_factory(borrower_sarah())
    pdf = _make_pdf_bytes()

    with patch("src.routes.documents.asyncio.create_task"):
        resp = await client.post(
            "/api/applications/99999/documents",
            files={"file": ("test.pdf", io.BytesIO(pdf), "application/pdf")},
            data={"doc_type": "w2"},
        )

    assert resp.status_code == 404
    await client.aclose()


async def test_list_documents_returns_statuses(db_session, seed_data):
    """list_documents returns documents with their processing statuses against real PG."""
    from db.enums import DocumentStatus, DocumentType
    from db.models import Document

    from src.services.document import list_documents
    from tests.functional.personas import borrower_sarah

    # Add a doc with PROCESSING_COMPLETE status
    doc3 = Document(
        application_id=seed_data.sarah_app1.id,
        borrower_id=seed_data.sarah.id,
        doc_type=DocumentType.BANK_STATEMENT,
        status=DocumentStatus.PROCESSING_COMPLETE,
        file_path="test/doc3.pdf",
        uploaded_by="sarah-uuid",
    )
    db_session.add(doc3)
    await db_session.flush()

    user = borrower_sarah()
    documents, total = await list_documents(db_session, user, seed_data.sarah_app1.id, limit=50)

    assert total == 3
    statuses = {d.doc_type: d.status for d in documents}
    assert statuses[DocumentType.BANK_STATEMENT] == DocumentStatus.PROCESSING_COMPLETE
    # Seed docs are UPLOADED
    assert statuses[DocumentType.W2] == DocumentStatus.UPLOADED


async def test_list_documents_scope_isolation(db_session, seed_data):
    """Michael cannot see Sarah's documents."""
    from src.services.document import list_documents
    from tests.functional.personas import borrower_michael

    user = borrower_michael()
    documents, total = await list_documents(db_session, user, seed_data.sarah_app1.id, limit=50)

    assert total == 0
    assert documents == []


async def test_ceo_blocked_from_document_content(client_factory, seed_data):
    """CEO GET /documents/{id}/content -> 403."""
    from tests.functional.personas import ceo

    client = await client_factory(ceo())
    resp = await client.get(
        f"/api/applications/{seed_data.sarah_app1.id}/documents/{seed_data.doc1.id}/content"
    )
    assert resp.status_code == 403
    await client.aclose()
