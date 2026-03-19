# This project was developed with assistance from AI tools.
"""Document extraction pipeline.

Two-stage extraction: text extraction (pymupdf) then structured extraction
(LLM). Scanned PDFs and images fall back to LLM vision. Post-extraction
HMDA filter routes demographic fields to the compliance schema via
``services.compliance.hmda`` (the sole permitted HMDA accessor).
"""

import asyncio
import base64
import functools
import json
import logging
import re

import fitz  # pymupdf
from db import (
    Document,
    DocumentExtraction,
)
from db.database import SessionLocal
from db.enums import DocumentStatus, DocumentType
from sqlalchemy import select

from ..inference.client import get_completion
from ..services.audit import write_audit_event
from .compliance.hmda import route_extraction_demographics
from .extraction_prompts import (
    HMDA_DEMOGRAPHIC_KEYWORDS,
    build_extraction_prompt,
    build_image_extraction_prompt,
)
from .freshness import check_freshness
from .storage import get_storage_service

logger = logging.getLogger(__name__)

# Map common LLM variants to our enum values
_DOC_TYPE_ALIASES: dict[str, str] = {
    "homeowners_insurance": "insurance",
    "homeowner_insurance": "insurance",
    "insurance_document": "insurance",
    "insurance_policy": "insurance",
    "proof_of_insurance": "insurance",
    "hoi": "insurance",
    "drivers_license": "id",
    "driver_license": "id",
    "passport": "id",
    "government_id": "id",
    "identification": "id",
    "appraisal": "property_appraisal",
    "w-2": "w2",
    "paystub": "pay_stub",
}


def _normalize_doc_type(raw: str) -> str | None:
    """Try to resolve an LLM-returned doc type string to a valid DocumentType value."""
    cleaned = raw.strip().lower().replace(" ", "_").replace("-", "_")
    # Direct match
    try:
        return DocumentType(cleaned).value
    except ValueError:
        pass
    # Alias lookup
    if cleaned in _DOC_TYPE_ALIASES:
        return _DOC_TYPE_ALIASES[cleaned]
    # Substring match (e.g. "insurance" in "homeowners_insurance_policy")
    for dtype in DocumentType:
        if dtype.value != "other" and dtype.value in cleaned:
            return dtype.value
    return None


# Minimum text length to consider PDF text extraction successful.
# Below this threshold we assume the PDF is scanned (image-only).
_MIN_TEXT_LENGTH = 50

# Matches ```json ... ``` or ``` ... ``` fences that LLMs often wrap around JSON.
_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences wrapping JSON output.

    Many LLMs wrap JSON in ```json ... ``` blocks when not constrained by
    response_format. This strips the fences so json.loads() succeeds.
    """
    stripped = text.strip()
    m = _FENCE_RE.match(stripped)
    return m.group(1).strip() if m else stripped


class ExtractionService:
    """Orchestrates download -> extract -> persist for uploaded documents."""

    async def process_document(self, document_id: int) -> None:
        """Main pipeline entry point. Runs as a background task with own DB sessions."""
        async with SessionLocal() as session:
            try:
                stmt = select(Document).where(Document.id == document_id)
                result = await session.execute(stmt)
                doc = result.scalar_one_or_none()
                if doc is None:
                    logger.error("Document %s not found, skipping extraction", document_id)
                    return

                file_path = doc.file_path
                doc_type = doc.doc_type.value
                application_id = doc.application_id
                content_type = self._guess_content_type(file_path)

                # Download from S3
                storage = get_storage_service()
                file_data = await storage.download_file(file_path)

                # Run extraction based on content type
                if content_type == "application/pdf":
                    llm_result = await self._process_pdf(file_data, doc_type)
                else:
                    # JPEG/PNG -> direct to LLM vision
                    llm_result = await self._extract_image_via_llm(
                        file_data, content_type, doc_type
                    )

                if llm_result is None:
                    # Extraction failed (corrupted, unreadable)
                    doc.status = DocumentStatus.PROCESSING_FAILED
                    doc.quality_flags = json.dumps(["unreadable"])
                    await session.commit()
                    return

                extractions = llm_result.get("extractions", [])
                quality_flags = llm_result.get("quality_flags", [])
                detected_doc_type = llm_result.get("detected_doc_type", doc_type)

                # Check for empty extractions (LLM couldn't read)
                if not extractions:
                    doc.status = DocumentStatus.PROCESSING_FAILED
                    doc.quality_flags = json.dumps(["unreadable"])
                    await session.commit()
                    return

                # Auto-reclassify when LLM detects a different document type
                if detected_doc_type and detected_doc_type != doc_type:
                    normalized = _normalize_doc_type(detected_doc_type)
                    if normalized and normalized != doc_type:
                        doc.doc_type = DocumentType(normalized)
                        logger.info(
                            "Reclassified document %d from %s to %s (raw: %s)",
                            document_id,
                            doc_type,
                            normalized,
                            detected_doc_type,
                        )
                    elif not normalized:
                        quality_flags.append("document_type_mismatch")

                # HMDA demographic filter
                lending_extractions, demographic_extractions = self._filter_hmda_fields(extractions)

                # Route demographic data to compliance schema
                if demographic_extractions:
                    await route_extraction_demographics(
                        document_id,
                        application_id,
                        demographic_extractions,
                        borrower_id=doc.borrower_id,
                    )

                # Document freshness check
                freshness_flag = check_freshness(doc_type, lending_extractions)
                if freshness_flag:
                    quality_flags.append(freshness_flag)

                # Store quality flags
                doc.quality_flags = json.dumps(quality_flags) if quality_flags else None

                # Persist lending-path extractions
                for ext in lending_extractions:
                    extraction = DocumentExtraction(
                        document_id=document_id,
                        field_name=ext.get("field_name", ""),
                        field_value=ext.get("field_value"),
                        confidence=ext.get("confidence"),
                        source_page=ext.get("source_page"),
                    )
                    session.add(extraction)

                doc.status = DocumentStatus.PROCESSING_COMPLETE

                await write_audit_event(
                    session,
                    event_type="document_extraction_complete",
                    application_id=application_id,
                    event_data={
                        "document_id": document_id,
                        "doc_type": doc.doc_type.value,
                        "extraction_count": len(lending_extractions),
                        "quality_flags": quality_flags,
                        "reclassified_from": (doc_type if doc.doc_type.value != doc_type else None),
                    },
                )

                await session.commit()
                logger.info(
                    "Document %s processed: %d extractions, %d flags",
                    document_id,
                    len(lending_extractions),
                    len(quality_flags),
                )

            except Exception as exc:
                logger.exception("Extraction failed for document %s", document_id)
                try:
                    doc.status = DocumentStatus.PROCESSING_FAILED
                    await write_audit_event(
                        session,
                        event_type="document_extraction_failed",
                        application_id=doc.application_id,
                        event_data={
                            "document_id": document_id,
                            "error": str(exc)[:500],
                        },
                    )
                    await session.commit()
                except Exception:
                    logger.exception("Failed to update status for document %s", document_id)

    async def _process_pdf(self, file_data: bytes, doc_type: str) -> dict | None:
        """Process a PDF: try text extraction, fall back to image if scanned."""
        text = await self._extract_text_from_pdf(file_data)
        if text is None:
            # Corrupted / unopenable PDF
            return None

        if len(text) >= _MIN_TEXT_LENGTH:
            # Sufficient text layer -- use text-based extraction
            return await self._extract_via_llm(text, doc_type)

        # Scanned PDF -- render first page and use vision
        image = await self._pdf_first_page_to_image(file_data)
        if image is None:
            return None

        return await self._extract_image_via_llm(image, "image/png", doc_type)

    async def _extract_text_from_pdf(self, file_data: bytes) -> str | None:
        """Use pymupdf to extract text from all pages.

        Returns None if PDF is corrupted/unopenable.
        Returns empty string if no text layer (scanned doc).
        Runs in executor to avoid blocking the async event loop.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, functools.partial(self._extract_text_from_pdf_sync, file_data)
        )

    @staticmethod
    def _extract_text_from_pdf_sync(file_data: bytes) -> str | None:
        """Synchronous PDF text extraction (runs in thread pool)."""
        pdf = None
        try:
            pdf = fitz.open(stream=file_data, filetype="pdf")
            text_parts = []
            for page in pdf:
                text_parts.append(page.get_text())
            return " ".join(text_parts).strip()
        except Exception:
            logger.exception("Failed to open PDF with pymupdf")
            return None
        finally:
            if pdf is not None:
                pdf.close()

    async def _pdf_first_page_to_image(self, file_data: bytes) -> bytes | None:
        """Render only the first page of a PDF as a PNG image.

        Runs in executor to avoid blocking the async event loop.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, functools.partial(self._pdf_first_page_to_image_sync, file_data)
        )

    @staticmethod
    def _pdf_first_page_to_image_sync(file_data: bytes) -> bytes | None:
        """Synchronous PDF-to-image rendering (runs in thread pool)."""
        pdf = None
        try:
            pdf = fitz.open(stream=file_data, filetype="pdf")
            if len(pdf) == 0:
                return None
            pix = pdf[0].get_pixmap()
            return pix.tobytes("png")
        except Exception:
            logger.exception("Failed to render PDF first page to image")
            return None
        finally:
            if pdf is not None:
                pdf.close()

    async def _extract_via_llm(self, text: str, doc_type: str) -> dict | None:
        """Send text to LLM, get structured extractions + quality flags."""
        messages = build_extraction_prompt(doc_type, text)
        try:
            raw = await get_completion(messages, tier="capable_large")
            return json.loads(_strip_json_fences(raw))
        except json.JSONDecodeError:
            logger.error("LLM returned non-JSON for text extraction")
            return None

    async def _extract_image_via_llm(
        self,
        image_data: bytes,
        content_type: str,
        doc_type: str,
    ) -> dict | None:
        """Send image to LLM vision, get structured extractions + quality flags."""
        system_msg = build_image_extraction_prompt(doc_type)
        b64 = base64.b64encode(image_data).decode("ascii")
        messages = [
            system_msg,
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{content_type};base64,{b64}"},
                    },
                    {"type": "text", "text": "Extract data from this document image."},
                ],
            },
        ]
        try:
            raw = await get_completion(messages, tier="capable_large")
            return json.loads(_strip_json_fences(raw))
        except json.JSONDecodeError:
            logger.error("LLM returned non-JSON for image extraction")
            return None

    def _filter_hmda_fields(
        self,
        extractions: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """Separate demographic from lending-path extractions.

        Returns (lending_extractions, demographic_extractions).
        """
        lending = []
        demographic = []
        for ext in extractions:
            field_name = ext.get("field_name", "").lower().replace(" ", "_").replace("-", "_")
            if field_name in HMDA_DEMOGRAPHIC_KEYWORDS:
                demographic.append(ext)
            else:
                lending.append(ext)
        return lending, demographic

    @staticmethod
    def _guess_content_type(file_path: str) -> str:
        """Guess content type from file extension in the S3 key."""
        lower = file_path.lower()
        if lower.endswith(".pdf"):
            return "application/pdf"
        if lower.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        if lower.endswith(".png"):
            return "image/png"
        return "application/pdf"  # default to PDF


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: ExtractionService | None = None


def init_extraction_service() -> ExtractionService:
    """Initialise the singleton (called once from app lifespan)."""
    global _service  # noqa: PLW0603
    _service = ExtractionService()
    logger.info("ExtractionService initialised")
    return _service


def get_extraction_service() -> ExtractionService:
    """Return the initialised ExtractionService singleton."""
    if _service is None:
        raise RuntimeError(
            "ExtractionService not initialised -- call init_extraction_service() first"
        )
    return _service
