# This project was developed with assistance from AI tools.
"""Full extraction pipeline: real S4 + real pymupdf + real HMDA routing.

Only get_completion (LLM inference) is patched. Uses truncate_all fixture
because ExtractionService opens its own SessionLocal() connections.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

pytestmark = pytest.mark.integration


def _make_text_pdf() -> bytes:
    """Create a minimal PDF with actual text content for pymupdf extraction."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Employee Name: Sarah Mitchell\nGross Income: $102,000")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_scanned_pdf() -> bytes:
    """Create a PDF with no text layer (image-only) to trigger vision fallback."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    # Insert a tiny colored rect (no text layer)
    page.draw_rect(fitz.Rect(100, 100, 200, 200), color=(1, 0, 0), fill=(1, 0, 0))
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


_LLM_RESPONSE_WITH_DEMOGRAPHICS = json.dumps(
    {
        "extractions": [
            {"field_name": "gross_income", "field_value": "102000", "confidence": 0.95},
            {"field_name": "race", "field_value": "White", "confidence": 0.90},
            {"field_name": "ethnicity", "field_value": "Not Hispanic", "confidence": 0.88},
        ],
        "quality_flags": [],
        "detected_doc_type": "w2",
    }
)

_LLM_RESPONSE_NO_DEMOGRAPHICS = json.dumps(
    {
        "extractions": [
            {"field_name": "gross_income", "field_value": "102000", "confidence": 0.95},
            {"field_name": "employer_name", "field_value": "Acme Corp", "confidence": 0.92},
        ],
        "quality_flags": [],
        "detected_doc_type": "w2",
    }
)


async def _seed_and_upload(async_engine, pdf_bytes: bytes) -> int:
    """Seed a borrower + app + document with real S4 upload. Returns document ID."""
    from db.database import SessionLocal
    from db.enums import ApplicationStage, DocumentStatus, DocumentType
    from db.models import Application, ApplicationBorrower, Borrower, Document

    from src.services.storage import get_storage_service

    async with SessionLocal() as session:
        b = Borrower(
            keycloak_user_id="extract-test-user",
            first_name="Test",
            last_name="User",
            email="test@extract.com",
        )
        session.add(b)
        await session.flush()

        app = Application(stage=ApplicationStage.APPLICATION)
        session.add(app)
        await session.flush()

        session.add(
            ApplicationBorrower(
                application_id=app.id,
                borrower_id=b.id,
                is_primary=True,
            )
        )

        doc = Document(
            application_id=app.id,
            borrower_id=b.id,
            doc_type=DocumentType.W2,
            status=DocumentStatus.PROCESSING,
            uploaded_by="extract-test-user",
        )
        session.add(doc)
        await session.flush()

        # Capture IDs before session closes
        doc_id = doc.id
        app_id = app.id

        # Upload to real S4
        storage = get_storage_service()
        object_key = storage.build_object_key(app_id, doc_id, "test.pdf")
        await storage.upload_file(pdf_bytes, object_key, "application/pdf")
        doc.file_path = object_key

        await session.commit()
    return doc_id


async def test_pdf_text_extraction_calls_llm(async_engine, truncate_all):
    """Upload text PDF -> process_document -> get_completion called with text prompt."""
    from src.services.extraction import get_extraction_service

    doc_id = await _seed_and_upload(async_engine, _make_text_pdf())

    with patch(
        "src.services.extraction.get_completion",
        new_callable=AsyncMock,
        return_value=_LLM_RESPONSE_NO_DEMOGRAPHICS,
    ) as mock_llm:
        svc = get_extraction_service()
        await svc.process_document(doc_id)

    mock_llm.assert_called_once()
    call_args = mock_llm.call_args
    messages = call_args[0][0]
    # Text-based extraction uses a list of message dicts
    assert any(isinstance(m, dict) and m.get("role") == "user" for m in messages)


async def test_extraction_creates_db_rows(async_engine, truncate_all):
    """After pipeline -> DocumentExtraction rows in DB."""
    from db.database import SessionLocal
    from db.models import DocumentExtraction

    from src.services.extraction import get_extraction_service

    doc_id = await _seed_and_upload(async_engine, _make_text_pdf())

    with patch(
        "src.services.extraction.get_completion",
        new_callable=AsyncMock,
        return_value=_LLM_RESPONSE_NO_DEMOGRAPHICS,
    ):
        svc = get_extraction_service()
        await svc.process_document(doc_id)

    async with SessionLocal() as session:
        result = await session.execute(
            select(DocumentExtraction).where(DocumentExtraction.document_id == doc_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        field_names = {r.field_name for r in rows}
        assert "gross_income" in field_names


async def test_extraction_updates_status_to_complete(async_engine, truncate_all):
    """Document status transitions to PROCESSING_COMPLETE."""
    from db.database import SessionLocal
    from db.enums import DocumentStatus
    from db.models import Document

    from src.services.extraction import get_extraction_service

    doc_id = await _seed_and_upload(async_engine, _make_text_pdf())

    with patch(
        "src.services.extraction.get_completion",
        new_callable=AsyncMock,
        return_value=_LLM_RESPONSE_NO_DEMOGRAPHICS,
    ):
        svc = get_extraction_service()
        await svc.process_document(doc_id)

    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id)
        assert doc.status == DocumentStatus.PROCESSING_COMPLETE


async def test_hmda_fields_routed_to_compliance_schema(async_engine, truncate_all):
    """LLM returns race/ethnicity -> row in hmda.demographics, NOT in extractions."""
    from db.database import ComplianceSessionLocal, SessionLocal
    from db.models import DocumentExtraction, HmdaDemographic

    from src.services.extraction import get_extraction_service

    doc_id = await _seed_and_upload(async_engine, _make_text_pdf())

    with patch(
        "src.services.extraction.get_completion",
        new_callable=AsyncMock,
        return_value=_LLM_RESPONSE_WITH_DEMOGRAPHICS,
    ):
        svc = get_extraction_service()
        await svc.process_document(doc_id)

    # race/ethnicity should NOT be in document_extractions
    async with SessionLocal() as session:
        result = await session.execute(
            select(DocumentExtraction).where(DocumentExtraction.document_id == doc_id)
        )
        rows = result.scalars().all()
        field_names = {r.field_name for r in rows}
        assert "race" not in field_names
        assert "ethnicity" not in field_names
        assert "gross_income" in field_names

    # race/ethnicity SHOULD be in hmda.demographics
    async with ComplianceSessionLocal() as session:
        result = await session.execute(select(func.count(HmdaDemographic.id)))
        assert result.scalar() > 0


async def test_non_hmda_fields_stay_in_lending(async_engine, truncate_all):
    """LLM returns gross_income -> DocumentExtraction, no hmda row."""
    from db.database import ComplianceSessionLocal, SessionLocal
    from db.models import DocumentExtraction, HmdaDemographic

    from src.services.extraction import get_extraction_service

    doc_id = await _seed_and_upload(async_engine, _make_text_pdf())

    with patch(
        "src.services.extraction.get_completion",
        new_callable=AsyncMock,
        return_value=_LLM_RESPONSE_NO_DEMOGRAPHICS,
    ):
        svc = get_extraction_service()
        await svc.process_document(doc_id)

    async with SessionLocal() as session:
        result = await session.execute(
            select(DocumentExtraction).where(DocumentExtraction.document_id == doc_id)
        )
        assert len(result.scalars().all()) == 2

    async with ComplianceSessionLocal() as session:
        count = (await session.execute(select(func.count(HmdaDemographic.id)))).scalar()
        assert count == 0


async def test_extraction_failed_on_bad_json(async_engine, truncate_all):
    """LLM returns non-JSON -> Document status = PROCESSING_FAILED."""
    from db.database import SessionLocal
    from db.enums import DocumentStatus
    from db.models import Document

    from src.services.extraction import get_extraction_service

    doc_id = await _seed_and_upload(async_engine, _make_text_pdf())

    with patch(
        "src.services.extraction.get_completion",
        new_callable=AsyncMock,
        return_value="This is not valid JSON at all",
    ):
        svc = get_extraction_service()
        await svc.process_document(doc_id)

    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id)
        assert doc.status == DocumentStatus.PROCESSING_FAILED


async def test_scanned_pdf_falls_back_to_vision(async_engine, truncate_all):
    """PDF with no text layer -> get_completion called with image content."""
    from src.services.extraction import get_extraction_service

    doc_id = await _seed_and_upload(async_engine, _make_scanned_pdf())

    with patch(
        "src.services.extraction.get_completion",
        new_callable=AsyncMock,
        return_value=_LLM_RESPONSE_NO_DEMOGRAPHICS,
    ) as mock_llm:
        svc = get_extraction_service()
        await svc.process_document(doc_id)

    mock_llm.assert_called_once()
    call_args = mock_llm.call_args
    messages = call_args[0][0]
    # Vision path includes image_url content
    has_image = any(
        isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), list)
        for m in messages
    )
    assert has_image
