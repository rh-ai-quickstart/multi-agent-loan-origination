# Documentation Review -- Pre-Phase 3

Reviewer: Technical Writer
Date: 2026-02-26
Scope: All documentation (READMEs, plans, code comments, env config)

---

## DOC-01: Root README describes template, not mortgage application

**Severity:** Critical
**Location:** `README.md:1-3`
**Description:** The root README opens with "A ready-made template for creating new AI Quickstarts" and reads as a generic template README throughout. It does not describe Summit Cap Financial, the mortgage lending domain, the multi-agent architecture, the five personas, or any domain-specific functionality. A developer or stakeholder arriving at this repo gets no indication of what the application actually does. The "Quick Start" section also omits critical services (MinIO, Keycloak) and environment variables (LLM_BASE_URL, LLM_API_KEY) needed to actually run the application.
**Recommendation:** Rewrite the root README to reflect the actual project: one-line description of Summit Cap Financial, the mortgage lending use case, the five personas, a quick-start that covers all required services (including MinIO and LLM endpoint config), and links to the architecture and plan docs. The current template content can be trimmed to a "Template Origin" footnote.

---

## DOC-02: No .env.example file exists

**Severity:** Critical
**Location:** Missing file (project root)
**Description:** The project has no `.env.example` or equivalent documenting required and optional environment variables. `packages/api/src/core/config.py` defines 27+ settings across 7 groups (app, CORS, database, auth, safety, LLM, storage, observability), but a new developer has no single reference for what to configure. The root README references a `.env` file with only 5 variables (`DATABASE_URL`, `DB_ECHO`, `DEBUG`, `ALLOWED_HOSTS`, `VITE_API_BASE_URL`) which is a small fraction of the actual settings. Critical variables like `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_FAST`, `LLM_MODEL_CAPABLE`, `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `COMPLIANCE_DATABASE_URL`, `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `LANGFUSE_*`, and `SAFETY_*` are undocumented.
**Recommendation:** Create a `.env.example` at project root with all environment variables, grouped and commented. Mark which are required vs. optional, and note which have defaults suitable for local development.

---

## DOC-03: Architecture doc references non-existent file paths

**Severity:** Warning
**Location:** `plans/architecture.md:250,776,828,848`
**Description:** The architecture document references paths that do not exist in the codebase:
- `packages/db/src/summit_cap_db/database.py` -- actual path is `packages/db/src/db/database.py`
- `packages/api/src/summit_cap/` -- actual path is `packages/api/src/`
- `python -m summit_cap.seed` -- actual module path is `src.seed` (based on `packages/api/src/seed.py`)
- Section 10 project tree shows `packages/api/src/summit_cap/` and `packages/db/src/summit_cap_db/` which do not exist

The architecture was written before the package naming was finalized. Every `summit_cap` and `summit_cap_db` path reference is wrong.
**Recommendation:** Search and replace all `summit_cap` path references in `plans/architecture.md` to match the actual codebase structure.

---

## DOC-04: Interface contracts reference wrong schema path

**Severity:** Warning
**Location:** `plans/interface-contracts-phase-1.md:28`
**Description:** The interface contracts document says Python schemas live at `packages/api/src/summit_cap/schemas/`. The actual path is `packages/api/src/schemas/`.
**Recommendation:** Update the path reference.

---

## DOC-05: Architecture doc references ADRs that do not exist

**Severity:** Warning
**Location:** `plans/architecture.md:877-919` (Section 11)
**Description:** The architecture document references 7 ADRs stored in `plans/adr/` (e.g., `plans/adr/0001-hmda-data-isolation.md` through `plans/adr/0007-deployment.md`). The `plans/adr/` directory does not exist. The ADR summaries are inline in the architecture doc but the referenced detail files are missing.
**Recommendation:** Either create the ADR files or remove the file path references and mark the inline summaries as the canonical record.

---

## DOC-06: Architecture doc says "PoC maturity" but CLAUDE.md says "MVP"

**Severity:** Warning
**Location:** `plans/architecture.md:15` and throughout (~15 occurrences)
**Description:** The architecture document consistently refers to "PoC maturity" and "PoC-level" throughout (e.g., lines 15, 167, 246, 389, 674, 702, 714). However, CLAUDE.md states "Current maturity: MVP" and `.claude/rules/maturity-expectations.md` defines MVP as the current maturity level, with different expectations than PoC. The maturity level affects testing requirements, error handling depth, and documentation standards.
**Recommendation:** Update `plans/architecture.md` to consistently use "MVP" instead of "PoC" to match the project's declared maturity level.

---

## DOC-07: DB README documents wrong default port

**Severity:** Warning
**Location:** `packages/db/README.md:402-404,424-425`
**Description:** The DB README documents the database port as 5432 in the connection string examples and the container reference table. The actual default in `compose.yml` maps host port 5433 to container port 5432 (`"5433:5432"`). Both `packages/db/src/db/config.py` and `packages/api/src/core/config.py` default to port 5433. A developer following the README's `DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/summit-cap` would fail to connect.
**Recommendation:** Update all port references in the DB README from 5432 to 5433 for the host-side connection.

---

## DOC-08: Root README "Development URLs" section lists wrong frontend port

**Severity:** Warning
**Location:** `README.md:129`
**Description:** The README lists the frontend at `http://localhost:3000`. While this is the externally mapped port in `compose.yml` (`"3000:8080"`), the Vite dev server (when running `make dev` / `pnpm dev` for local development) runs on port 5173 by default, and the CORS setting `ALLOWED_HOSTS` defaults to `["http://localhost:5173"]`. The README should distinguish between container mode (port 3000) and local dev mode (port 5173) URLs.
**Recommendation:** Split the "Development URLs" section into "Local Dev" (Vite on 5173) and "Container" (nginx on 3000) modes.

---

## DOC-09: API README is template boilerplate, not project-specific

**Severity:** Warning
**Location:** `packages/api/README.md` (entire file)
**Description:** The API README is unchanged from the quickstart template. It describes a generic FastAPI app with example "users" endpoints. It does not mention any of the actual domain routes (applications, documents, HMDA, chat, borrower_chat, admin), services (application, document, extraction, audit, compliance, conversation, rate_lock, condition, disclosure), middleware (auth, PII masking), agents (public_assistant, borrower_assistant), or the inference layer (LLM client, model router, safety shields). The directory structure section shows a minimal `src/` tree that does not match the actual 10+ route files, 15+ service files, agents directory, middleware directory, or inference directory.
**Recommendation:** Rewrite the API README to document the actual project structure, routes, services, middleware, agents, and configuration. At minimum, update the directory structure tree and remove fake "users" examples.

---

## DOC-10: UI README component list is stale

**Severity:** Info
**Location:** `packages/ui/README.md:42-54`
**Description:** The UI README lists a `quick-stats` component directory that does not exist in the codebase. The component directory listing appears to be from an earlier iteration. The actual component tree matches most of the listing but `quick-stats/` is missing.
**Recommendation:** Remove `quick-stats/` from the directory listing, or note it as planned.

---

## DOC-11: DB README examples use deprecated patterns

**Severity:** Info
**Location:** `packages/db/README.md:148-149`
**Description:** The DB README model example imports `from sqlalchemy.orm import declarative_base` and `from db.database import Base`. The actual codebase now uses `class Base(DeclarativeBase)` (SQLAlchemy 2.0 pattern, as seen in `packages/db/src/db/database.py:25`). Additionally, the DB README uses `from db import ...` import paths, but the actual Python package structure uses `from db.database import ...` or the package is consumed as a workspace dependency.
**Recommendation:** Update the code examples in the DB README to use the current SQLAlchemy 2.0 `DeclarativeBase` pattern and correct import paths.

---

## DOC-12: Technical debt tracker has resolved items still marked open

**Severity:** Info
**Location:** `plans/technical-debt.md:28-29,49,97-101`
**Description:** Several items in `technical-debt.md` have been resolved but are still listed as open:
- D18 ("DB package reads os.environ directly"): `packages/db/src/db/config.py` now uses pydantic-settings (`DatabaseSettings(BaseSettings)`)
- D5 ("CORS allow_methods too permissive"): `main.py:45-46` now explicitly lists methods and headers
- "Pydantic v2 deprecated config style": `packages/api/src/core/config.py` now uses `SettingsConfigDict(...)` not inner `Config` class
- "SQLAlchemy deprecated API usage": `packages/db/src/db/database.py:25` now uses `class Base(DeclarativeBase)`
**Recommendation:** Move these items to the "Resolved" table at the bottom of `technical-debt.md`.

---

## DOC-13: Architecture compose profile table does not match reality

**Severity:** Warning
**Location:** `plans/architecture.md:618-624`
**Description:** The architecture document's compose profile table says the default (no profile) stack is "postgres, api, ui". The actual compose.yml default profile includes MinIO as well (it has no profile restriction). The architecture doc does not mention MinIO at all as a required service. MinIO is required for document storage (the API service depends on it via `depends_on`).
**Recommendation:** Update the architecture doc's compose profile table and service inventory to include MinIO.

---

## DOC-14: No documentation for WebSocket chat protocol

**Severity:** Warning
**Location:** Missing (no standalone doc)
**Description:** The WebSocket chat protocol is documented only in `plans/architecture.md:693-699` with a high-level message schema. There is no developer-facing documentation for how to connect to the chat endpoints (`/api/chat`, `/api/borrower-chat`), what authentication is required, the message format, or how streaming works. The actual implementation has two separate WebSocket routes (public chat and borrower chat) with different behaviors, but this is not documented anywhere accessible to a frontend developer.
**Recommendation:** Add a WebSocket protocol section to the API README or create a standalone doc covering connection setup, authentication, message types, and the two chat endpoint behaviors.

---

## DOC-15: Interface contracts incomplete for Phase 2 routes

**Severity:** Warning
**Location:** `plans/interface-contracts-phase-1.md`
**Description:** The interface contracts document covers only Phase 1 routes (health, products, affordability calculator, HMDA collect, admin seed). All Phase 2 routes are undocumented in any contracts document:
- `POST /api/applications/` (create application)
- `GET/PATCH /api/applications/{id}` (get/update application)
- `POST /api/documents/upload` (document upload)
- `GET /api/documents/{id}/status` (document processing status)
- `POST /api/hmda/collect` (with borrower_id parameter added in Phase 2)
- `GET /api/applications/{id}/conditions` (conditions listing)
- `POST /api/applications/{id}/conditions/{id}/respond` (condition response)
- `GET /api/applications/{id}/rate-lock` (rate lock status)
- `POST /api/applications/{id}/disclosures/acknowledge` (disclosure acknowledgment)
- `GET /api/conversations/{thread_id}/history` (conversation history)

There is no `interface-contracts-phase-2.md`.
**Recommendation:** Create an interface contracts document for Phase 2 routes, or extend the Phase 1 document. This is important for Phase 3 work where the loan officer persona will build on these endpoints.

---

## DOC-16: Architecture config file references do not exist

**Severity:** Info
**Location:** `plans/architecture.md:756-758,799-815`
**Description:** The architecture references several config files that do not exist:
- `config/app.yaml` -- does not exist
- `config/agents/lo-assistant.yaml` -- does not exist (only `public-assistant.yaml` and `borrower-assistant.yaml` exist)
- `config/agents/underwriter-assistant.yaml` -- does not exist
- `config/agents/ceo-assistant.yaml` -- does not exist
- `data/compliance-kb/` directory -- does not exist
- `data/demo/seed.json` -- does not exist

These are future artifacts that the architecture describes but implementation has not yet created.
**Recommendation:** Add a note to the architecture document clarifying which config files exist now versus which are planned for future phases. This prevents confusion when developers look for referenced files.

---

## DOC-17: Interface contracts reference conversation_checkpoints table that does not exist

**Severity:** Warning
**Location:** `plans/interface-contracts-phase-1.md:195`
**Description:** The interface contracts database schema table lists `conversation_checkpoints` as a table with columns `id, user_id, thread_id, checkpoint_data, created_at`. This table does not exist in the SQLAlchemy models. Conversation persistence is handled by `langgraph-checkpoint-postgres` which manages its own tables (created by `AsyncPostgresSaver.setup()`), not by a Summit Cap-defined model.
**Recommendation:** Update the interface contracts to reflect the actual checkpoint storage mechanism (LangGraph's AsyncPostgresSaver with auto-created tables).

---

## DOC-18: Root README "Extending the Template" section is irrelevant

**Severity:** Warning
**Location:** `README.md:472-558`
**Description:** The root README contains a large "Extending the Template" section with instructions for renaming the project, adding generic endpoints, adding generic UI pages, and connecting UI to API. This content is from the quickstart template and is not relevant to the Summit Cap Financial application. A developer working on this project does not need template extension instructions; they need domain-specific development guidance.
**Recommendation:** Remove or heavily reduce the "Extending the Template" section. Replace with domain-relevant developer guidance (how to add a new agent, how to add a new persona route, how to add a new document type, etc.).

---

## DOC-19: Root README footer says "Generated with AI QuickStart CLI"

**Severity:** Info
**Location:** `README.md:609`, `packages/api/README.md:284`, `packages/ui/README.md:663`, `packages/db/README.md:448`
**Description:** All four READMEs end with "Generated with AI QuickStart CLI" with a link to the template repo. While technically true (the project started from the template), this line at the bottom of an active project's README is misleading -- it suggests the content is auto-generated and current, when in fact the README has not been updated to match the project's actual state.
**Recommendation:** Remove the "Generated with" footer from all READMEs, or replace with a note like "Based on the AI QuickStart template."

---

## DOC-20: No developer onboarding for LLM setup

**Severity:** Warning
**Location:** Missing (no doc covers LLM setup for local development)
**Description:** A new developer needs to configure an LLM endpoint to run the chat features. The environment variables `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_FAST`, and `LLM_MODEL_CAPABLE` are required, and the developer needs either a local model server (LM Studio, Ollama, vLLM) or an API key for an external service. None of this is documented in any README or getting-started guide. The compose.yml defaults to `http://host.docker.internal:1234/v1` which suggests LM Studio, but this is not explained.
**Recommendation:** Add an LLM setup section to the root README or create a dedicated developer setup guide covering: (a) local model server options (LM Studio, Ollama), (b) external API options (OpenAI, etc.), (c) which env vars to set, (d) which models are recommended.

---

## DOC-21: Makefile `help` output is accurate but README commands table is not

**Severity:** Warning
**Location:** `README.md:86-123`
**Description:** The root README "Available Commands" section lists Makefile targets that do not exist (`make containers-logs` exists but `make db-logs` is listed as `make db-logs` in one place and correctly elsewhere). More significantly, the README does not document several important Makefile targets that do exist: `make run` (full stack), `make run-minimal`, `make run-auth`, `make run-ai`, `make run-obs`, `make smoke`, `make build-images`, `make push-images`, `make lint-hmda`. The README also lists `make containers-up` which is actually just an alias for `run-minimal`, not the "production-like" deployment the README suggests.
**Recommendation:** Synchronize the README commands section with the actual Makefile `help` output.

---

## DOC-22: Requirements doc references wrong HMDA isolation path

**Severity:** Info
**Location:** `plans/requirements.md:265`
**Description:** The requirements document references `packages/api/src/summit_cap/services/compliance/` as the compliance service path for the HMDA isolation CI lint check. The actual path is `packages/api/src/services/compliance/`.
**Recommendation:** Update the path reference.
