# This project was developed with assistance from AI tools.
"""FastAPI application entry point."""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.exceptions import HTTPException as StarletteHTTPException

from .admin import setup_admin
from .core.config import settings
from .inference.safety import log_safety_status
from .middleware.pii import PIIMaskingMiddleware
from .observability import init_mlflow_tracing, log_observability_status
from .routes import (
    admin,
    analytics,
    applications,
    audit,
    borrower_chat,
    ceo_chat,
    chat,
    decisions,
    documents,
    health,
    hmda,
    loan_officer_chat,
    model_monitoring,
    public,
    underwriter_chat,
    underwriting,
)
from .schemas.error import ErrorResponse

logger = logging.getLogger(__name__)


async def _auto_seed() -> None:
    """Seed demo data on startup if not already seeded (or config hash changed)."""
    import logging

    from db.database import ComplianceSessionLocal, SessionLocal

    from .services.seed.seeder import seed_demo_data

    logger = logging.getLogger(__name__)
    try:
        async with SessionLocal() as session:
            async with ComplianceSessionLocal() as compliance_session:
                result = await seed_demo_data(session, compliance_session, force=False)
                if result.get("status") == "already_seeded":
                    logger.info("Demo data already seeded (hash: %s)", result.get("config_hash"))
                else:
                    logger.info("Demo data seeded: %s", result)
    except Exception:
        logger.warning("Auto-seed failed (non-fatal)", exc_info=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application startup/shutdown lifecycle."""
    log_safety_status()
    init_mlflow_tracing()
    log_observability_status()
    from .services.conversation import get_conversation_service
    from .services.extraction import init_extraction_service
    from .services.storage import init_storage_service

    conversation_service = get_conversation_service()
    await conversation_service.initialize(settings.DATABASE_URL)
    init_storage_service(settings)
    init_extraction_service()
    await _auto_seed()
    yield
    await conversation_service.shutdown()


app = FastAPI(
    title=f"{settings.COMPANY_NAME} API",
    description=f"Multi-agent loan origination system for {settings.COMPANY_NAME}",
    version="0.1.0",
    lifespan=lifespan,
)

# Prometheus metrics instrumentation - exposes /metrics endpoint
Instrumentator().instrument(app).expose(app)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# PII masking -- runs after CORS, masks JSON response bodies for CEO role
app.add_middleware(PIIMaskingMiddleware)

_HTTP_STATUS_TITLES: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    413: "Payload Too Large",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
}


def _build_error(
    status_code: int, detail: str, request_id: str, instance: str = ""
) -> ErrorResponse:
    return ErrorResponse(
        type="about:blank",
        title=_HTTP_STATUS_TITLES.get(status_code, "Error"),
        status=status_code,
        detail=detail,
        request_id=request_id,
        instance=instance,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Convert HTTPException to RFC 7807 Problem Details."""
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    body = _build_error(
        exc.status_code, str(exc.detail), request_id, instance=str(request.url.path)
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Convert Pydantic validation errors to RFC 7807 Problem Details."""
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    body = _build_error(422, str(exc.errors()), request_id, instance=str(request.url.path))
    return JSONResponse(status_code=422, content=body.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions -- log and return 500."""
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    logger.exception("Unhandled exception (request_id=%s)", request_id)
    body = _build_error(
        500, "An unexpected error occurred.", request_id, instance=str(request.url.path)
    )
    return JSONResponse(status_code=500, content=body.model_dump())


# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(applications.router, prefix="/api/applications", tags=["applications"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(borrower_chat.router, prefix="/api", tags=["chat"])
app.include_router(loan_officer_chat.router, prefix="/api", tags=["chat"])
app.include_router(underwriter_chat.router, prefix="/api", tags=["chat"])
app.include_router(ceo_chat.router, prefix="/api", tags=["chat"])
app.include_router(decisions.router, prefix="/api/applications", tags=["decisions"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(hmda.router, prefix="/api/hmda", tags=["hmda"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(model_monitoring.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(underwriting.router, prefix="/api/applications", tags=["underwriting"])

# Setup SQLAdmin dashboard at /admin
setup_admin(app)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint"""
    return {"message": f"Welcome to {settings.COMPANY_NAME} API"}
