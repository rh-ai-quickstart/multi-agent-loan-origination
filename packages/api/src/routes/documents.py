# This project was developed with assistance from AI tools.
"""Document routes with CEO content restriction (Layer 1)."""

import asyncio
import logging

from db import Document, get_db
from db.enums import DocumentType, UserRole
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..middleware.auth import CurrentUser, require_roles
from ..schemas import Pagination
from ..schemas.completeness import CompletenessResponse
from ..schemas.document import (
    DocumentDetailResponse,
    DocumentFilePathResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    ExtractionListResponse,
)
from ..services import document as doc_service
from ..services.completeness import check_completeness
from ..services.document import DocumentAccessDenied, DocumentUploadError
from ..services.extraction import get_extraction_service

logger = logging.getLogger(__name__)

# Track background extraction tasks so exceptions aren't silently lost
_extraction_tasks: set[asyncio.Task] = set()

router = APIRouter()

_ALL_AUTHENTICATED = (
    UserRole.ADMIN,
    UserRole.BORROWER,
    UserRole.LOAN_OFFICER,
    UserRole.UNDERWRITER,
    UserRole.CEO,
)

_CONTENT_ROLES = (
    UserRole.ADMIN,
    UserRole.BORROWER,
    UserRole.LOAN_OFFICER,
    UserRole.UNDERWRITER,
)


_UPLOAD_ROLES = (
    UserRole.ADMIN,
    UserRole.BORROWER,
    UserRole.LOAN_OFFICER,
)


@router.post(
    "/applications/{application_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=201,
    dependencies=[Depends(require_roles(*_UPLOAD_ROLES))],
)
async def upload_document(
    application_id: int,
    user: CurrentUser,
    file: UploadFile = File(...),
    doc_type: DocumentType = Form(...),
    session: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload a document for an application."""
    # Validate content type
    content_type = file.content_type or ""
    if content_type not in doc_service.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {content_type}. "
            f"Allowed: {', '.join(sorted(doc_service.ALLOWED_CONTENT_TYPES))}",
        )

    file_data = await file.read()

    try:
        doc = await doc_service.upload_document(
            session=session,
            user=user,
            application_id=application_id,
            doc_type=doc_type,
            filename=file.filename or "document",
            content_type=content_type,
            file_data=file_data,
        )
    except DocumentUploadError as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        ) from exc

    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # Fire background extraction pipeline (retain reference for error handling)
    extraction_svc = get_extraction_service()
    task = asyncio.create_task(
        extraction_svc.process_document(doc.id),
        name=f"extract-doc-{doc.id}",
    )
    _extraction_tasks.add(task)
    task.add_done_callback(_extraction_tasks.discard)

    return DocumentUploadResponse.model_validate(doc)


@router.get(
    "/applications/{application_id}/documents",
    response_model=DocumentListResponse,
    dependencies=[Depends(require_roles(*_ALL_AUTHENTICATED))],
)
async def list_documents(
    application_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> DocumentListResponse:
    """List documents for an application. All roles see metadata only."""
    documents, total = await doc_service.list_documents(
        session,
        user,
        application_id,
        offset=offset,
        limit=limit,
    )
    items = [DocumentResponse.model_validate(doc) for doc in documents]
    return DocumentListResponse(
        data=items,
        pagination=Pagination(
            total=total,
            offset=offset,
            limit=limit,
            has_more=(offset + limit < total),
        ),
    )


@router.get(
    "/applications/{application_id}/documents/{document_id}",
    response_model=DocumentDetailResponse,
    dependencies=[Depends(require_roles(*_ALL_AUTHENTICATED))],
)
async def get_document(
    application_id: int,
    document_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    """Get document metadata. CEO sees file_path=null; others see the full path."""
    doc = await doc_service.get_document(session, user, document_id)
    if doc is None or doc.application_id != application_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    result = DocumentDetailResponse.model_validate(doc)
    if user.data_scope.document_metadata_only:
        result = result.model_copy(update={"file_path": None})
    return result


_EXTRACTION_ROLES = (
    UserRole.ADMIN,
    UserRole.LOAN_OFFICER,
    UserRole.UNDERWRITER,
)


@router.get(
    "/applications/{application_id}/documents/{document_id}/extractions",
    response_model=ExtractionListResponse,
    dependencies=[Depends(require_roles(*_EXTRACTION_ROLES))],
)
async def get_extractions(
    application_id: int,
    document_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> ExtractionListResponse:
    """Get extraction results for a document."""
    stmt = (
        select(Document)
        .options(selectinload(Document.extractions))
        .where(Document.id == document_id)
    )
    result = await session.execute(stmt)
    doc = result.unique().scalar_one_or_none()
    if doc is None or doc.application_id != application_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return ExtractionListResponse(
        document_id=document_id,
        extractions=doc.extractions or [],
    )


@router.get(
    "/applications/{application_id}/completeness",
    response_model=CompletenessResponse,
    dependencies=[Depends(require_roles(*_ALL_AUTHENTICATED))],
)
async def get_completeness(
    application_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> CompletenessResponse:
    """Check document completeness for an application."""
    result = await check_completeness(session, user, application_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    return result


@router.get(
    "/applications/{application_id}/documents/{document_id}/content",
    response_model=DocumentFilePathResponse,
    dependencies=[Depends(require_roles(*_CONTENT_ROLES))],
)
async def get_document_content(
    application_id: int,
    document_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> DocumentFilePathResponse:
    """Get document content (file path). CEO is blocked at route level (Layer 1)."""
    doc = await doc_service.get_document(session, user, document_id)
    if doc is None or doc.application_id != application_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    try:
        file_path = doc_service.get_document_content(user, doc)
    except DocumentAccessDenied as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return DocumentFilePathResponse(file_path=file_path)
