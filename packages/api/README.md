# This project was developed with assistance from AI tools.

# Mortgage AI API

FastAPI backend for a multi-agent mortgage loan origination system. This is the core backend for the Mortgage AI demo application (Red Hat AI Quickstart).

## Overview

Multi-persona chat application with role-scoped agents, compliance checks, audit trails, and analytics. Five LangGraph agents (public, borrower, loan officer, underwriter, CEO) powered by LangFuse observability and rule-based model routing (fast/capable tiers).

**Key capabilities:**
- Role-scoped agents with 60+ tools across 5 personas
- WebSocket chat with streaming responses
- HMDA data isolation (separate schema + DB role)
- Compliance knowledge base (pgvector + 8 regulatory documents)
- Audit hash chains with tamper detection
- PII masking for CEO role
- Rule-based model routing with confidence escalation
- 1083 tests (unit, functional, integration)

## Directory Structure

```
src/
  main.py              # FastAPI app entry point
  core/
    config.py          # Pydantic Settings (env-driven)
  middleware/
    auth.py            # Keycloak JWT validation + RBAC
    pii.py             # PII masking for CEO responses
  routes/              # API route handlers
    health.py          # Health checks
    public.py          # Public endpoints (products, affordability)
    applications.py    # Application CRUD + status
    decisions.py       # Decision history (read-only)
    documents.py       # Document upload + MinIO storage
    hmda.py            # HMDA demographics (isolated schema)
    analytics.py       # Pipeline + denial + LO performance
    model_monitoring.py # LangFuse model metrics
    audit.py           # Audit trail + hash verification
    admin.py           # Seed data + admin tools
    chat.py            # Public WebSocket (unauthenticated)
    borrower_chat.py   # Borrower WebSocket + history
    loan_officer_chat.py  # LO WebSocket + history
    underwriter_chat.py   # UW WebSocket + history
    ceo_chat.py        # CEO WebSocket + history
    _chat_handler.py   # Shared WebSocket streaming logic
    underwriting.py    # Underwriter-specific endpoints
  schemas/             # Pydantic models (request/response)
  services/            # Business logic
    compliance/        # Compliance checks + KB
    seed/              # Demo data generation
  agents/              # LangGraph agents + tools
    base.py            # Base graph (shields, routing, RBAC)
    registry.py        # Config loading (config/agents/*.yaml)
    public_assistant.py
    borrower_assistant.py
    loan_officer_assistant.py
    underwriter_assistant.py
    ceo_assistant.py
    *_tools.py         # Tool modules per agent
  inference/           # LLM client + safety shields
  admin.py             # SQLAdmin dashboard
tests/
  test_*.py            # Unit tests
  functional/          # Persona functional tests
  integration/         # DB + MinIO integration tests
```

## Agents

Five LangGraph agents, each with role-scoped tools and configuration in `config/agents/*.yaml`:

| Agent | Tools | WebSocket Endpoint |
|-------|-------|-------------------|
| **Public Assistant** | 2 tools (products, affordability) | `ws://host/api/chat` |
| **Borrower Assistant** | 15 tools (intake, docs, status, disclosures, conditions) | `ws://host/api/borrower/chat?token=<jwt>` |
| **Loan Officer Assistant** | 12 tools (pipeline, workflow, communication, KB search) | `ws://host/api/loan-officer/chat?token=<jwt>` |
| **Underwriter Assistant** | 19 tools (queue, risk, conditions, decisions, compliance) | `ws://host/api/underwriter/chat?token=<jwt>` |
| **CEO Assistant** | 12 tools (analytics, audit, model monitoring, product info) | `ws://host/api/ceo/chat?token=<jwt>` |

All agents share a common base graph (`agents/base.py`) with:
- **Input/output safety shields** (Llama Guard, optional)
- **Rule-based model routing** (fast tier for simple queries, capable tier for complex/tools)
- **Confidence escalation** (fast model responses with low confidence auto-escalate to capable model)
- **Tool-level RBAC** (tools check user role before execution)

### Agent Architecture

```
user input -> input_shield -> classify (rule-based) -> agent_fast / agent_capable
                   |                                          |
                   +-(blocked)-> END              tools <-> agent_capable -> output_shield -> END
```

**Rule-based routing:**
- Keyword/pattern matching (no LLM call) classifies queries as SIMPLE or COMPLEX
- COMPLEX queries route directly to capable model with tools
- SIMPLE queries route to fast model (text-only, no tools)
- Fast model responses with low confidence (logprobs or hedging phrases) auto-escalate to capable model

## REST API

Full REST API for application management, document handling, analytics, and audit trails. Authentication via Keycloak JWT (or `AUTH_DISABLED=true` for dev).

**Key routes:**
- `GET /health/` - Service health (DB + S3 + LLM status)
- `GET /api/public/products` - Mortgage product catalog (unauthenticated)
- `POST /api/public/calculate-affordability` - Affordability calculator (unauthenticated)
- `GET /api/applications/` - List applications (paginated, role-scoped, sortable by urgency)
- `POST /api/applications/` - Create application (borrower, admin)
- `PATCH /api/applications/{id}` - Update application (LO, UW, admin)
- `POST /api/applications/{id}/documents` - Upload document (MinIO storage)
- `GET /api/applications/{id}/completeness` - Check document completeness
- `POST /api/hmda/collect` - Collect demographics (isolated schema)
- `GET /api/analytics/pipeline` - Pipeline summary (admin + CEO)
- `GET /api/analytics/denial-trends` - Denial trends by product/time (admin + CEO)
- `GET /api/analytics/lo-performance` - LO performance metrics (admin + CEO)
- `GET /api/analytics/model-monitoring/latency` - Model latency breakdown (admin + CEO)
- `GET /api/audit/application/{id}` - Audit trail for application (admin + CEO)
- `GET /api/audit/verify` - Verify hash chain integrity (admin only)

See [OpenAPI docs](http://localhost:8000/docs) for the full API specification.

## WebSocket Chat Protocol

All agent chat endpoints use WebSocket with streaming token delivery. Authenticated endpoints pass JWT via query parameter.

**Message format (client -> server):**
```json
{"type": "message", "content": "user text here"}
```

**Message formats (server -> client):**
```json
{"type": "token", "content": "partial text"}
{"type": "tool_start", "content": "tool_name"}
{"type": "tool_end", "content": "tool result summary"}
{"type": "safety_override", "content": "refusal reason"}
{"type": "done"}
{"type": "error", "content": "error message"}
```

**Conversation persistence:**
- Public chat: ephemeral (UUID session, no persistence)
- Authenticated chats: persistent via PostgreSQL checkpoint (LangGraph)
- Thread ID format: `user:{userId}:agent:{agent-name}`
- History retrieval: `GET /api/{persona}/conversations/history`

**Development mode:**
When `AUTH_DISABLED=true`, all authenticated endpoints return a development user without requiring a JWT.

## Compliance Features

**HMDA Data Isolation:**
- Demographic data stored in separate `compliance` schema
- Accessed via dedicated DB role with limited grants
- Separate connection string (`COMPLIANCE_DATABASE_URL`)
- Enforced at database level, not application level

**Compliance Knowledge Base:**
- 8 regulatory documents across 3 tiers (federal > agency > internal)
- Vector search via pgvector (768-dim embeddings, HNSW index, cosine similarity)
- Tier-based boosting (federal 1.5x, agency 1.2x, internal 1.0x)
- Conflict detection (numeric thresholds, contradictory directives, same-tier conflicts)
- Documents: TRID, ECOA, ATR/QM, HMDA, FCRA, Fannie Mae, FHA, internal policies

**Compliance Checks:**
- Pure-function rule implementations (ECOA, ATR/QM, TRID)
- Combined runner returns all violations
- Underwriter agent tool (`uw_run_compliance_checks`)
- Compliance guard blocks decisions with open violations

**Audit Trail:**
- Hash chain across all audit events (tamper detection)
- Session-scoped, application-scoped, decision-scoped queries
- Backward trace from decision to contributing events
- Hash verification endpoint (admin only)
- CSV/JSON export (admin + CEO + underwriter)

## Authentication & Authorization

**Keycloak OIDC:**
- JWT validation via `Authorization: Bearer <token>` header or `?token=<jwt>` query param (WebSocket)
- Five roles: `admin`, `borrower`, `loan_officer`, `underwriter`, `ceo`
- Data scoping: borrower sees own applications, LO sees assigned, UW sees in-review, CEO sees all
- Tool-level RBAC: tools validate role before execution
- Development bypass: `AUTH_DISABLED=true` returns a dev user

**PII Masking:**
- CEO role triggers PII masking middleware
- Masks SSN, account numbers, precise addresses
- Applied to JSON response bodies after serialization

## Model Routing & Observability

**LangFuse Integration:**
- All agent interactions traced to LangFuse (if configured)
- Metrics: latency, token usage, error rates, model routing decisions
- Analytics endpoints expose LangFuse-backed metrics

**Model Tiers:**
- Fast tier: text-only responses for simple queries (no tools)
- Capable tier: tool-calling for complex queries
- Confidence escalation: fast responses with low confidence auto-escalate to capable
- Configurable via `LLM_MODEL_FAST` and `LLM_MODEL_CAPABLE` env vars

**Safety Shields:**
- Optional Llama Guard integration (input/output)
- Fail-open on safety model errors
- Configurable via `SAFETY_MODEL` and `SAFETY_ENDPOINT`

## Configuration

Environment variables loaded via Pydantic Settings (`src/core/config.py`). See `.env.example` in the root for a complete list.

**Database:**
- `DATABASE_URL` - PostgreSQL connection string (default: `postgresql+asyncpg://mortgage_ai:password@localhost:5433/mortgage_ai`)
- `COMPLIANCE_DATABASE_URL` - HMDA schema connection (same host, separate role)

**Authentication:**
- `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID` - Keycloak OIDC config
- `AUTH_DISABLED` - Bypass auth for local dev (default: false)

**Storage:**
- `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET` - MinIO/S3 config

**LLM:**
- `LLM_BASE_URL`, `LLM_API_KEY` - OpenAI-compatible endpoint
- `LLM_MODEL_FAST`, `LLM_MODEL_CAPABLE` - Model names for routing
- `SAFETY_MODEL`, `SAFETY_ENDPOINT` - Llama Guard (optional)

**Observability:**
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` - LangFuse (optional)

**Admin:**
- `SQLADMIN_USER`, `SQLADMIN_PASSWORD`, `SQLADMIN_SECRET_KEY` - SQLAdmin dashboard at `/admin`
- `ALLOWED_HOSTS` - CORS allowed origins (comma-separated)

## Development

**Start dev server:**
```bash
cd packages/api
uv run uvicorn src.main:app --reload --port 8000

# Or from root
pnpm --filter api dev
```

**Run tests:**
```bash
# All tests (1083 tests)
AUTH_DISABLED=true uv run pytest -v

# Specific test types
AUTH_DISABLED=true uv run pytest -m functional  # Functional tests
AUTH_DISABLED=true uv run pytest -m integration # Integration tests (requires containers)
AUTH_DISABLED=true uv run pytest -k "test_health" # Pattern match

# Coverage
AUTH_DISABLED=true uv run pytest --cov=src --cov-report=term-missing
```

**Linting and formatting:**
```bash
uv run ruff check src/          # Check
uv run ruff check src/ --fix    # Auto-fix
uv run ruff format src/         # Format
```

**Database setup:**
```bash
make db-start      # Start PostgreSQL container (port 5433)
make db-upgrade    # Run Alembic migrations
```

**Access points:**
- API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs
- SQLAdmin dashboard: http://localhost:8000/admin
- Database: `postgresql://localhost:5433/mortgage_ai`

See the [DB package README](../db/README.md) for migration and schema details.
