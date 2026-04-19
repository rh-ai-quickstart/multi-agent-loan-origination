<!-- This project was developed with assistance from AI tools. -->

# Mortgage AI - Database Package

PostgreSQL database layer for the Mortgage AI multi-agent mortgage lending demo application. Part of the Red Hat AI Quickstart catalog.

## Technology Stack

- **PostgreSQL 16** with pgvector extension for compliance KB embeddings
- **SQLAlchemy 2.0** async ORM with asyncpg driver
- **Alembic** for schema migrations
- **pydantic-settings** for type-safe configuration
- **pgvector** (768-dimensional vectors) with HNSW indexing

## Schema Overview

The database models the complete mortgage lending lifecycle across 20+ tables:

| Model | Purpose |
|-------|---------|
| **Borrower** | Borrower profile linked to Keycloak identity |
| **Application** | Mortgage application with lifecycle stage tracking |
| **ApplicationBorrower** | Junction table supporting co-borrowers (many-to-many) |
| **ApplicationFinancials** | Financial data per application, optionally per borrower |
| **RateLock** | Interest rate lock with expiration tracking |
| **Condition** | Underwriting conditions with severity and status lifecycle |
| **Decision** | Underwriting decisions (approval, conditional, denied) |
| **Document** | Uploaded documents (W2, pay stubs, appraisals, etc.) |
| **DocumentExtraction** | Extracted fields from document processing |
| **AuditEvent** | Append-only audit trail with hash chaining |
| **AuditViolation** | Trigger violations (attempted UPDATE/DELETE on audit_events) |
| **KBDocument** | Compliance knowledge base documents (3-tier: federal, agency, internal) |
| **KBChunk** | Embedded text chunks with Vector(768) embeddings for semantic search |
| **CreditReport** | Credit bureau pull records with hard/soft inquiry tracking |
| **PrequalificationDecision** | Pre-qualification decisions with denial reason tracking |
| **RiskAssessmentRecord** | AI risk assessment outputs with model metadata |
| **ComplianceResult** | Compliance check results (ECOA, ATR/QM, TRID) |
| **HmdaDemographic** | HMDA demographic data (isolated schema, restricted access) |
| **HmdaLoanData** | HMDA-reportable loan characteristics |
| **DemoDataManifest** | Tracks synthetic demo data for bulk deletion |

## Key Architectural Patterns

### HMDA Data Isolation

HMDA demographic data lives in a separate `hmda` schema with restricted access enforced at the database role level:

- **lending_app** role: Normal application access (public schema only)
- **compliance_app** role: HMDA schema access for analytics and reporting

Dual connection strings:

```python
DATABASE_URL = "postgresql+asyncpg://lending_app:lending_pass@localhost:5433/mortgage-ai"
COMPLIANCE_DATABASE_URL = "postgresql+asyncpg://compliance_app:compliance_pass@localhost:5433/mortgage-ai"
```

Code uses `get_db()` for normal operations and `get_compliance_db()` for HMDA access.

### Audit Event Hash Chains

Every audit event includes `prev_hash` (SHA-256 hash of the previous event), forming an append-only chain:

```
Event 1 [hash=abc123] → Event 2 [prev_hash=abc123, hash=def456] → Event 3 [prev_hash=def456, hash=...]
```

A trigger blocks UPDATE/DELETE operations on `audit_events` and logs violations to `audit_violations`.

### Vector Embeddings for Compliance KB

Compliance knowledge base chunks use pgvector for semantic search:

```sql
-- KBChunk.embedding is a Vector(768) column
CREATE INDEX kb_chunks_embedding_idx ON kb_chunks USING hnsw (embedding vector_cosine_ops);
```

Application code performs cosine similarity search to retrieve relevant regulatory guidance during agent interactions.

## Database Container

The PostgreSQL container runs on **port 5433** (not the default 5432):

```bash
# From project root
make db-start       # Start container
make db-stop        # Stop container
make db-upgrade     # Run migrations
```

Container configuration in `compose.yml`:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports:
      - "5433:5432"  # Host 5433 → Container 5432
    environment:
      POSTGRES_DB: mortgage-ai
```

Initialization script (`config/postgres/init-databases.sh`) creates:

- `mlflow` database (for observability)
- `lending_app` and `compliance_app` roles
- HMDA schema (created via Alembic migration)

## Configuration

Configuration uses pydantic-settings for type safety. Set environment variables in `.env` at project root:

```bash
DATABASE_URL=postgresql+asyncpg://lending_app:lending_pass@localhost:5433/mortgage-ai
COMPLIANCE_DATABASE_URL=postgresql+asyncpg://compliance_app:compliance_pass@localhost:5433/mortgage-ai
SQL_ECHO=false  # Set to true for SQL query logging
```

## Migrations

Alembic manages schema versioning. Migrations live in `alembic/versions/` with sequential numbering.

### Common Commands

```bash
# From packages/db directory
pnpm migrate                  # Apply pending migrations
pnpm migrate:down             # Rollback last migration
pnpm migrate:new -m "message" # Generate new migration
pnpm migrate:history          # Show migration history

# Direct Alembic commands
uv run alembic upgrade head   # Apply all pending
uv run alembic downgrade -1   # Rollback one
uv run alembic current        # Show current revision
```

### Creating Migrations

Auto-generate from model changes:

```bash
# 1. Update models in src/db/models.py
# 2. Generate migration
pnpm migrate:new -m "add prequalification decision table"

# 3. Review generated file in alembic/versions/
# 4. Apply migration
pnpm migrate
```

### Migration Best Practices

- Always review auto-generated migrations before applying
- Test migrations in development before production
- Commit migration files to version control
- Never rollback migrations that have been applied to production for more than a few hours
- For data transformations, create manual migrations using `alembic revision`

## Usage in API Package

The API package imports models and session dependencies from the DB package:

```python
from db.database import get_db, get_compliance_db
from db.models import Application, Borrower, AuditEvent, HmdaDemographic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# In a FastAPI route
@router.get("/applications/{app_id}")
async def get_application(
    app_id: int,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Application).where(Application.id == app_id)
    )
    return result.scalar_one_or_none()
```

For HMDA data access:

```python
@router.get("/analytics/demographics")
async def get_demographics(
    session: AsyncSession = Depends(get_compliance_db),  # compliance_app role
):
    result = await session.execute(select(HmdaDemographic))
    return result.scalars().all()
```

## Testing

Tests use pytest with pytest-asyncio:

```bash
# Start database
pnpm db:start

# Run migrations
pnpm migrate

# Run tests
cd packages/db
uv run pytest -v
```

Test isolation via transaction rollback (fixture in `tests/conftest.py`).

## Package Structure

```
packages/db/
├── src/db/
│   ├── __init__.py       # Package exports
│   ├── config.py         # pydantic-settings config
│   ├── database.py       # Engine, session factories, DatabaseService
│   ├── enums.py          # Domain enums (ApplicationStage, DocumentType, etc.)
│   └── models.py         # SQLAlchemy models (20+ tables)
├── alembic/
│   ├── versions/         # Migration files
│   ├── env.py            # Alembic environment
│   └── script.py.mako    # Migration template
├── tests/
│   ├── conftest.py       # Test fixtures
│   └── test_*.py         # Test modules
├── alembic.ini           # Alembic configuration
└── pyproject.toml        # Dependencies and build config
```
