# This project was developed with assistance from AI tools.
"""Integration test fixtures -- real PostgreSQL + real MinIO, no mocks.

Session-scoped containers (started once per test run) provide real PostgreSQL
(pgvector) and MinIO instances. Function-scoped fixtures give each test an
isolated DB session with savepoint rollback so tests don't leak state.
"""

import os
from collections import namedtuple

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from testcontainers.minio import MinioContainer
from testcontainers.postgres import PostgresContainer

# ---------------------------------------------------------------------------
# Mark all tests in this directory as integration
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Session-scoped: containers + engine + migrations
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_container():
    """Start pgvector/pgvector:pg16 via testcontainers."""
    with PostgresContainer(
        image="pgvector/pgvector:pg16",
        username="test",
        password="test",
        dbname="test",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def minio_container():
    """Start minio/minio:latest via testcontainers."""
    with MinioContainer() as mc:
        yield mc


@pytest.fixture(scope="session")
def db_url(pg_container):
    """Async DB URL for asyncpg."""
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return f"postgresql+asyncpg://test:test@{host}:{port}/test"


@pytest.fixture(scope="session")
def sync_db_url(pg_container):
    """Sync DB URL for Alembic (psycopg2)."""
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return f"postgresql://test:test@{host}:{port}/test"


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(sync_db_url):
    """Create required PG roles then run alembic upgrade head."""
    import psycopg2

    # Migrations GRANT to these roles -- create them in the test container
    conn = psycopg2.connect(sync_db_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        for role in ("lending_app", "compliance_app"):
            cur.execute(
                f"DO $$ BEGIN CREATE ROLE {role}; EXCEPTION WHEN duplicate_object THEN NULL; END $$"
            )
    conn.close()

    os.environ["DATABASE_URL"] = sync_db_url
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "db", "alembic.ini")
    )
    alembic_cfg.set_main_option(
        "script_location",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "db", "alembic"),
    )
    alembic_cfg.set_main_option("sqlalchemy.url", sync_db_url)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="session")
def async_engine(db_url, _run_migrations):
    """Create an async engine pointing at the test container."""
    engine = create_async_engine(db_url, echo=False, poolclass=NullPool)
    yield engine


@pytest.fixture(scope="session", autouse=True)
def _patch_db_module(async_engine):
    """Monkey-patch db.database globals so ExtractionService and HMDA
    service calls that import SessionLocal/ComplianceSessionLocal directly
    use the test database.

    Because tests/conftest.py imports ``from src.main import app`` at module
    level, the entire application (including extraction.py and hmda.py) is
    imported during test collection -- before any fixtures run.  Their
    ``from db.database import SessionLocal`` captures the ORIGINAL factory.
    Patching db.database alone doesn't update those already-bound local
    references, so we must also patch the modules that imported by name.
    """
    import db.database as db_mod

    test_session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=async_engine,
        class_=AsyncSession,
    )
    db_mod.engine = async_engine
    db_mod.SessionLocal = test_session_factory
    db_mod.compliance_engine = async_engine
    db_mod.ComplianceSessionLocal = test_session_factory
    db_mod.db_service = db_mod.DatabaseService(engine=async_engine)

    # Patch already-imported local references (captured at import time
    # before this fixture ran).
    import db as db_pkg

    import src.seed as seed_mod
    import src.services.compliance.hmda as hmda_mod
    import src.services.extraction as ext_mod

    for mod in (ext_mod, hmda_mod, seed_mod):
        mod.SessionLocal = test_session_factory

    for mod in (db_pkg, hmda_mod):
        mod.ComplianceSessionLocal = test_session_factory


@pytest.fixture(scope="session", autouse=True)
def _init_storage(minio_container):
    """Initialize the StorageService singleton with test MinIO."""
    from src.services import storage as storage_mod

    host = minio_container.get_container_host_ip()
    port = minio_container.get_exposed_port(9000)
    endpoint = f"http://{host}:{port}"

    svc = storage_mod.StorageService(
        endpoint=endpoint,
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="test-documents",
    )
    storage_mod._service = svc


@pytest.fixture(scope="session", autouse=True)
def _init_extraction(_patch_db_module, _init_storage):
    """Initialize the ExtractionService singleton.

    Depends on _patch_db_module so that extraction.py's
    ``from db.database import SessionLocal`` captures the test session factory,
    and on _init_storage so MinIO is ready for download_file calls.
    """
    from src.services.extraction import init_extraction_service

    init_extraction_service()


# ---------------------------------------------------------------------------
# Function-scoped: per-test session with savepoint rollback
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(async_engine):
    """Per-test DB session with savepoint rollback."""
    conn = await async_engine.connect()
    txn = await conn.begin()
    session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    await session.close()
    await txn.rollback()
    await conn.close()


@pytest_asyncio.fixture
async def compliance_session(async_engine):
    """Per-test compliance DB session with savepoint rollback."""
    conn = await async_engine.connect()
    txn = await conn.begin()
    session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    await session.close()
    await txn.rollback()
    await conn.close()


@pytest.fixture
def client_factory(db_session, compliance_session):
    """Factory returning an async httpx client with dependency overrides."""
    import db.database as db_mod
    from db.database import get_compliance_db, get_db, get_db_service

    from src.main import app
    from src.middleware.auth import get_current_user

    async def _make(user):
        async def _get_db():
            yield db_session

        async def _get_compliance_db():
            yield compliance_session

        async def _get_current_user(request=None):
            return user

        async def _get_db_service():
            return db_mod.db_service

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_compliance_db] = _get_compliance_db
        app.dependency_overrides[get_current_user] = _get_current_user
        app.dependency_overrides[get_db_service] = _get_db_service
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    yield _make

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed data helper
# ---------------------------------------------------------------------------


class _Ref:
    """Lightweight reference holding an ID and any extra scalar attrs."""

    def __init__(self, id: int, **kwargs):
        self.id = id
        for k, v in kwargs.items():
            setattr(self, k, v)


SeedData = namedtuple(
    "SeedData",
    [
        "sarah",
        "michael",
        "jennifer",
        "sarah_app1",
        "sarah_app2",
        "michael_app",
        "sarah_financials",
        "doc1",
        "doc2",
    ],
)


@pytest_asyncio.fixture
async def seed_data(db_session, compliance_session):
    """Create realistic test data in the DB."""
    from db.enums import ApplicationStage, DocumentStatus, DocumentType, LoanType
    from db.models import (
        Application,
        ApplicationBorrower,
        ApplicationFinancials,
        Borrower,
        Document,
    )

    from tests.functional.personas import LO_USER_ID, MICHAEL_USER_ID, SARAH_USER_ID

    # Borrowers
    sarah = Borrower(
        keycloak_user_id=SARAH_USER_ID,
        first_name="Sarah",
        last_name="Mitchell",
        email="sarah@example.com",
    )
    michael = Borrower(
        keycloak_user_id=MICHAEL_USER_ID,
        first_name="Michael",
        last_name="Chen",
        email="michael@example.com",
    )
    jennifer = Borrower(
        keycloak_user_id="jennifer-davis-003",
        first_name="Jennifer",
        last_name="Davis",
        email="jennifer@example.com",
    )
    db_session.add_all([sarah, michael, jennifer])
    await db_session.flush()

    # Applications
    sarah_app1 = Application(
        stage=ApplicationStage.APPLICATION,
        loan_type=LoanType.CONVENTIONAL_30,
        property_address="123 Main St, Denver, CO",
        loan_amount=350000,
        property_value=450000,
        assigned_to=LO_USER_ID,
    )
    sarah_app2 = Application(
        stage=ApplicationStage.INQUIRY,
        loan_type=LoanType.FHA,
        property_address="456 Oak Ave, Boulder, CO",
        loan_amount=275000,
        property_value=325000,
        assigned_to=None,
    )
    michael_app = Application(
        stage=ApplicationStage.PROCESSING,
        loan_type=LoanType.VA,
        property_address="789 Pine Rd, Aurora, CO",
        loan_amount=500000,
        property_value=600000,
        assigned_to=LO_USER_ID,
    )
    db_session.add_all([sarah_app1, sarah_app2, michael_app])
    await db_session.flush()

    # Junction rows
    db_session.add_all(
        [
            ApplicationBorrower(
                application_id=sarah_app1.id,
                borrower_id=sarah.id,
                is_primary=True,
            ),
            ApplicationBorrower(
                application_id=sarah_app2.id,
                borrower_id=sarah.id,
                is_primary=True,
            ),
            ApplicationBorrower(
                application_id=michael_app.id,
                borrower_id=michael.id,
                is_primary=True,
            ),
            # Jennifer is co-borrower on sarah_app1
            ApplicationBorrower(
                application_id=sarah_app1.id,
                borrower_id=jennifer.id,
                is_primary=False,
            ),
        ]
    )
    await db_session.flush()

    # Financials for sarah
    sarah_financials = ApplicationFinancials(
        application_id=sarah_app1.id,
        gross_monthly_income=8500,
        monthly_debts=1200,
        total_assets=150000,
        credit_score=740,
        dti_ratio=0.28,
    )
    db_session.add(sarah_financials)

    # Documents on sarah_app1
    doc1 = Document(
        application_id=sarah_app1.id,
        borrower_id=sarah.id,
        doc_type=DocumentType.W2,
        status=DocumentStatus.UPLOADED,
        file_path="test/doc1.pdf",
        uploaded_by=SARAH_USER_ID,
    )
    doc2 = Document(
        application_id=sarah_app1.id,
        borrower_id=sarah.id,
        doc_type=DocumentType.PAY_STUB,
        status=DocumentStatus.UPLOADED,
        file_path="test/doc2.pdf",
        uploaded_by=SARAH_USER_ID,
    )
    db_session.add_all([doc1, doc2])
    await db_session.flush()

    return SeedData(
        sarah=_Ref(sarah.id),
        michael=_Ref(michael.id),
        jennifer=_Ref(jennifer.id),
        sarah_app1=_Ref(sarah_app1.id),
        sarah_app2=_Ref(sarah_app2.id),
        michael_app=_Ref(michael_app.id),
        sarah_financials=_Ref(sarah_financials.id),
        doc1=_Ref(doc1.id),
        doc2=_Ref(doc2.id),
    )


# ---------------------------------------------------------------------------
# Truncate fixture for tests where services create their own sessions
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def truncate_all(async_engine):
    """Yield-based: truncates all tables after the test completes."""
    yield
    async with async_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE hmda.demographics, hmda.loan_data CASCADE"))
        await conn.execute(
            text(
                "TRUNCATE TABLE kb_chunks, kb_documents, "
                "document_extractions, documents, conditions, decisions, "
                "credit_reports, prequalification_decisions, "
                "rate_locks, application_financials, application_borrowers, applications, "
                "borrowers, audit_events, audit_violations, demo_data_manifest CASCADE"
            )
        )
