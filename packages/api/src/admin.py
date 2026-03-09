# This project was developed with assistance from AI tools.
"""
SQLAdmin configuration for database administration UI

Access the admin panel at: http://localhost:8000/admin

When AUTH_DISABLED=false, requires admin credentials via login form.
When AUTH_DISABLED=true, admin panel is open (dev mode).
"""

from db import (
    Application,
    ApplicationFinancials,
    AuditEvent,
    Borrower,
    Condition,
    Decision,
    DemoDataManifest,
    Document,
    DocumentExtraction,
    RateLock,
)
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import create_engine
from starlette.requests import Request
from starlette.responses import Response

from .core.config import settings

# SQLAdmin requires a sync engine; derive from the async DATABASE_URL
_sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
engine = create_engine(_sync_url, echo=False)


class AdminAuth(AuthenticationBackend):
    """Session-based auth gate for SQLAdmin.

    When AUTH_DISABLED=true, authenticate() always returns True (dev mode).
    Otherwise, requires login with credentials from ADMIN_USER / ADMIN_PASSWORD env vars.
    """

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        if username == settings.SQLADMIN_USER and password == settings.SQLADMIN_PASSWORD:
            request.session.update({"admin_authenticated": True})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Response | bool:
        if settings.AUTH_DISABLED:
            return True
        return request.session.get("admin_authenticated", False)


class BorrowerAdmin(ModelView, model=Borrower):
    column_list = [
        Borrower.id,
        Borrower.first_name,
        Borrower.last_name,
        Borrower.email,
        Borrower.created_at,
    ]
    column_searchable_list = [Borrower.first_name, Borrower.last_name, Borrower.email]
    column_sortable_list = [Borrower.id, Borrower.last_name, Borrower.created_at]
    column_default_sort = [(Borrower.created_at, True)]
    name = "Borrower"
    name_plural = "Borrowers"
    icon = "fa-solid fa-user"


class ApplicationAdmin(ModelView, model=Application):
    column_list = [
        Application.id,
        Application.stage,
        Application.loan_type,
        Application.loan_amount,
        Application.assigned_to,
        Application.created_at,
    ]
    column_searchable_list = [Application.property_address, Application.assigned_to]
    column_sortable_list = [Application.id, Application.stage, Application.created_at]
    column_default_sort = [(Application.created_at, True)]
    name = "Application"
    name_plural = "Applications"
    icon = "fa-solid fa-file-alt"


class ApplicationFinancialsAdmin(ModelView, model=ApplicationFinancials):
    column_list = [
        ApplicationFinancials.id,
        ApplicationFinancials.application_id,
        ApplicationFinancials.credit_score,
        ApplicationFinancials.dti_ratio,
        ApplicationFinancials.gross_monthly_income,
    ]
    name = "Financials"
    name_plural = "Financials"
    icon = "fa-solid fa-dollar-sign"


class RateLockAdmin(ModelView, model=RateLock):
    column_list = [
        RateLock.id,
        RateLock.application_id,
        RateLock.locked_rate,
        RateLock.lock_date,
        RateLock.expiration_date,
        RateLock.is_active,
    ]
    column_default_sort = [(RateLock.created_at, True)]
    name = "Rate Lock"
    name_plural = "Rate Locks"
    icon = "fa-solid fa-lock"


class ConditionAdmin(ModelView, model=Condition):
    column_list = [
        Condition.id,
        Condition.application_id,
        Condition.severity,
        Condition.status,
        Condition.issued_by,
        Condition.created_at,
    ]
    column_sortable_list = [Condition.id, Condition.severity, Condition.status]
    column_default_sort = [(Condition.created_at, True)]
    name = "Condition"
    name_plural = "Conditions"
    icon = "fa-solid fa-clipboard-check"


class DecisionAdmin(ModelView, model=Decision):
    column_list = [
        Decision.id,
        Decision.application_id,
        Decision.decision_type,
        Decision.decided_by,
        Decision.created_at,
    ]
    column_default_sort = [(Decision.created_at, True)]
    name = "Decision"
    name_plural = "Decisions"
    icon = "fa-solid fa-gavel"


class DocumentAdmin(ModelView, model=Document):
    column_list = [
        Document.id,
        Document.application_id,
        Document.doc_type,
        Document.status,
        Document.uploaded_by,
        Document.created_at,
    ]
    column_searchable_list = [Document.uploaded_by]
    column_sortable_list = [Document.id, Document.doc_type, Document.status]
    column_default_sort = [(Document.created_at, True)]
    name = "Document"
    name_plural = "Documents"
    icon = "fa-solid fa-file-upload"


class DocumentExtractionAdmin(ModelView, model=DocumentExtraction):
    column_list = [
        DocumentExtraction.id,
        DocumentExtraction.document_id,
        DocumentExtraction.field_name,
        DocumentExtraction.confidence,
    ]
    name = "Extraction"
    name_plural = "Extractions"
    icon = "fa-solid fa-search"


class AuditEventAdmin(ModelView, model=AuditEvent):
    column_list = [
        AuditEvent.id,
        AuditEvent.timestamp,
        AuditEvent.event_type,
        AuditEvent.user_id,
        AuditEvent.user_role,
        AuditEvent.application_id,
    ]
    column_sortable_list = [AuditEvent.id, AuditEvent.timestamp, AuditEvent.event_type]
    column_default_sort = [(AuditEvent.timestamp, True)]
    can_create = False
    can_edit = False
    can_delete = False
    name = "Audit Event"
    name_plural = "Audit Events"
    icon = "fa-solid fa-shield-alt"


class DemoDataManifestAdmin(ModelView, model=DemoDataManifest):
    column_list = [DemoDataManifest.id, DemoDataManifest.seeded_at, DemoDataManifest.config_hash]
    can_create = False
    can_edit = False
    can_delete = False
    name = "Seed Manifest"
    name_plural = "Seed Manifests"
    icon = "fa-solid fa-database"


def setup_admin(app):
    """Set up SQLAdmin and mount it to the FastAPI app."""
    auth_backend = AdminAuth(
        secret_key=settings.SQLADMIN_SECRET_KEY,
    )
    admin = Admin(
        app, engine, title=f"{settings.COMPANY_NAME} Admin", authentication_backend=auth_backend
    )

    admin.add_view(BorrowerAdmin)
    admin.add_view(ApplicationAdmin)
    admin.add_view(ApplicationFinancialsAdmin)
    admin.add_view(RateLockAdmin)
    admin.add_view(ConditionAdmin)
    admin.add_view(DecisionAdmin)
    admin.add_view(DocumentAdmin)
    admin.add_view(DocumentExtractionAdmin)
    admin.add_view(AuditEventAdmin)
    admin.add_view(DemoDataManifestAdmin)

    return admin
