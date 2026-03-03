# Pre-Phase 3 Project Manager Review

**Reviewer:** Project Manager
**Date:** 2026-02-26
**Scope:** Phase 1 (32 stories) and Phase 2 (34 stories) completeness verification, scope drift, technical debt accuracy, Phase 3 readiness

---

## PM-01: No application state machine enforcement in code

**Severity:** Critical
**Description:** Requirements S-3-F8-04 specifies that only valid state transitions are allowed per the application state machine (e.g., "application" -> "underwriting" or "withdrawn"; "underwriting" -> "conditional_approval", "denied", or "application"). The current `update_application()` in `packages/api/src/services/application.py` accepts any value for the `stage` field without validation. The `_UPDATABLE_FIELDS` set includes "stage" as a freely updatable field. There is no mapping of valid transitions or enforcement anywhere in the codebase. A search for "transition", "state_machine", or "valid_stage" across the entire `packages/api/src/` directory returns zero results outside of the status service (which only reads stage info, does not enforce transitions).
**Reference:** S-3-F8-04 (state transition validation), S-1-F14-01 (RBAC enforcement at API level -- invalid transitions should be rejected before handler logic)
**Recommendation:** Implement a `VALID_TRANSITIONS` mapping (e.g., `{"application": ["underwriting", "withdrawn"], ...}`) and validate in `update_application()` before applying the stage change. This is a Phase 3 prerequisite -- the LO submission flow (S-3-F8-03, S-3-F8-04) depends on state transition enforcement. Without it, any role can set any stage on any application.

---

## PM-02: No Loan Officer agent or agent config exists

**Severity:** Critical
**Description:** Phase 3 requires an LO Assistant agent (F7 pipeline, F8 review/submission, F24 communication drafting). The agent registry (`packages/api/src/agents/registry.py`) only knows about two agents: `public-assistant` and `borrower-assistant`. There is no `lo-assistant` or `loan-officer-assistant` entry. The `config/agents/` directory contains only `public-assistant.yaml` and `borrower-assistant.yaml`. There is no LO agent module in `packages/api/src/agents/`, no LO-specific tools file, and no LO WebSocket chat route. The borrower tools exist (`borrower_tools.py`) but there are no LO-specific tools like `submit_to_underwriting`, `pipeline_view`, `draft_communication`, or `completeness_check` as required by F7/F8/F24.
**Reference:** S-3-F8-01 through S-3-F8-04 (LO agent tools), S-3-F24-01 through S-3-F24-03 (communication drafting), S-3-F7-01 (pipeline view)
**Recommendation:** Phase 3 implementation must include: (1) LO assistant agent module, (2) LO agent config YAML, (3) LO-specific tools file, (4) LO WebSocket chat route, (5) registry entry for the new agent. This is new work, not a gap in Phase 1/2.

---

## PM-03: No LO WebSocket chat endpoint

**Severity:** Critical
**Description:** The chat endpoints exist for public (`/ws/chat` in `routes/chat.py`) and borrower (`/ws/borrower/chat` in `routes/borrower_chat.py`), but there is no `/ws/loan-officer/chat` or equivalent endpoint. Phase 3 requires an authenticated WebSocket endpoint for the LO persona to interact with their assistant agent (F8 stories).
**Reference:** S-3-F8-01 (LO reviews application in chat interface), architecture Section 2.3 (each persona has its own agent)
**Recommendation:** Create `routes/loan_officer_chat.py` with a WebSocket endpoint requiring `UserRole.LOAN_OFFICER` authentication. Pattern is identical to `borrower_chat.py`.

---

## PM-04: Technical debt item D14 (Application service untested) not resolved

**Severity:** Warning
**Description:** `plans/technical-debt.md` item D14 states "Application service untested -- `services/application.py` has no direct test coverage." This was classified as "Pre-Production" but the application service is the core of all CRUD operations and Phase 3 LO pipeline queries. Integration tests exist for data scope filtering but the service layer methods (`list_applications`, `get_application`, `create_application`, `update_application`) lack unit tests. Phase 3 will add significant complexity to application queries (urgency calculation, pipeline filtering, submission readiness checks). Starting Phase 3 on an untested foundation increases regression risk.
**Reference:** D14 in `plans/technical-debt.md`, S-3-F7-01 (pipeline queries), S-3-F8-03 (submission readiness)
**Recommendation:** Add unit tests for the application service before Phase 3 implementation. At minimum, test `list_applications` with different data scopes, `update_application` with valid/invalid fields, and `create_application` borrower resolution.

---

## PM-05: Pre-Phase 3 technical debt items still open

**Severity:** Warning
**Description:** `plans/technical-debt.md` categorizes 6 items as "Pre-Phase 3 (address before loan officer features)": D2 (WebSocket rate limits), D7 (unbounded conversation history), D8 (`verify_aud` disabled), D16 (agent registry filesystem stat on every message), D17 (fragile path resolution), D18 (DB package config divergence). None of these have been resolved. D2 and D7 are directly relevant to Phase 3 since the LO will use WebSocket chat -- without rate limits or message caps, the LO chat could exhaust memory or be abused.
**Reference:** `plans/technical-debt.md` "Pre-Phase 3" section
**Recommendation:** At minimum, address D2 (WebSocket rate/size limits) and D7 (unbounded message accumulation) before Phase 3. The others (D8, D16, D17, D18) are less urgent but should not accumulate indefinitely.

---

## PM-06: HMDA CI lint check not integrated into CI or pre-commit

**Severity:** Warning
**Description:** Story S-1-F25-05 requires a CI lint check that prevents HMDA schema access outside the Compliance Service, with an acceptance criterion that it runs in CI and optionally as a pre-commit hook. The script exists (`scripts/lint-hmda-isolation.sh`) and a Makefile target exists (`make lint-hmda`), but the check is not integrated into any CI pipeline (no GitHub Actions workflow references it) and is not configured as a pre-commit hook. The story's acceptance criteria explicitly require CI integration ("Given the CI pipeline runs / When the lint check step executes...").
**Reference:** S-1-F25-05 (CI lint check prevents HMDA schema access outside Compliance Service)
**Recommendation:** Add `lint-hmda` to the CI workflow and/or the `lint` Makefile target so it runs automatically.

---

## PM-07: S-1-F20-02 seed data distribution deviates from requirements

**Severity:** Warning
**Description:** S-1-F20-02 specifies "5-10 applications distributed across stages: application (2-3), underwriting (2-3), conditional_approval (1-2), final_approval (1-2)." The actual fixture data (`packages/api/src/services/seed/fixtures.py`) seeds 8 active applications: 3 in APPLICATION, 2 in UNDERWRITING, 2 in CONDITIONAL_APPROVAL, 1 in CLEAR_TO_CLOSE. This is 8 total (within the 5-10 range) but the requirements mention `final_approval` stage which does not exist in the `ApplicationStage` enum. The enum uses `clear_to_close` instead. The fixture data does not include any applications in the `PROCESSING` stage, which means the LO pipeline will not demonstrate the "processing" stage during demos. This is a minor semantic gap but worth noting for demo fidelity.
**Reference:** S-1-F20-02 (demo data includes 5-10 active applications across all stages)
**Recommendation:** No action needed for the stage name discrepancy (the enum is authoritative). Consider adding 1-2 applications in the PROCESSING stage for demo completeness.

---

## PM-08: No urgency calculation service for LO pipeline

**Severity:** Warning
**Description:** Phase 3 story S-3-F7-01 requires urgency indicators (Critical/High/Medium/Normal) based on rate lock expiration, stage timing, outstanding conditions, and document request age. S-3-F7-03 defines specific thresholds (rate lock < 3 days = Critical, < 7 days = High, etc.). There is currently no urgency calculation service, no stage timing thresholds configuration, and no pipeline-specific query that joins applications with rate locks and conditions to compute urgency. The `services/status.py` provides per-application status but does not compute urgency levels or support pipeline-level queries with sorting by urgency. This is expected Phase 3 work, but the data foundations need to be solid.
**Reference:** S-3-F7-01 (urgency indicators), S-3-F7-03 (urgency calculation logic)
**Recommendation:** Verify that the Phase 3 TD includes an urgency calculation service that queries rate locks (F27 data), stage timing, and conditions (F28 data) to produce urgency levels. The data is available in the DB; the service logic is the gap.

---

## PM-09: No pipeline filtering/sorting endpoint for LO

**Severity:** Warning
**Description:** S-3-F7-01 requires pipeline filtering (by stage, closing date, stalled applications) and sorting (by urgency, closing date, loan amount, last activity). The current `GET /api/applications/` endpoint supports only `offset` and `limit` query parameters. It does not support `stage`, `closing_date`, `stalled`, or `sort` parameters. Phase 3 will need to extend the applications endpoint or create a dedicated pipeline endpoint.
**Reference:** S-3-F7-01 (pipeline filtering), S-3-F7-04 (pipeline sorting)
**Recommendation:** Phase 3 implementation should extend the applications list endpoint with filter/sort parameters rather than creating a separate pipeline endpoint, to maintain API consistency.

---

## PM-10: Conversation history endpoint only serves borrower persona

**Severity:** Warning
**Description:** The conversation history endpoint (`GET /borrower/conversations/history` in `routes/borrower_chat.py`) is hard-coded to the borrower-assistant agent name and restricted to `UserRole.BORROWER` and `UserRole.ADMIN`. Phase 3 needs conversation history for the LO persona (S-3-F7-04 mentions "chat interface displays the conversation history"). This endpoint pattern will need to be replicated for the LO persona or generalized.
**Reference:** S-3-F7-04 (application detail loads conversation history), S-2-F19-01 through F19-04 (conversation persistence)
**Recommendation:** Either create a parallel LO conversation history endpoint or refactor the existing endpoint to accept an `agent_name` parameter and role-based access.

---

## PM-11: Interface contract drift items D13a-d untracked in detail

**Severity:** Info
**Description:** The technical debt tracker lists "Interface contract drift (D13a-d)" as a bucket item covering 4 sub-issues: (a) Compose version mismatches (Keycloak 24->26, LangFuse v2->v3, MinIO added), (b) ID types (contract says UUID, implementation uses int; user_id is str not UUID), (c) models.yaml provider ("llamastack" vs "openai_compatible"), (d) HealthResponse (implementation returns list, contract says single object). These drifts are documented but not individually tracked. ID type mismatch (D13b) could cause issues if a future phase introduces UUID-based routing or if the OpenAPI spec is auto-generated from the current int-based models.
**Reference:** `plans/technical-debt.md` "Interface contract drift (D13a-d)", `plans/interface-contracts-phase-1.md`
**Recommendation:** Break D13a-d into individual tracked items so they can be addressed independently. D13b (int vs UUID) is the highest risk as it affects API shape.

---

## PM-12: No frontend persona routing for any authenticated role

**Severity:** Info
**Description:** S-1-F2-02 requires role-based access to persona UIs (borrower sees `/borrower/dashboard`, LO sees `/loan-officer/pipeline`, etc.) with 403 pages for unauthorized routes. The frontend (`packages/ui/src/`) has no role-based routing, no protected routes, no persona-specific pages, and no 403 error page. The UI contains only generic components (hero, status-panel, service-card, stat-card) and a single index route. There is no Keycloak integration in the frontend at all. While the requirements note "Frontend is replaceable" and all auth is server-side, the current frontend cannot demo any authenticated persona experience.
**Reference:** S-1-F2-02 (role-based access to persona UIs), project constraints ("Frontend is replaceable -- the AI BU may provide their own frontend")
**Recommendation:** This is expected given the "frontend is replaceable" constraint and the focus on API-first development. However, for the Summit demo target, the frontend will need at minimum: (1) Keycloak OIDC integration, (2) role-based route protection, (3) persona-specific pages (at least borrower chat and LO pipeline). Track this as a cross-cutting item for the demo preparation phase.

---

## PM-13: S-1-F25-02 PostgreSQL role separation not implemented

**Severity:** Info
**Description:** S-1-F25-02 requires two PostgreSQL roles (`lending_app` and `compliance_app`) with database-level access control. The implementation uses a single database connection for the lending path and a separate engine for the compliance path, but both use the same PostgreSQL user (the connection URL in settings). True PostgreSQL role separation (where `lending_app` role gets "permission denied" on `SELECT * FROM hmda.demographics`) is not implemented. The HMDA isolation is enforced at the application layer (separate connection pools, lint check, code organization) rather than at the database level.
**Reference:** S-1-F25-02 (PostgreSQL role separation)
**Recommendation:** This is acceptable for MVP maturity. Application-layer enforcement is in place. Database-level role separation should be tracked for pre-production hardening.

---

## PM-14: Demo data seeder creates only 1 LO (affects Phase 3 testing)

**Severity:** Info
**Description:** The seed fixtures assign all applications to a single loan officer (`JAMES_TORRES_ID`). S-1-F14-02 and S-3-F7-02 require demonstration of data scope isolation (LO sees only their own applications). With only one LO having applications, data scope isolation cannot be demonstrated in the seeded environment. Phase 3 testing will need at least 2 LOs with different application assignments.
**Reference:** S-1-F14-02 (data scope injection for LO pipeline), S-3-F7-02 (pipeline filtered to LO's own applications)
**Recommendation:** Add a second LO user to the seed fixtures with 2-3 applications assigned to them, so data scope isolation can be demonstrated and tested.

---

## PM-15: S-1-F20-05 (empty state handling) not verifiable in backend

**Severity:** Info
**Description:** S-1-F20-05 requires informative empty states in all UIs (LO pipeline, CEO dashboard, underwriter queue, borrower assistant, document list, audit trail). The backend returns empty arrays/zero counts correctly, but the specific empty state messages ("No applications yet. Applications will appear here once borrowers begin the intake process") are frontend concerns. With the current minimal frontend, none of these empty states are implemented. This is a frontend task, not a backend gap.
**Reference:** S-1-F20-05 (empty state handling in all UIs)
**Recommendation:** Track as a frontend task for the demo preparation phase.

---

## PM-16: S-1-F18-01 through S-1-F18-03 (LangFuse integration) only partially verifiable

**Severity:** Info
**Description:** LangFuse integration exists (`packages/api/src/observability.py`) with callback handler setup and session ID correlation. However, the integration is entirely dependent on environment variables (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`) being set, and degrades to no-op when not configured. There are no tests verifying the LangFuse callback is actually attached to agent invocations, that traces contain tool calls and LLM calls, or that session_id correlation works end-to-end. S-1-F18-02 (dashboard displays traces) and S-1-F18-03 (trace-to-audit correlation) are infrastructure stories that depend on a running LangFuse instance and cannot be verified in unit tests.
**Reference:** S-1-F18-01 (LangFuse callback integration), S-1-F18-02 (dashboard), S-1-F18-03 (trace-audit correlation)
**Recommendation:** These stories are "infrastructure verified" -- they work when the stack is running but lack automated regression tests. Acceptable for MVP maturity. Consider a manual verification checklist before the Summit demo.

---

## Summary

| Severity | Count | Details |
|----------|-------|---------|
| Critical | 3 | PM-01 (no state machine), PM-02 (no LO agent), PM-03 (no LO WebSocket) |
| Warning | 7 | PM-04 (untested app service), PM-05 (open pre-Phase-3 debt), PM-06 (HMDA lint not in CI), PM-07 (seed data gap), PM-08 (no urgency service), PM-09 (no pipeline endpoint), PM-10 (conversation history borrower-only) |
| Info | 6 | PM-11 (contract drift), PM-12 (no frontend routing), PM-13 (PG role separation), PM-14 (single LO in seed), PM-15 (empty states), PM-16 (LangFuse partial) |

### Phase 3 Readiness Assessment

Phase 3 is **not ready to start implementation** without addressing the 3 Critical items:

1. **State machine enforcement** (PM-01) -- Required by F8 submission flow. Without it, the LO can set any stage, bypassing business rules.
2. **LO agent and tools** (PM-02) -- This is the core Phase 3 deliverable. The agent framework pattern exists (borrower agent is the template), but no LO-specific code exists yet.
3. **LO WebSocket endpoint** (PM-03) -- Required for the chat-based LO workflow.

The Warning items (PM-04 through PM-10) represent quality and completeness gaps that increase risk if not addressed early in Phase 3 but do not strictly block starting.

### Phases 1-2 Completeness

Phase 1 and Phase 2 stories are substantially complete at the backend API level. The following stories have partial implementation or known gaps:

- **S-1-F2-02** (role-based persona UIs) -- Backend RBAC works; frontend has no role routing (PM-12)
- **S-1-F25-02** (PostgreSQL role separation) -- Application-layer only, no DB-level enforcement (PM-13)
- **S-1-F25-05** (CI HMDA lint) -- Script exists but not in CI (PM-06)
- **S-1-F20-05** (empty states) -- Backend returns empty data correctly; frontend not implemented (PM-15)
- **S-1-F18-01 to S-1-F18-03** (LangFuse) -- Integration exists but not automatically testable (PM-16)
