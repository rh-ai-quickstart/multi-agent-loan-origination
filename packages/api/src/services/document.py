# This project was developed with assistance from AI tools.
"""Document service with content restriction for metadata-only scopes.

Roles with document_metadata_only scope see document metadata only --
file_path and content are stripped at the service layer (defense-in-depth
Layer 2). The route layer provides Layer 1, and the response schema
provides Layer 4.
"""

import logging

from db import Application, ApplicationBorrower, Document
from db.enums import DocumentStatus, DocumentType
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..schemas.auth import UserContext
from ..services.audit import write_audit_event
from ..services.scope import apply_data_scope
from ..services.storage import get_storage_service

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


class DocumentAccessDenied(Exception):
    """Raised when a role is not allowed to access document content."""


class DocumentUploadError(Exception):
    """Raised when a document upload fails validation."""


async def list_documents(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    *,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Document], int]:
    """Return documents for an application visible to the current user."""
    count_stmt = select(func.count(func.distinct(Document.id))).where(
        Document.application_id == application_id,
    )
    count_stmt = apply_data_scope(
        count_stmt,
        user.data_scope,
        user,
        join_to_application=Document.application,
    )
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Document)
        .where(Document.application_id == application_id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    stmt = apply_data_scope(
        stmt,
        user.data_scope,
        user,
        join_to_application=Document.application,
    )
    result = await session.execute(stmt)
    documents = result.unique().scalars().all()

    return documents, total


async def get_document(
    session: AsyncSession,
    user: UserContext,
    document_id: int,
) -> Document | None:
    """Return a single document if visible to the current user."""
    stmt = select(Document).where(Document.id == document_id)
    stmt = apply_data_scope(
        stmt,
        user.data_scope,
        user,
        join_to_application=Document.application,
    )
    result = await session.execute(stmt)
    return result.unique().scalar_one_or_none()


def get_document_content(user: UserContext, document: Document) -> str | None:
    """Return document file_path, enforcing content restriction.

    Raises DocumentAccessDenied for metadata-only scopes (service-level
    enforcement, defense-in-depth Layer 2).
    """
    if user.data_scope.document_metadata_only:
        raise DocumentAccessDenied("Document content access denied (metadata-only scope)")
    return document.file_path


# Statuses from which an LO may flag a document for resubmission.
_FLAGGABLE_STATUSES = {
    DocumentStatus.PROCESSING_COMPLETE,
    DocumentStatus.PENDING_REVIEW,
    DocumentStatus.ACCEPTED,
}


async def update_document_status(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    document_id: int,
    new_status: DocumentStatus,
    reason: str | None = None,
) -> Document | None:
    """Update a document's status (e.g. flag for resubmission).

    Returns the updated Document, or None if the document is not found /
    out of scope.  Raises ValueError for invalid status transitions.
    """
    doc = await get_document(session, user, document_id)
    if doc is None:
        return None

    if doc.application_id != application_id:
        return None

    if new_status == DocumentStatus.FLAGGED_FOR_RESUBMISSION:
        if doc.status not in _FLAGGABLE_STATUSES:
            raise ValueError(
                f"Cannot flag document from status '{doc.status.value}'. "
                f"Allowed: {sorted(s.value for s in _FLAGGABLE_STATUSES)}."
            )

    old_status = doc.status.value
    doc.status = new_status
    if reason:
        doc.quality_flags = reason

    await write_audit_event(
        session,
        event_type="document_status_changed",
        user_id=user.user_id,
        user_role=user.role.value if user.role else None,
        application_id=application_id,
        event_data={
            "document_id": document_id,
            "from_status": old_status,
            "to_status": new_status.value,
            "reason": reason,
        },
    )

    await session.commit()
    await session.refresh(doc)
    return doc


async def upload_document(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    doc_type: DocumentType,
    filename: str,
    content_type: str,
    file_data: bytes,
) -> Document | None:
    """Upload a document to S3 and create the DB record.

    1. Verify user has access to the application (via data scope query)
    2. Validate file size and content type
    3. Create Document row (status=UPLOADED)
    4. Upload file to S3 using document.id in the object key
    5. Update file_path and status=PROCESSING
    6. Return Document
    """
    # Validate content type
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise DocumentUploadError(
            f"Unsupported content type: {content_type}. "
            f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
        )

    # Validate file size
    max_bytes = settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024
    if len(file_data) > max_bytes:
        raise DocumentUploadError(
            f"File size {len(file_data)} exceeds maximum of {settings.UPLOAD_MAX_SIZE_MB}MB"
        )

    # Verify the application exists and is accessible to this user
    app_stmt = select(Application).where(Application.id == application_id)
    app_stmt = apply_data_scope(app_stmt, user.data_scope, user)
    result = await session.execute(app_stmt)
    application = result.unique().scalar_one_or_none()
    if application is None:
        return None

    # Resolve primary borrower for document linkage
    primary_stmt = select(ApplicationBorrower.borrower_id).where(
        ApplicationBorrower.application_id == application_id,
        ApplicationBorrower.is_primary.is_(True),
    )
    primary_result = await session.execute(primary_stmt)
    primary_borrower_id = primary_result.scalar_one_or_none()

    # Create document row with initial status
    doc = Document(
        application_id=application_id,
        borrower_id=primary_borrower_id,
        doc_type=doc_type,
        status=DocumentStatus.UPLOADED,
        uploaded_by=user.user_id,
    )
    session.add(doc)
    await session.flush()  # Assign doc.id

    # Upload to S3
    storage = get_storage_service()
    object_key = storage.build_object_key(application_id, doc.id, filename)
    await storage.upload_file(file_data, object_key, content_type)

    # Update document with storage path and advance status
    doc.file_path = object_key
    doc.status = DocumentStatus.PROCESSING

    await write_audit_event(
        session,
        event_type="document_uploaded",
        user_id=user.user_id,
        user_role=user.role.value if user.role else None,
        application_id=application_id,
        event_data={
            "document_id": doc.id,
            "doc_type": doc_type.value,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": len(file_data),
        },
    )

    await session.commit()
    await session.refresh(doc)

    return doc
