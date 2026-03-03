# Documentation Review -- Pre-Phase 5

**Reviewer:** technical-writer
**Date:** 2026-02-27
**Scope:** All documentation -- READMEs, planning docs, API docs, code docstrings, YAML configs

---

## Findings

### [TW-01] Severity: Critical
**File(s):** `/home/jary/redhat/git/mortgage-ai/README.md`
**Finding:** Root README is still the AI QuickStart CLI template. It describes a generic template project ("A ready-made template for creating new AI Quickstarts") and includes template-specific content: an "Extending the Template" section with a `sed` renaming command, a "Generated with AI QuickStart CLI" footer, generic "Learn More" links (Turborepo, TanStack Router, FastAPI, Alembic), and no mention of mortgage lending, Summit Cap Financial, agents, compliance, or any domain-specific feature. After 4 completed phases (739+ tests, 4 agents, compliance KB, underwriting decisions), the root README tells a reader nothing about what this application actually does.
**Recommendation:** Rewrite the root README to describe Summit Cap Financial as a multi-agent loan origination system. Include: one-line description, architecture overview (5 personas, 4 agents, compliance KB), quick start with compose, prerequisites, the current feature set, and a link to `plans/product-plan.md` for full context. Remove the template boilerplate entirely.

### [TW-02] Severity: Critical
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/README.md`
**Finding:** The API README is missing all Phase 3 and Phase 4 endpoints and features. Specifically absent:
- Loan officer chat WebSocket: `ws://host/api/loan-officer/chat`
- Underwriter chat WebSocket: `ws://host/api/underwriter/chat`
- LO conversation history: `GET /api/loan-officer/conversations/history`
- UW conversation history: `GET /api/underwriter/conversations/history`
- Audit by application: `GET /api/admin/audit/application/{id}`
- Pipeline query parameters on `GET /api/applications/` (`sort_by`, `filter_stage`, `filter_stalled`)
- The 4 agents and their tool sets (public: 2 tools, borrower: 15 tools, LO: 12 tools, UW: 19 tools)
- Compliance KB (vector search, conflict detection)
- Compliance checks (ECOA, ATR/QM, TRID)
- Underwriting decisions (propose/confirm flow)
- Condition lifecycle (issue, review, clear, waive, return)
- Document extraction pipeline
**Recommendation:** Add sections covering: (1) all WebSocket endpoints including LO and UW chat, (2) the pipeline query parameters, (3) the audit-by-application endpoint, (4) an "Agents" section listing all 4 agents and their tool sets, (5) a "Compliance" section describing the KB and checks, (6) a "Features by Phase" summary.

### [TW-03] Severity: Critical
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/README.md` (line 65)
**Finding:** The HMDA endpoint path is documented as `POST /api/hmda/demographics` but the actual route (in `packages/api/src/routes/hmda.py` line 17) is `POST /api/hmda/collect`. A developer relying on the README will get 404 errors.
**Recommendation:** Change the HMDA line to: `POST /api/hmda/collect` with description "Collect HMDA borrower demographics (isolated schema)".

### [TW-04] Severity: Critical
**File(s):** `/home/jary/redhat/git/mortgage-ai/README.md` (line 132), `/home/jary/redhat/git/mortgage-ai/packages/db/README.md` (lines 402, 415, 424), `/home/jary/redhat/git/mortgage-ai/README.md` (line 398)
**Finding:** All database connection strings in READMEs use port 5432, but `compose.yml` maps host port 5433 to container port 5432. Both `packages/api/src/core/config.py` and `packages/db/src/db/config.py` correctly default to port 5433. A developer following the README connection strings will fail to connect from the host.
- Root README line 132: `postgresql://localhost:5432`
- Root README line 398: `DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/summit-cap`
- DB README line 402: `DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/summit-cap`
- DB README line 415: `host:port: Database server (default: localhost:5432)`
- DB README line 424: `Port: 5432`
**Recommendation:** Change all localhost port references from 5432 to 5433. The 5432 references in Helm/compose sections that use container-internal networking (`summit-cap-db:5432`) are correct and should be left as-is.

### [TW-05] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/plans/architecture.md` (lines 15, 101, 167, 208, 246, 283, 349, 350, 389, 480, 519, 625, 674, 702, 714, 742)
**Finding:** The architecture document uses "PoC" 16 times as the maturity label. The project's authoritative maturity level is "MVP" as stated in `CLAUDE.md` and `maturity-expectations.md`. This creates confusion about what quality bar applies -- PoC implies "smoke tests, console errors acceptable" while MVP implies "happy path + critical edges" tested.
**Recommendation:** Replace all 16 occurrences of "PoC" with "MVP" in `plans/architecture.md`. The document was written before the maturity label was finalized and was flagged in the pre-Phase 3 review but never corrected.

### [TW-06] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/plans/architecture.md` (line 250, 828, 848), `/home/jary/redhat/git/mortgage-ai/plans/interface-contracts-phase-1.md` (line 28), `/home/jary/redhat/git/mortgage-ai/plans/requirements.md` (line 265)
**Finding:** Three planning docs reference incorrect package paths:
- Architecture line 250: `packages/db/src/summit_cap_db/database.py` -- actual path is `packages/db/src/db/database.py`
- Architecture lines 828/848: `src/summit_cap/` and `src/summit_cap_db/` -- actual paths are `packages/api/src/` and `packages/db/src/db/`
- Interface contracts Phase 1 line 28: `packages/api/src/summit_cap/schemas/` -- actual path is `packages/api/src/schemas/`
- Requirements line 265: references `packages/api/src/summit_cap/services/compliance/` -- actual path is `packages/api/src/services/compliance/`
These were flagged in the pre-Phase 3 review but remain uncorrected.
**Recommendation:** Update all `summit_cap` and `summit_cap_db` path references to match actual codebase paths. This affects all three documents.

### [TW-07] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/plans/technical-debt.md`
**Finding:** Several technical debt items are stale -- they describe issues that have been resolved but remain in the "open" sections:
1. **D10** (line 35): "audit_events.event_data is Text, contract says JSONB" -- models.py line 336 shows `event_data = Column(JSON, nullable=True)`. This is resolved.
2. **D18** (line 29): "DB package reads os.environ directly" -- `packages/db/src/db/config.py` now uses pydantic-settings (`DatabaseSettings`). This is resolved.
3. **"Pydantic v2 deprecated config style"** (line 121): `packages/api/src/core/config.py` now uses `SettingsConfigDict`. This is resolved.
4. **"SQLAlchemy deprecated API usage"** (line 117): `packages/db/src/db/database.py` now uses `DeclarativeBase`. This is resolved.
**Recommendation:** Move D10, D18, and the two "Existing Items" entries to the "Resolved" table at the bottom of the file with their resolution descriptions.

### [TW-08] Severity: Warning
**File(s):** (missing file)
**Finding:** No `.env.example` file exists in the repository. The project uses 27+ environment variables across `packages/api/src/core/config.py` (28 settings), `packages/db/src/db/config.py` (3 settings), and `compose.yml` (LangFuse, MinIO, Keycloak). The root README's Environment Configuration section (line 394) shows only 6 variables (`DATABASE_URL`, `DB_ECHO`, `DEBUG`, `ALLOWED_HOSTS`, `VITE_API_BASE_URL`, `VITE_ENVIRONMENT`), omitting all LLM, safety, storage, auth, compliance, and observability configuration. A developer setting up from scratch has no reference for what environment to configure.
**Recommendation:** Create `.env.example` at the project root with all environment variables grouped by subsystem (App, Database, Auth, LLM, Safety, Storage, Observability). Include descriptive comments for each variable and safe default values. Update the root README's Environment Configuration section to reference this file.

### [TW-09] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/ui/README.md`, `/home/jary/redhat/git/mortgage-ai/packages/db/README.md`
**Finding:** Both READMEs are essentially unchanged from the template. The UI README describes a generic component library with example "UserList" and "About page" components that do not exist. The DB README describes a generic "User" model pattern and uses `DatabaseService.get_session()` examples that don't match the actual codebase (the API uses `get_db` dependency injection from `packages/db/__init__.py`, not `DatabaseService.get_session()`). Neither README mentions mortgage-specific models, the 15 database tables, the HMDA isolated schema, or pgvector. The DB README still says `Port: 5432` and `echo=True` for the engine, both incorrect.
**Recommendation:** Rewrite both READMEs to reflect the actual implementation. The DB README should list the actual models (Borrower, Application, Condition, Decision, Document, etc.), the HMDA schema isolation, pgvector for KB embeddings, and the compliance database role. The UI README can remain lighter since the frontend is flagged as replaceable, but should at minimum remove the template examples.

### [TW-10] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/README.md`
**Finding:** The directory structure listing (lines 8-33) is incomplete. It omits several directories and files that now exist:
- `services/compliance/` (HMDA, checks, knowledge_base)
- `services/seed/` (demo data seeder, fixtures)
- `services/condition.py`, `services/decision.py`, `services/urgency.py`
- `agents/base.py` (base graph class)
- `agents/loan_officer_assistant.py`, `agents/underwriter_assistant.py`
- `agents/loan_officer_tools.py`, `agents/underwriter_tools.py`, `agents/compliance_tools.py`, `agents/compliance_check_tool.py`, `agents/condition_tools.py`, `agents/decision_tools.py`
- `routes/loan_officer_chat.py`, `routes/underwriter_chat.py`
- `inference/` directory (LLM client, model routing, safety shields)
- `observability.py` (LangFuse integration)
**Recommendation:** Update the directory structure tree to reflect the current layout, or switch to a higher-level description that won't need updating with every new file.

### [TW-11] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/plans/interface-contracts-phase-1.md` (line 18)
**Finding:** The Phase 1 interface contracts list the HMDA endpoint as `POST /api/hmda/collect` with `borrower` role only. The actual implementation (routes/hmda.py line 20) allows both `borrower` and `admin` roles. The response type in the contract says `HmdaCollectionResponse` which is correct, but the route path documented in the API README (`/api/hmda/demographics`) differs from both the contract and implementation.
**Recommendation:** Update the Phase 1 interface contract to reflect `[borrower, admin]` roles. Ensure the API README path matches the implementation (`/api/hmda/collect`).

### [TW-12] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/plans/technical-debt.md` (line 57)
**Finding:** Technical debt item D11 says "SSN stored as plaintext with `ENC:` prefix" and references `models.py:46` with field name `ssn_encrypted`. The actual model (models.py line 51) uses `ssn = Column(String(255), nullable=True)` -- the field was already renamed from `ssn_encrypted` to `ssn` during the pre-Phase 3 cleanup (PR #48). The debt item description is stale.
**Recommendation:** Update D11 to reflect the current state: field is named `ssn` (not `ssn_encrypted`), stored as plaintext. The core issue (no actual encryption) remains valid for pre-production tracking, but the description should match current code.

### [TW-13] Severity: Warning
**File(s):** (no file exists)
**Finding:** No interface contracts exist for Phases 3 or 4. Interface contracts exist for Phase 1 (`plans/interface-contracts-phase-1.md`) and Phase 2 (`plans/interface-contracts-phase-2.md`), but Phases 3-4 introduced substantial new API surface:
- Phase 3: Pipeline query parameters, LO chat WebSocket, LO conversation history, audit-by-application endpoint, 12 LO agent tools
- Phase 4: UW chat WebSocket, UW conversation history, compliance check service, KB vector search, risk assessment, 19 UW agent tools, condition lifecycle (6 operations), decision rendering (2-phase flow), Loan Estimate/Closing Disclosure generation
Without Phase 3-4 contracts, there is no single document a frontend developer can reference to understand the complete API surface added in those phases.
**Recommendation:** Create `plans/interface-contracts-phase-3.md` and `plans/interface-contracts-phase-4.md` documenting the endpoints, WebSocket protocol additions, request/response shapes, and agent tool interfaces added in each phase.

### [TW-14] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/README.md` (lines 78-109)
**Finding:** The WebSocket protocol section documents only two endpoints (public chat, borrower chat) and three message types (`token`, `done`, `error`, `safety_override`). Two additional WebSocket endpoints exist:
- `ws://host/api/loan-officer/chat?token=<jwt>` (requires loan_officer role)
- `ws://host/api/underwriter/chat?token=<jwt>` (requires underwriter role)
The message protocol is identical for all four, but the agent behaviors, tool calls, and conversation persistence patterns differ. Additionally, tool calls within agent streams may produce intermediate `token` messages with structured tool output that the client needs to handle.
**Recommendation:** Add LO and UW WebSocket endpoints to the protocol section. Consider documenting the agent-specific behaviors (e.g., "LO chat supports 12 tools for pipeline management", "UW chat supports 19 tools including 2-phase decisions").

### [TW-15] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/README.md`
**Finding:** The README lacks an "Agent Architecture" section. The project has 4 distinct agents with YAML-driven configuration, a registry with hot-reload, rule-based model routing with confidence escalation, RBAC-scoped tool access, and safety shields. This is the project's core differentiator (multi-agent AI for regulated lending) but is undocumented in any user-facing README. The only documentation is in the YAML config files themselves and the agent Python modules' docstrings.
**Recommendation:** Add an "Agent Architecture" section to the API README (or a standalone `docs/agents.md` linked from the README) covering: the 4 agents and their personas, the YAML configuration format, the tool registration mechanism, rule-based routing (SIMPLE vs COMPLEX), safety shields, and RBAC enforcement on tool access.

### [TW-16] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/data/compliance-kb/`
**Finding:** The compliance KB contains 8 synthetic regulatory documents across 3 tiers (federal: HMDA, TRID, ATR/QM, FCRA, ECOA; agency: FHA, Fannie Mae; internal: Summit Cap policies). This content is domain-specific, curated for the demo, and undocumented outside of the source files themselves. There is no README or index explaining: what the tiers mean, what each document covers, the YAML frontmatter format required for ingestion, the embedding dimensions used (768), or the ingestion command to rebuild the index.
**Recommendation:** Add a `data/compliance-kb/README.md` explaining the KB structure, tier hierarchy (federal > agency > internal), document format requirements, and ingestion process. This helps both demo presenters and quickstart adopters understand the compliance RAG pattern.

### [TW-17] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/README.md` (line 3)
**Finding:** The root README one-liner says "A ready-made template for creating new AI Quickstarts" which is the template description, not the project description. The project's actual identity is defined in CLAUDE.md: "A Red Hat AI Quickstart demonstrating agentic AI applied to the mortgage lending lifecycle."
**Recommendation:** Replace the one-liner with the CLAUDE.md description or a condensed variant: "Multi-agent AI loan origination system for mortgage lending -- a Red Hat AI Quickstart."

### [TW-18] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/README.md` (lines 470, 609)
**Finding:** Two template-era references remain in the root README:
- Line 470: "For more details, see the Helm chart documentation (if available)" -- the Helm chart exists, this parenthetical is unnecessary template hedging.
- Line 609: "Generated with AI QuickStart CLI" -- attribution to the template generator is no longer relevant after 4 phases of development.
**Recommendation:** Remove the "(if available)" parenthetical and the template attribution footer.

### [TW-19] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/README.md` (line 155-158)
**Finding:** The Configuration section groups all env vars into 7 bullet points without showing default values or required/optional status. With 28+ settings in `config.py`, a developer needs to look at the source code to understand what's required vs optional and what the defaults are. The LLM configuration alone has 4 variables (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_FAST`, `LLM_MODEL_CAPABLE`) that are not individually documented.
**Recommendation:** Expand the Configuration section into a table listing each env var, its default, whether it's required, and a one-line description. Alternatively, reference a `.env.example` file (see TW-08).

### [TW-20] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/plans/technical-debt.md` (lines 7-30)
**Finding:** The "Pre-Phase 3" section heading is misleading now that Phase 3 is complete. Items D2, D7, D8, D16, D17 were supposed to be addressed before Phase 3 but were not. They remain open but the phase gate they were tagged for has passed. Similarly, the "Pre-Phase 4" section (D10) has passed, and D10 is actually resolved (see TW-07).
**Recommendation:** Reorganize the technical debt document by severity or category rather than phase gates. Items that missed their phase gate should be re-evaluated: either they are still important (move to a general "Open" section) or they were implicitly accepted as technical debt (note the acceptance). Remove the resolved items per TW-07.
