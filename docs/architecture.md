<!-- This project was developed with assistance from AI tools. -->
# Architecture

This multi-agent AI reference application is built to demonstrate production-grade patterns in a regulated domain. The architecture balances MVP maturity (rapid iteration, focused scope) with production structure (clear boundaries, extensible patterns, hardening paths). This document describes the system design for developers and architects evaluating or adapting this Quickstart.

## System Overview

### Component Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Browser (Client)                           │
└─────────┬───────────────────────────────────────────────────────────┘
          │ HTTPS / WebSocket
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    UI Package (React + Vite)                        │
│  - TanStack Router (file-based routing)                             │
│  - TanStack Query (server state)                                    │
│  - Tailwind CSS + shadcn/ui (components)                            │
└─────────┬───────────────────────────────────────────────────────────┘
          │ HTTP/WS (port 8000)
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    API Package (FastAPI)                            │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Middleware Layer                                              │  │
│  │  - JWT validation (Keycloak OIDC)                             │  │
│  │  - PII masking (role-based)                                   │  │
│  │  - CORS                                                        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ REST Routes                                                    │  │
│  │  - /api/applications, /api/documents, /api/conditions         │  │
│  │  - /api/analytics (CEO dashboards)                            │  │
│  │  - /admin (SQLAdmin panel)                                    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ WebSocket Chat Endpoints                                      │  │
│  │  - /api/public/chat (unauthenticated)                         │  │
│  │  - /api/borrower/chat, /api/lo/chat, /api/uw/chat, /api/ceo/chat  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Agent System (LangGraph)                                      │  │
│  │  - Registry (YAML config → graph builder)                     │  │
│  │  - Router (rule-based intent → model tier)                    │  │
│  │  - Agent graphs (5 personas, tool-augmented)                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────┬───────────────────────────┬──────────────────────────┬────────┘
      │                           │                          │
      ▼                           ▼                          ▼
┌──────────┐            ┌──────────────────┐    ┌────────────────────┐
│ Keycloak │            │  LlamaStack      │    │ LangFuse           │
│ (OIDC)   │            │  (Model Router)  │    │ (Observability)    │
└──────────┘            └──────────────────┘    └────────────────────┘
      │                           │                          │
      │                           │                          │
      ▼                           ▼                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                             │
│  ┌─────────────┐  ┌─────────┐  ┌──────────┐  ┌────────────────┐   │
│  │ PostgreSQL  │  │  MinIO  │  │  Redis   │  │  ClickHouse    │   │
│  │  + pgvector │  │  (S3)   │  │ (LF)     │  │  (LF)          │   │
│  └─────────────┘  └─────────┘  └──────────┘  └────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Monorepo Structure

The application is organized as a Turborepo monorepo with three packages:

```
packages/
├── ui/                 # React frontend (pnpm)
│   ├── src/
│   │   ├── routes/    # TanStack Router file-based routing
│   │   ├── components/
│   │   ├── hooks/     # TanStack Query hooks
│   │   └── lib/       # Utilities, types
│   └── package.json
│
├── api/                # FastAPI backend (uv/Python)
│   ├── src/
│   │   ├── routes/    # REST endpoint handlers
│   │   ├── agents/    # LangGraph agent definitions + tools
│   │   ├── middleware/# Auth, PII masking, CORS
│   │   ├── schemas/   # Pydantic request/response models
│   │   └── core/      # Config, auth logic, error handling
│   └── pyproject.toml
│
└── db/                 # Database models + migrations (uv/Python)
    ├── src/db/
    │   ├── models.py  # SQLAlchemy ORM models
    │   ├── enums.py   # Shared enums (stages, statuses)
    │   └── database.py# Async session factory
    ├── alembic/        # Migration scripts
    └── pyproject.toml
```

**Dependency flow:** `ui → api → db` (ui calls api via HTTP, api imports db models as Python dependency).

### Environment Profiles

The `compose.yml` supports layered profiles to run only what you need:

| Profile | Services Added | Use Case |
|---------|---------------|----------|
| (none) | postgres, minio, api, ui | Minimal stack for development |
| `auth` | + keycloak | Test OIDC authentication flow |
| `ai` | + llamastack | LlamaStack model router (optional) |
| `observability` | + redis, clickhouse, langfuse-web, langfuse-worker | LLM tracing and monitoring |
| `full` | all of the above | Full stack for integration testing |

## Agent System

The agent system is the core differentiator. It uses **LangGraph** for orchestration, a **rule-based router** for model tier selection, and **role-scoped tools** to enforce business logic and compliance constraints at the agent level.

### Agent Architecture

#### Registry and Graph Loading

Agents are defined declaratively in YAML configuration files (`config/agents/*.yaml`). Each YAML file specifies:

- System prompt (persona, tone, capabilities)
- Tool list (functions the agent can call)
- Tool RBAC (which user roles can invoke each tool)

The agent registry (`packages/api/src/agents/registry.py`) loads these configs, builds LangGraph graphs on demand, and caches them in memory. Graphs are rebuilt automatically when the config file changes (mtime-based detection).

```python
# Usage in a WebSocket route handler
from agents.registry import get_agent

agent = get_agent("borrower-assistant")  # Returns compiled LangGraph graph
response = await agent.ainvoke({"messages": [user_message], ...})
```

#### Graph Structure

Each agent uses a common graph structure with safety shields and rule-based routing:

```
input_shield → classify → [agent_fast | agent_capable] → tools → output_shield → END
                              (text-only)   (tool-calling)
```

**Nodes:**

- **input_shield:** Llama Guard safety check on user input (when `SAFETY_MODEL` configured). Blocks unsafe requests.
- **classify:** Rule-based intent classifier (no LLM call). Matches keywords/patterns to route SIMPLE → fast tier, COMPLEX → capable tier.
- **agent_fast:** Fast/small model (e.g., `gpt-4o-mini`). No tools bound. Text-only responses. Requests logprobs for confidence scoring.
- **agent_capable:** Capable/large model (e.g., `gpt-4o`, local 70B model). Tools bound. Reliable function calling.
- **tools:** LangChain `ToolNode` that executes tool calls from the LLM.
- **tool_auth:** Pre-tool authorization node (RBAC Layer 3). Checks user role against `allowed_roles` for each tool before execution.
- **output_shield:** Llama Guard safety check on agent output. Replaces unsafe responses with a refusal message.

**Confidence escalation:** If the fast model returns a low-confidence response (low token logprobs or hedging phrases like "I'm not sure"), the response is discarded and the graph re-routes to `agent_capable` for a second pass.

#### Agent Personas

The system includes five agents, each scoped to a user role:

| Agent | User Role | Tool Count | Key Capabilities |
|-------|-----------|------------|------------------|
| **public-assistant** | Anonymous | 2 | Product info, affordability calculator |
| **borrower-assistant** | Borrower | 15 | Application CRUD, document status, disclosure acknowledgment, condition responses, pre-qualification |
| **loan-officer-assistant** | Loan Officer | 12 | Pipeline management, document review requests, underwriting submission, communication drafting, compliance KB search |
| **underwriter-assistant** | Underwriter | 19 | Risk assessment, compliance checks (ECOA, ATR/QM, TRID), preliminary decision recommendation, condition generation |
| **ceo-assistant** | CEO | 12 | Pipeline analytics, denial trends, LO performance, audit trail search, model monitoring |

**Tool design philosophy:** Tools are single-purpose functions that read or write application state. Complex workflows (e.g., "submit application to underwriting") decompose into multiple tool calls orchestrated by the LLM. This keeps each tool testable and the agent's reasoning transparent.

#### Rule-Based Routing

Model tier selection happens **before** the LLM is invoked, using keyword/pattern matching:

```python
# Simplified from packages/api/src/inference/router.py
def classify_query(user_message: str) -> str:
    """Return 'fast_small' or 'capable_large' based on message patterns."""

    # Tool-use signals → capable tier (tool calling requires reliable model)
    if any(keyword in msg_lower for keyword in [
        "application", "document", "upload", "submit", "status",
        "condition", "underwriting", "compliance", "risk"
    ]):
        return "capable_large"

    # Information queries → fast tier (simple retrieval, no side effects)
    if any(keyword in msg_lower for keyword in [
        "what is", "how do", "can you explain", "tell me about"
    ]):
        return "fast_small"

    # Default to capable tier when uncertain
    return "capable_large"
```

This approach is **cheaper** (no LLM inference for routing) and **more predictable** (classification logic is explicit, not learned) than using an LLM classifier. The trade-off: rules require maintenance as the tool set evolves.

### Tool System

Tools are Python functions decorated with `@tool` from LangChain. Each tool:

- Has a docstring (the LLM sees this as the tool description)
- Accepts typed parameters (Pydantic schema extracted automatically)
- Returns structured data (string, dict, or raises an exception)
- May have RBAC restrictions (declared in agent config YAML)

**Example tool:**

```python
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

@tool
async def get_application_summary(
    application_id: int,
    session: AsyncSession,
) -> str:
    """Get a summary of the application including status, stage, and key details.

    Use this when the borrower asks about their application status or needs
    an overview of where things stand.

    Args:
        application_id: The ID of the application to summarize.
    """
    result = await session.execute(
        select(Application).where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        return f"Application {application_id} not found."

    return f"Application {app.id} is in {app.stage} stage..."
```

**RBAC enforcement (Layer 3):** The `tool_auth` node (see graph structure above) checks each tool call against the user's role before execution. If the user's role is not in the tool's `allowed_roles` list, the tool call is blocked and replaced with an error message back to the LLM.

### Conversation Persistence

Agent conversations are persisted using LangGraph's checkpointer pattern:

- Each conversation has a unique `thread_id` (stored in `conversations` table)
- Graph state (messages, model tier, escalation flags, user context) is checkpointed after each turn
- On reconnect, the graph state is loaded from the checkpoint and the conversation continues

**Storage:** Currently uses an in-memory checkpointer (SQLite or Postgres checkpointer can be swapped in for production).

## Data Architecture

### Database Schema

The application uses **PostgreSQL 16** with the **pgvector** extension for embeddings. The schema supports the mortgage lending lifecycle from inquiry through closing.

**Core entities:**

- **Borrower:** User profile linked to Keycloak identity (`keycloak_user_id`). Stores PII (SSN, DOB), employment status.
- **Application:** Loan application. Tracks stage (inquiry, pre-qualification, application, submitted, underwriting, conditional approval, approved, denied, withdrawn), loan type, property details, loan amount.
- **ApplicationBorrower:** Junction table supporting co-borrowers (many-to-many).
- **Document:** File metadata and S3 key. Status (pending, extracted, failed). Type (paystub, W2, bank statement, etc.).
- **Condition:** Underwriting conditions issued by the underwriter. Severity (critical, standard, informational), status (open, satisfied, waived, expired).
- **Decision:** Underwriting decisions (approve, conditional approval, deny, refer). Includes decision rationale and timestamp.
- **AuditEvent:** Append-only audit log with hash chaining. Captures every agent action, data access, and human decision.
- **CreditReport:** Simulated credit data (no real bureau integration).
- **RateLock:** Rate lock records with effective dates.
- **KBDocument / KBChunk:** Compliance knowledge base with pgvector embeddings for semantic search.

**Enums (shared):** `ApplicationStage`, `LoanType`, `DocumentType`, `DocumentStatus`, `ConditionStatus`, `ConditionSeverity`, `DecisionType`, `UserRole`, `EmploymentStatus`. Defined in `packages/db/src/db/enums.py` as Python enums, mapped to PostgreSQL `VARCHAR` (not native enums for flexibility).

### HMDA Data Isolation

The system demonstrates **dual-data-path isolation** for HMDA (Home Mortgage Disclosure Act) demographic data to comply with fair lending regulations:

**Separate PostgreSQL roles:**

- `lending_app` role: Default application role. **Cannot** query `hmda.borrower_demographics` table.
- `compliance_app` role: Compliance-only role. **Can** query HMDA schema. Used exclusively by HMDA reporting endpoints.

**Isolation mechanism:**

1. HMDA data stored in a separate schema (`hmda.borrower_demographics`).
2. Separate database connections:
   - `DATABASE_URL` → `lending_app` role (used by all agent tools, standard API endpoints)
   - `COMPLIANCE_DATABASE_URL` → `compliance_app` role (used only by HMDA collection/reporting endpoints)
3. Application code enforces connection usage by endpoint scope.

**Result:** Agent tools and lending workflows **cannot** access demographic data, even if compromised. HMDA reporting endpoints can read demographics but are restricted to compliance role users.

### Compliance Knowledge Base

The compliance KB stores regulatory content (TRID, ECOA, ATR/QM, HMDA, FCRA, Fannie Mae, FHA, internal policies) as vector embeddings for retrieval-augmented generation (RAG).

**Schema:**

- **KBDocument:** Document metadata (title, tier, source, version). Tier: `federal` (CFR), `agency` (Fannie Mae, FHA), or `internal` (company policies).
- **KBChunk:** Chunk of document text with:
  - `embedding`: pgvector `Vector(768)` — generated by the local embedding provider (`nomic-ai/nomic-embed-text-v1.5` via sentence-transformers, or a remote OpenAI-compatible endpoint)
  - `metadata`: JSONB (section title, chunk index, parent document ID)
  - HNSW index on embedding column for fast cosine similarity search

**Tiered boosting:** Search results apply tier-based score multipliers:

- Federal (CFR) → 1.5x
- Agency (Fannie Mae, FHA) → 1.2x
- Internal → 1.0x (no boost)

This prioritizes authoritative sources over internal policies when both match the query.

**Conflict detection:** The `kb_search` tool detects conflicting guidance across sources:

- Numeric conflicts (different values for the same threshold, e.g., DTI limits)
- Contradictory directives ("always require X" vs "never require X" from different docs)
- Same-tier conflicts (e.g., two federal regulations contradicting each other)

When conflicts are detected, the agent is instructed to surface all variants to the user and recommend escalation.

### Audit Trail

Every agent action, data access, and human decision is logged to the `audit_events` table with hash chaining for tamper detection.

**Schema:**

- `event_type`: `agent_action`, `data_access`, `human_decision`, `model_inference`, `pii_access`, `compliance_check`
- `event_data`: JSONB (action name, parameters, result summary, timestamps)
- `hash`: SHA-256 hash of `(previous_hash || current_event_data)`
- `previous_hash`: Hash of the prior event in the chain

**Hash chain verification:**

```python
def verify_audit_chain(events: list[AuditEvent]) -> bool:
    """Verify that audit trail hashes form a valid chain."""
    for i, event in enumerate(events):
        if i == 0:
            expected_hash = hashlib.sha256(event.event_data.encode()).hexdigest()
        else:
            expected_hash = hashlib.sha256(
                (events[i-1].hash + event.event_data).encode()
            ).hexdigest()
        if event.hash != expected_hash:
            return False
    return True
```

If any event is modified after creation, the hash breaks and verification fails.

### Document Storage

Documents are stored in **MinIO** (S3-compatible object storage). The `documents` table stores metadata:

- `s3_key`: Object key in the S3 bucket
- `file_name`: Original uploaded filename
- `content_type`: MIME type
- `size_bytes`: File size
- `status`: `pending` (uploaded but not processed), `extracted` (text extracted successfully), `failed` (extraction error)
- `extracted_text`: Full text extracted from the document (stored in DB for search/RAG, not in S3)

**Document extraction pipeline (Phase 2):**

1. Borrower uploads via WebSocket (base64-encoded chunks)
2. API validates file type, size, assembles chunks, uploads to MinIO
3. Background task extracts text (PDF → pdfplumber, images → Tesseract OCR)
4. Extracted text stored in `extracted_text` column, status → `extracted`

**Document routing:** HMDA-sensitive documents (e.g., government ID) trigger isolation:

- Document metadata stored in `documents` table (accessible to lending app)
- Demographic data extracted from the document routed to `hmda.borrower_demographics` (compliance app only)

## Security Architecture

### Authentication (Keycloak OIDC)

The API uses **Keycloak** for identity management and authentication:

- **Protocol:** OpenID Connect (OIDC) with JWT bearer tokens
- **Token validation:** JWT signature verified against Keycloak's JWKS endpoint (RS256)
- **Token claims:**
  - `sub`: Keycloak user ID (maps to `borrowers.keycloak_user_id`)
  - `email`, `name`: User profile data
  - `realm_access.roles`: Assigned roles (borrower, loan_officer, underwriter, ceo, admin)

**JWKS caching:** The API caches Keycloak's public keys in memory for 5 minutes (configurable via `JWKS_CACHE_TTL`). On key rotation, the cache auto-refreshes on the first JWT with a new `kid` (key ID).

**Auth bypass mode:** Setting `AUTH_DISABLED=true` disables JWT validation for local development and testing. In this mode:

- All endpoints accept requests without an `Authorization` header
- A synthetic dev user is injected with configurable role via `X-Dev-Role` header
- PII masking still applies based on the dev user's role

**Security note:** `AUTH_DISABLED` is for development only. Production deployments must enforce Keycloak authentication.

### Role-Based Access Control (RBAC)

RBAC is enforced at three layers:

#### Layer 1: Route-Level (FastAPI Dependencies)

Routes require specific roles via the `require_roles()` dependency:

```python
from db.enums import UserRole
from middleware.auth import require_roles

@router.get("/pipeline", dependencies=[Depends(require_roles(UserRole.LOAN_OFFICER, UserRole.ADMIN))])
async def get_pipeline(...):
    """Only loan officers and admins can access."""
```

#### Layer 2: Data Scope Filtering (SQL WHERE Clauses)

Each authenticated user gets a `data_scope` object that defines:

- **Scope type:** `none` (CEO — no data access), `own` (borrower — own applications only), `assigned` (LO, UW — assigned applications only), `all` (admin — everything)
- **Filter conditions:** SQL filter clauses applied automatically to queries

```python
# Borrower: data_scope.type = "own"
# SQL: WHERE borrowers.keycloak_user_id = '<user_id>'

# Loan Officer: data_scope.type = "assigned"
# SQL: WHERE applications.assigned_to = '<user_id>'

# Admin: data_scope.type = "all"
# SQL: (no filter)
```

Queries that return application data apply the user's data scope filter to prevent horizontal privilege escalation.

#### Layer 3: Tool RBAC (LangGraph Pre-Tool Authorization)

Agent tools declare `allowed_roles` in the agent config YAML:

```yaml
# config/agents/borrower-assistant.yaml
tools:
  - name: start_application
    allowed_roles:
      - borrower

  - name: submit_to_underwriting
    allowed_roles:
      - loan_officer
      - admin
```

The `tool_auth` graph node checks the user's role before executing each tool call. Unauthorized tool calls are blocked with an error message returned to the LLM.

**Why three layers?** Defense in depth. Route-level RBAC prevents unauthorized API access. Data scope filtering prevents lateral movement across applications. Tool RBAC prevents agents from executing privileged actions even if the LLM hallucinates a tool call.

### PII Masking

The **PII masking middleware** (`packages/api/src/middleware/pii.py`) masks sensitive fields in JSON response bodies when the user's data scope has `pii_mask=True`:

**Masked fields:**

- `ssn` → `***-**-1234` (last 4 digits visible)
- `dob` → `YYYY-**-**` (year visible)
- `account_number` → `****5678` (last 4 visible)

**How it works:**

1. Auth middleware sets `request.state.pii_mask = True` for users with CEO role (CEO sees aggregates, not PII).
2. PII masking middleware runs after every response.
3. If `pii_mask=True` and response is JSON, recursively walk the structure and apply masking functions.
4. Return masked response body.

**Result:** CEO endpoints (pipeline analytics, denial trends, LO performance) receive masked data automatically. No per-endpoint masking logic required.

## Observability

### LangFuse Integration

The application uses **LangFuse** (self-hosted) for LLM observability:

- **Traces:** Every agent invocation creates a trace with LLM calls, tool executions, token counts, latencies.
- **Prompt versioning:** System prompts stored as LangFuse prompt templates (not yet implemented — planned for production hardening).
- **User feedback:** UI can submit thumbs-up/down on agent responses (captured in LangFuse).

**Infrastructure:**

- **LangFuse web:** Next.js app (port 3001)
- **LangFuse worker:** Background worker for async processing
- **Redis:** Session cache, job queue
- **ClickHouse:** Time-series storage for traces and metrics
- **MinIO:** S3 storage for trace payloads

**Configuration:**

- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`: API keys (auto-provisioned by init script)
- `LANGFUSE_HOST`: LangFuse server URL (e.g., `http://langfuse-web:3000`)

When these env vars are set, the API automatically wraps all LangGraph invocations with LangFuse callbacks.

### Model Monitoring (CEO Dashboard)

The CEO agent has access to model monitoring tools backed by LangFuse analytics:

- **Model latency:** P50/P90/P99 latencies by model and tier
- **Token usage:** Input/output token counts and cost estimates
- **Error rates:** Failed inferences by model and error type
- **Routing distribution:** Fast vs capable tier usage over time

These tools query LangFuse's ClickHouse backend via REST API.

### Logging and Error Handling

The API uses Python's `logging` module with structured log output:

- **Production:** JSON-formatted logs (parseable by log aggregators)
- **Development:** Human-readable console logs with color

**What's logged:**

- Agent actions (tool calls, model tier selection, confidence escalation)
- Auth events (JWT validation, RBAC denials)
- Safety shield blocks (input/output violations)
- Compliance check results (pass/fail for ECOA, ATR/QM, TRID)

**What's NEVER logged:**

- PII (SSN, DOB, account numbers)
- Secrets (API keys, passwords, JWT tokens)
- Full document text (only excerpts with PII redacted)

Error responses follow **RFC 7807** (Problem Details for HTTP APIs):

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "Application 12345 not found."
}
```

## Deployment

### Container Images

Each package builds a container image:

- **UI:** Nginx serving static build output (port 8080)
- **API:** FastAPI with uvicorn (port 8000)

**Base images:**

- UI: `registry.access.redhat.com/ubi9/nginx-122`
- API: `registry.access.redhat.com/ubi9/python-311`

### Helm Chart

The `deploy/helm/` directory contains a Helm chart for deploying to OpenShift:

- Deployments for UI, API, DB, Keycloak, MinIO, LangFuse
- Services, Routes (OpenShift), ConfigMaps, Secrets
- Health checks, resource limits, autoscaling config

**Installation:**

```bash
helm install mortgage-ai ./deploy/helm/ \
  --set api.llm.baseUrl="https://openshift-ai.example.com/v1" \
  --set api.llm.apiKey="sk-..." \
  --set keycloak.adminPassword="secure-password"
```

### Configuration Management

Configuration follows the **12-factor app** pattern:

- **Environment variables:** All runtime config (DB URLs, API keys, feature flags)
- **Config files:** Static configs (agent YAML, LlamaStack model routing, Keycloak realm JSON)
- **Secrets:** Managed via OpenShift Secrets or Helm values (never in Git)

**Environment variable groups:**

| Group | Examples | Default (dev) |
|-------|----------|---------------|
| Database | `DATABASE_URL`, `COMPLIANCE_DATABASE_URL` | `postgresql+asyncpg://user:password@localhost:5433/mortgage-ai` |
| Auth | `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `AUTH_DISABLED` | `http://localhost:8080`, `mortgage-ai`, `mortgage-ai-ui`, `true` |
| LLM | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_FAST`, `LLM_MODEL_CAPABLE` | `https://api.openai.com/v1`, `not-needed`, `gpt-4o-mini`, `gpt-4o-mini` |
| Storage | `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET` | `http://localhost:9090`, `minio`, `miniosecret`, `documents` |
| Observability | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | (unset — tracing disabled) |

## Extension Points

Developers adapting this Quickstart to their domain should consider:

### Adding a New Agent

1. Create `config/agents/<agent-name>.yaml` with system prompt, tools, RBAC.
2. Create `packages/api/src/agents/<agent_name>.py` with `build_graph()` function.
3. Register in `packages/api/src/agents/registry.py` → `_AGENT_MODULES` dict.
4. Add WebSocket route in `packages/api/src/routes/`.
5. Add tests in `packages/api/tests/test_agents.py`.

### Adding a Tool

1. Define tool function in `packages/api/src/agents/<role>_tools.py`:

   ```python
   @tool
   async def my_new_tool(param: int, session: AsyncSession) -> str:
       """Description visible to the LLM."""
       # Implementation
   ```

2. Add tool to agent's YAML config (`tools` list).
3. Add RBAC rules if needed (`allowed_roles`).
4. Add tests in `packages/api/tests/test_tools.py`.

### Integrating a Real LLM Provider

Replace the mock LlamaStack / LMStudio setup:

1. Set `LLM_BASE_URL` to your provider's OpenAI-compatible endpoint (e.g., `https://api.together.ai/v1`).
2. Set `LLM_API_KEY` to your API key.
3. Set `LLM_MODEL_FAST` and `LLM_MODEL_CAPABLE` to model names from your provider.
4. (Optional) Configure LlamaStack's `run.yaml` to route to multiple providers (OpenAI for fast, Groq for capable, etc.).

## Summary

This application demonstrates how to architect a multi-agent AI system for a regulated domain:

- **Agent orchestration:** LangGraph graphs with rule-based routing, tool RBAC, safety shields.
- **Data isolation:** Dual PostgreSQL roles enforce HMDA separation.
- **Compliance patterns:** Vector KB with tiered boosting, compliance check tools, audit hash chain.
- **Production structure:** Clear package boundaries, configuration-driven extensibility, observability hooks.

The architecture is designed for **learning and adaptation** — not as a production mortgage system, but as a reference for building your own domain-specific multi-agent application on Red Hat AI.
