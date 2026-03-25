# This project was developed with assistance from AI tools.
"""Document request/response schemas."""

from datetime import datetime

from db.enums import DocumentStatus, DocumentType
from pydantic import BaseModel, ConfigDict

from . import Pagination


class DocumentResponse(BaseModel):
    """Document metadata response (safe for all roles including CEO)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    borrower_id: int | None = None
    doc_type: DocumentType
    status: DocumentStatus
    quality_flags: str | None = None
    uploaded_by: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    """Full document response including file_path (not for CEO)."""

    file_path: str | None = None


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    borrower_id: int | None = None
    doc_type: DocumentType
    status: DocumentStatus
    quality_flags: str | None = None
    uploaded_by: str | None = None
    file_path: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentStatusUpdate(BaseModel):
    """Request body for updating a document's status."""

    status: DocumentStatus
    reason: str | None = None


class DocumentFilePathResponse(BaseModel):
    """Response for document content endpoint."""

    file_path: str


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    data: list[DocumentResponse]
    pagination: Pagination


class ExtractionFieldResponse(BaseModel):
    """A single extracted field from a document."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    field_name: str
    field_value: str | None = None
    confidence: float | None = None
    source_page: int | None = None


class ExtractionListResponse(BaseModel):
    """Extraction results for a document."""

    document_id: int
    extractions: list[ExtractionFieldResponse]
