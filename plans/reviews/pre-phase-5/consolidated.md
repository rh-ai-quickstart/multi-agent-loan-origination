# Consolidated Review: Pre-Phase 5

**Reviews consolidated:** code-reviewer, security-engineer, architect, tech-lead, backend-developer, database-engineer, api-designer, test-engineer, performance-engineer, devops-engineer, debug-specialist, technical-writer, frontend-developer, product-manager, project-manager, orchestrator
**Date:** 2026-02-27

## Summary

- Total findings across all reviews: ~310
- De-duplicated findings: 89
- Reviewer disagreements: 2
- Breakdown: 13 Critical, 42 Warning, 34 Suggestion

---

## Critical (must fix before proceeding)

| # | Finding | Flagged By | Location | Suggested Resolution | Disposition |
|---|---------|-----------|----------|---------------------|-------------|
| C-1 | AUTH_DISABLED defaults to `true` in compose.yml -- all auth bypassed in default dev stack, disabled user is full admin | SE-01 | `compose.yml:91`, `auth.py:157` | Change default to `false`; require explicit opt-in; add startup warning | _pending_ |
| C-2 | SQLAdmin default credentials `admin/admin` with plain string comparison | SE-02 | `config.py:59-66`, `admin.py:49` | Remove defaults (fail startup if missing); use `secrets.compare_digest()` | _pending_ |
| C-3 | Tool RBAC `tool_allowed_roles` overridable via graph state merge -- privilege escalation risk | SE-03 | `base.py:230` | Remove `**state.get("tool_allowed_roles", {})` -- make roles immutable at graph construction | _pending_ |
| C-4 | No WebSocket message size or rate limits on any of 5 WS endpoints -- memory exhaustion, LLM cost attack, DoS | SE-04, BE-18, BE-19, BE-20 | `_chat_handler.py:136` | Set `--ws-max-size` on Uvicorn; add per-connection rate limit (10 msg/min); validate message length | _pending_ |
| C-5 | SSN stored as plaintext in database (renamed from `ssn_encrypted` but never encrypted) | SE-08 | `models.py:51`, `applications.py:55` | Implement Fernet encryption with env-var key; decrypt only for authorized roles | _pending_ |
| C-6 | No rate limiting on any REST or WebSocket endpoint (auth, uploads, decisions, chat) | SE-14, SE-21 | `main.py` (global) | Add `slowapi` middleware; priority: admin login (5/min), WS chat (10/min), uploads (10/min) | _pending_ |
| C-7 | SQLAdmin session secret regenerated on every restart -- breaks multi-worker/replica sessions | SE-09 | `admin.py:215` | Source from `SQLADMIN_SECRET_KEY` env var | _pending_ |
| C-8 | Compliance gate checks wrong key (`status` vs `overall_status`) -- gate is a no-op, approvals proceed despite failed compliance | DS-15 | `decision_tools.py:50-81` | Change `event_data.get("status")` to `event_data.get("overall_status")`; also check `can_proceed` | _pending_ |
| C-9 | Blocking synchronous PDF operations (`fitz.open`) in async context -- blocks event loop for all concurrent requests | BE-01, PE-04 | `extraction.py:175-205` | Wrap in `run_in_executor()`, consistent with `storage.py` pattern | _pending_ |
| C-10 | Root README is still the AI QuickStart template -- describes a generic template, not Summit Cap Financial | TW-01 | `README.md` | Rewrite to describe the mortgage lending system, architecture, quick start | _pending_ |
| C-11 | API README missing all Phase 3-4 endpoints, wrong HMDA path (`/demographics` vs `/collect`), wrong DB port (5432 vs 5433) | TW-02, TW-03, TW-04 | `packages/api/README.md`, `packages/db/README.md`, root `README.md` | Update all endpoint listings, fix HMDA path, fix all port references to 5433 | _pending_ |
| C-12 | No REST endpoints for decisions -- frontend has no way to list/retrieve underwriting decisions; CEO dashboard blocked | AD-25 | `schemas/decision.py` (exists), no route | Add `GET /api/applications/{id}/decisions` (list) and `GET .../decisions/{did}` (detail), read-only | _pending_ |
| C-13 | Helm chart missing config volume mount -- API will crash on OpenShift (no `config/` directory) | DO-01 | `api-deployment.yaml`, `values.yaml` | Create ConfigMap for `config/` YAML files or add `COPY config/` to Containerfile | _pending_ |

---

## Warning (should fix)

| # | Finding | Flagged By | Location | Suggested Resolution | Disposition |
|---|---------|-----------|----------|---------------------|-------------|
| W-1 | `_user_context_from_state()` copy-pasted identically in 6 tool modules (7 with orchestrator count) -- Phase 5 adds CEO copy #7 | CR-01, AR-02, TL-01, BE-14, OR-01, SE-06 | 6 `*_tools.py` files | Extract to `agents/_shared.py`; raise error if `user_id` missing instead of defaulting to "anonymous" | _pending_ |
| W-2 | Primary borrower name lookup duplicated 3x in `decision_tools.py` (adverse action, LE, CD) | CR-02, TL-04, OR-02, BE-15 | `decision_tools.py:310,430,585` | Extract `get_primary_borrower_name(session, app_id)` helper | _pending_ |
| W-3 | Monthly payment amortization formula duplicated between LE and CD generation (also in `calculator.py`) | CR-03, TL-05, OR-03 | `decision_tools.py:447,602` | Extract `compute_monthly_payment()` to `services/calculator.py` | _pending_ |
| W-4 | Outstanding conditions count (`open + responded + under_review + escalated`) duplicated in 3 locations | CR-05, AR-05, TL-06 | `decision_tools.py:569`, `decision.py:121`, `condition_tools.py:282` | Add `get_outstanding_count()` to condition service | _pending_ |
| W-5 | Chat endpoint boilerplate duplicated across 3 authenticated chat files (~60 lines each, only role/name/path differ) -- Phase 5 adds CEO copy #4 | CR-12, AR-13, TL-09, OR-07 | `borrower_chat.py`, `loan_officer_chat.py`, `underwriter_chat.py` | Create factory `create_chat_routes(role, agent_name, path_prefix)` in `_chat_handler.py` | _pending_ |
| W-6 | Agent tools bypass service layer with raw SQLAlchemy queries (6 instances: financials, borrower lookup, compliance gate) | AR-01, AR-06, TL-03 | `decision_tools.py`, `underwriter_tools.py`, `compliance_check_tool.py` | Extract to service functions: `get_financials()`, `check_compliance_gate()`, LE/CD generation | _pending_ |
| W-7 | `transition_stage()` raises `HTTPException` from service layer -- only service that does this; breaks in agent context | CR-21, AR-04, BE-08, TL-11 | `application.py:187` | Raise domain exception (`InvalidTransitionError`); route handler catches and raises HTTPException | _pending_ |
| W-8 | `_chat_handler._audit` uses `async for db_session in get_db()` generator protocol instead of `SessionLocal()` -- flagged 3rd review in a row | CR-11, BE-06, PE-09 | `_chat_handler.py:119-132` | Replace with `async with SessionLocal() as session:` -- promote to project rule | _pending_ |
| W-9 | Tool modules 700+ lines each (3 files: `underwriter_tools.py` 756, `borrower_tools.py` 728, `decision_tools.py` 701) | CR-07, TL-08 | 3 tool modules | Split by domain: LE/CD -> `disclosure_tools.py`; risk -> `risk_tools.py`; borrower by concern | _pending_ |
| W-10 | Service return type conventions inconsistent: ORM objects vs raw dicts with `"error"` key vs Pydantic models | TL-02, AR-14, TL-10, TL-12, OR-04, BE-12, BE-16 | `condition.py`, `decision.py`, `application.py`, `status.py` | Standardize on `ServiceResult(data, error)` or `BusinessRuleError` exceptions | _pending_ |
| W-11 | Audit hash chain uses global advisory lock -- serializes ALL concurrent audit writes across entire system | OR-09, PE-01, PE-20, DS-03, AR-12 | `audit.py:60` | Batch audit events per turn; long-term: per-application hash chains | _pending_ |
| W-12 | `verify_audit_chain` loads entire audit table into memory -- unbounded, will OOM at scale | BE-05, PE-02, SE-23, DB-02, DS-30 | `audit.py:97-99` | Stream with `yield_per(500)` or chunked iteration; keep only previous hash in memory | _pending_ |
| W-13 | Audit hash chain only hashes `event_id`, `timestamp`, `event_data` -- missing `event_type`, `user_id`, `user_role`, `application_id` | SE-10 | `audit.py:25-28` | Include all audit fields in hash computation | _pending_ |
| W-14 | N+1 query in `check_condition_documents` -- per-document extraction query inside loop | DB-01, PE-03 | `condition.py:238-246` | Batch query with `IN` clause or `selectinload` | _pending_ |
| W-15 | `denial_reasons` stored as JSON-encoded Text column (manual `json.dumps`/`json.loads`) | OR-14, DB-05 | `models.py:232`, `decision.py:283` | Migrate column to `JSONB` type | _pending_ |
| W-16 | `quality_flags` parsing logic repeated 3 different ways across tool files | CR-10, TL-07 | `loan_officer_tools.py:160,209`, `condition.py:32` | Make `_parse_quality_flags` public, share across all consumers | _pending_ |
| W-17 | `closing_date` in CD generation fabricated as today's date instead of using `app.closing_date` | CR-04 | `decision_tools.py:633-634` | Use `app.closing_date` if available, fallback to "TBD" | _pending_ |
| W-18 | LE/CD tools mutate ORM `app.le_delivery_date` before commit -- fragile MissingGreenlet risk if output formatting moves after commit | CR-24, AR-16 | `decision_tools.py:527,683` | Capture all needed fields before commit; add defensive comment | _pending_ |
| W-19 | `add_borrower` and `remove_borrower` contain business logic + raw SQL in route layer; `remove_borrower` is only hard-delete with no audit | AR-09, BE-13 | `applications.py:404-509` | Extract to `services/application.py`; add audit events for both operations | _pending_ |
| W-20 | `build_data_scope` imported from `middleware/auth.py` by agent tools -- cross-layer coupling | AR-03, AR-15 | `agents/*_tools.py` -> `middleware/auth.py` | Move `build_data_scope()` and `mask_ssn()` to `core/` or `schemas/auth.py` | _pending_ |
| W-21 | Bare `except Exception` in chat handler outer loop catches ALL errors as "Client disconnected" at DEBUG level -- swallows programming errors | BE-10, DS-12, DS-02 | `_chat_handler.py:252` | Catch `WebSocketDisconnect` explicitly; log other exceptions at ERROR with `exc_info=True` | _pending_ |
| W-22 | Silent audit write failures in chat handler -- conversation continues with zero audit trail if DB is down | BE-11, DS-06 | `_chat_handler.py:131` | Track consecutive failures; log ERROR; send degradation warning to client | _pending_ |
| W-23 | S3 upload failure leaves phantom Document row (`status=UPLOADED`, no file) -- extraction task crashes on None path | DS-01 | `document.py:149-219` | Wrap S3 upload in try/except; delete DB row or set `UPLOAD_FAILED` on failure | _pending_ |
| W-24 | Condition lifecycle operations (respond, clear, waive, return) have no `SELECT FOR UPDATE` -- concurrent requests create duplicate audit events | DS-04, DS-05 | `condition.py:89-143`, `decision.py:235-348` | Add `with_for_update()` when fetching condition/application rows before modification | _pending_ |
| W-25 | `lo_submit_to_underwriting` does two-step stage transition without atomicity -- first succeeds, second fails leaves app stuck in PROCESSING | DS-20, DS-11 | `loan_officer_tools.py:355-430` | Both transitions in single transaction; or make tool idempotent (skip step 1 if already PROCESSING) | _pending_ |
| W-26 | Audit hash chain interleaving: chat handler opens new session per audit write, advisory lock releases between writes, concurrent sessions can read same "latest" event | TL-17, PE-20 | `audit.py`, `_chat_handler.py` | Batch audit events per chat turn in single transaction | _pending_ |
| W-27 | `_resolve_role` raises `HTTPException` from auth utility used in WebSocket context -- wrong exception type, caught by bare `except Exception` | BE-09, DS-21 | `auth.py:121-124`, `_chat_handler.py:63-64` | Have `_resolve_role` raise `ValueError`; HTTP dependency converts to HTTPException; WS handler closes connection | _pending_ |
| W-28 | Conversation history endpoints return raw dicts with no `response_model` -- no OpenAPI schema for consumers | AD-02 | `borrower_chat.py`, `loan_officer_chat.py`, `underwriter_chat.py` (history endpoints) | Define `ConversationHistoryResponse` Pydantic model | _pending_ |
| W-29 | Products endpoint returns bare array, not standard `{"data": [], "pagination": {}}` envelope | AD-03 | `public.py:14` | Wrap in standard collection envelope | _pending_ |
| W-30 | Conditions endpoint has fake pagination (`offset=0, limit=len(result), has_more=False`); no real offset/limit support | CR-22, AD-12, TL-15 | `applications.py:274-282` | Add real offset/limit parameters through to service layer | _pending_ |
| W-31 | Deploy script missing 15+ env var overrides -- production uses insecure defaults from values.yaml | DO-02 | `scripts/deploy.sh` | Add `--set secrets.<KEY>` for all secrets; or use `-f production-secrets.yaml` | _pending_ |
| W-32 | Containerfile installs dev dependencies (`[dev]`) into production image; unpinned base images | DO-03, DO-04, DO-05 | `packages/api/Containerfile`, `packages/ui/Containerfile` | Use `uv pip install --system -e .` (no `[dev]`); pin to specific versions | _pending_ |
| W-33 | `compose.yml` uses `latest` tag for MinIO and LlamaStack images -- non-deterministic builds | DO-08 | `compose.yml:212,157` | Pin to specific version tags | _pending_ |
| W-34 | Helm values contain plaintext secrets as defaults (`changeme`, `miniosecret`) | DO-09 | `values.yaml` | Set defaults to empty; add Helm `required` validation | _pending_ |
| W-35 | Liveness and readiness probes use same endpoint and config -- slow DB query kills pod instead of marking unready | DO-10 | `api-deployment.yaml` | Differentiate: lightweight `/health/liveness` for liveness; `/health/` (DB-aware) for readiness only | _pending_ |
| W-36 | Multiple config settings absent from compose and Helm (`KEYCLOAK_CLIENT_ID`, `SAFETY_*`, `S3_REGION`, etc.) | DO-11 | `config.py`, `compose.yml`, `values.yaml` | Add all Settings fields explicitly to both deployment manifests | _pending_ |
| W-37 | Technical debt items D2, D7, D16, D17 still unaddressed despite "Pre-Phase 3" gate passing; D8, D10, D18 resolved but not in Resolved table | OR-05, OR-06, TW-07, TW-12, PJ-07 | `technical-debt.md` | Re-classify D2/D7 as pre-production; move D8/D10/D18 to Resolved table; update D11 description | _pending_ |
| W-38 | Architecture document uses "PoC" 16 times; actual maturity is "MVP" | TW-05 | `plans/architecture.md` | Replace all 16 "PoC" occurrences with "MVP" | _pending_ |
| W-39 | Test coverage gaps: no direct tests for `_chat_handler` auth paths, `apply_data_scope()`, extraction prompts, agent registry cache logic, agent graph topology | TE-01, TE-02, TE-03, TE-04, TE-06 | Various test files | Add targeted unit tests for these critical modules | _pending_ |
| W-40 | Decision service test mocks override return values in `fake_refresh` -- tests verify mock output, not service logic | TE-07, TE-08 | `test_decision.py`, `test_decision_tools.py` | Verify arguments passed to service calls (`call_args`); test pre-commit object state | _pending_ |
| W-41 | Test mock helpers duplicated across files (`_mock_condition` 2 variants, `_uw_user()` 2 copies, `_mock_app()` 3 copies) | TE-11, TE-14 | `test_condition.py`, `test_decision.py`, `test_decision_tools.py` | Consolidate into `tests/factories.py` | _pending_ |
| W-42 | No `.env.example` file -- 27+ env vars with no reference for developers | TW-08, DO-15 | (missing file) | Create `.env.example` at project root grouped by subsystem | _pending_ |

---

## Reviewer Disagreements

| # | Issue | Location | Reviewer A | Reviewer B | Disposition |
|---|-------|----------|-----------|-----------|-------------|
| D-1 | Audit advisory lock: correctness issue vs acceptable MVP limitation | `audit.py:60` | TL-17 (Critical): hash chain interleaving under concurrent tool operations is structurally wrong | AR-12 (Suggestion): acceptable for MVP, document as known constraint | _pending_ |
| D-2 | Safety output shields fail-open: intentional vs security gap | `safety.py:180-184` | SE-16 (Warning): fail-open defeats purpose; add circuit breaker | DS-28 (Suggestion): defense-in-depth; chat handler already filters empty messages | _pending_ |

---

## Suggestions (improve if approved)

| # | Finding | Flagged By | Location | Suggested Resolution | Disposition |
|---|---------|-----------|----------|---------------------|-------------|
| S-1 | `_TIER_LABELS` dict duplicated in KB search and compliance tools | CR-09 | `search.py:21`, `compliance_tools.py:27` | Define once in search module, import in tools | _pending_ |
| S-2 | `_DOC_TYPE_LABELS` and `_DISCLOSURE_BY_ID` imported across module boundary with underscore (private) prefix | AR-07, AR-08, CR-19, BE-17 | `borrower_tools.py:30,293,351` | Remove underscore prefix or expose via public accessor function | _pending_ |
| S-3 | `_compute_risk_factors` returns untyped 113-line nested dict | CR-17 | `underwriter_tools.py:292-405` | Define `RiskAssessment` dataclass for return value | _pending_ |
| S-4 | `.replace('_', ' ').title()` enum formatting pattern repeated ~15 times | CR-23 | Across 15 files | Create `format_enum_label()` utility | _pending_ |
| S-5 | InjectedState tool params use `= None` default -- misleading, should fail loudly if state missing | CR-20 | `condition_tools.py`, `decision_tools.py` (10 occurrences) | Remove `= None` defaults from InjectedState parameters | _pending_ |
| S-6 | Agent registry `checkpointer` not in cache key -- returns stale graph if checkpointer changes | CR-25, AR-18 | `registry.py:56-94` | Include checkpointer identity in cache key or document assumption | _pending_ |
| S-7 | `DOCUMENT_REQUIREMENTS` dict has 130 lines of redundancy | CR-27 | `completeness.py:37-168` | Factor out common sets as named constants | _pending_ |
| S-8 | Urgency sort in `uw_queue_view` compares StrEnum values with integer fallback -- works by alphabetical coincidence | CR-28, CR-29 | `underwriter_tools.py:80-85` | Use explicit integer `_URGENCY_ORDER` mapping | _pending_ |
| S-9 | `get_latest_decision` docstring contradicts implementation (says None, returns `{"no_decisions": True}`) | CR-13 | `decision.py:375-402` | Update docstring to match actual behavior | _pending_ |
| S-10 | `_business_days_between` uses day-by-day loop; inline import of `timedelta` | CR-14, PE-05 | `checks.py:52-68` | Use O(1) arithmetic formula; move import to module level | _pending_ |
| S-11 | Adverse action audit stores `decision_id` param (may be None) instead of actual `dec.id` | CR-15 | `decision_tools.py:398` | Change to `"decision_id": dec.id` | _pending_ |
| S-12 | Unused import `DocumentType` in `decision_tools.py` | CR-16 | `decision_tools.py:15` | Remove; run `ruff check --select F401` | _pending_ |
| S-13 | Deferred imports of `ApplicationFinancials` and `select` inside tool function bodies | CR-06 | `underwriter_tools.py`, `compliance_check_tool.py` (4 instances) | Move to module-level imports | _pending_ |
| S-14 | `uw_application_detail` is 152-line "god function" -- queries 5 sources + formats in one function | CR-08 | `underwriter_tools.py:129-280` | Extract formatting to pure function `_format_application_detail()` | _pending_ |
| S-15 | Session sourcing difference (tools use `SessionLocal()`, routes use `Depends(get_db)`) undocumented | BE-07 | `agents/` vs `routes/` | Add docstring in agents module explaining the rationale | _pending_ |
| S-16 | Compliance gate belongs in service layer, not tool layer -- REST endpoint would bypass it | OR-12 | `decision_tools.py:50-81` | Move compliance gate check into `services/decision.py:_resolve_decision()` | _pending_ |
| S-17 | `document_metadata_only` flag on CEO DataScope exists but is not enforced anywhere | OR-11 | `auth.py:137-150` | Verify enforcement in document service before Phase 5 | _pending_ |
| S-18 | Phase 5 CEO agent needs aggregate query patterns that don't exist yet | OR-10 | Service layer (general) | Plan analytics service additions early in Phase 5 | _pending_ |
| S-19 | `HmdaLoanData.snapshot_at` has `onupdate=func.now()` -- semantically wrong for immutable snapshot timestamp | DB-20 | `models.py:439-459` | Remove `onupdate`; add separate `updated_at` column | _pending_ |
| S-20 | `RateLock` model missing `updated_at` column (every other mutable model has one) | DB-07 | `models.py:176-194` | Add `updated_at` in migration | _pending_ |
| S-21 | `ConditionItem.severity` and `status` typed as `str | None` instead of enums; `DecisionItem.decision_type` same issue | AD-06, AD-07 | `schemas/condition.py:16-17`, `schemas/decision.py:16-17` | Use `ConditionSeverity`, `ConditionStatus`, `DecisionType` enums | _pending_ |
| S-22 | `ErrorResponse` missing RFC 7807 `instance` field; error details not populated with `request.url.path` | AD-08 | `schemas/error.py`, `main.py:84-91` | Add `instance: str = ""` and populate with request path | _pending_ |
| S-23 | Verb-based URL paths: `/calculate-affordability`, `/hmda/collect`, `/conditions/{id}/respond` | AD-04, AD-05, AD-09 | `public.py:20`, `hmda.py:16`, `applications.py:285` | Restructure to noun-based resource URLs | _pending_ |
| S-24 | Audit endpoints use non-standard envelope (`count` + `events` vs `data` + `pagination`) | AD-11, AD-10 | `schemas/admin.py` | Rename to standard `data` + `Pagination`; add offset/limit parameters | _pending_ |
| S-25 | All POST-create endpoints missing `Location` header in response | AD-16 | `applications.py`, `documents.py`, `hmda.py` | Add `response.headers["Location"]` with new resource URL | _pending_ |
| S-26 | PII masking middleware only covers `ssn` and `dob` -- `email`, `phone`, `employer_name` unmasked for CEO | SE-17 | `pii.py:61-64` | Register maskers for additional PII fields | _pending_ |
| S-27 | Validation error responses expose Pydantic internals (field paths, types, constraints) | SE-18 | `main.py:109` | Sanitize to show only field names and human-readable messages | _pending_ |
| S-28 | LLM extraction output stored without validation -- indirect prompt injection risk | SE-12, SE-13 | `extraction.py:130-138,207-212` | Validate `field_name` against allowlist per doc type; add length limits | _pending_ |
| S-29 | BorrowerSummary exposes full SSN in list responses for all roles except CEO | SE-26 | `applications.py:55` | Mask SSN to last-4 in summary; expose full only via dedicated endpoint | _pending_ |
| S-30 | ECOA compliance check hardcodes `has_demographic_query=False` -- never detects missing demographic data | SE-27 | `compliance_check_tool.py:153` | Query HMDA schema for actual demographic data existence | _pending_ |
| S-31 | LLM can set `confirmed=true` on first call to `uw_render_decision` -- no server-side enforcement of two-phase flow | SE-15 | `decision_tools.py:167,189` | Require `proposal_id` from Phase 1 as mandatory param for Phase 2 | _pending_ |
| S-32 | Containerfile copies `uv` into runtime image but never uses it; `uv` and base images unpinned | DO-16, DO-16b | `packages/api/Containerfile` | Remove unused `uv` COPY; pin image versions | _pending_ |
| S-33 | Helm chart placeholder URLs/emails (`example/summit-cap`, `dev@example.com`) | DO-19 | `Chart.yaml` | Update to actual repository URL | _pending_ |
| S-34 | Planning doc path references still use `summit_cap`/`summit_cap_db` (actual paths differ) | TW-06 | `architecture.md`, `interface-contracts-phase-1.md`, `requirements.md` | Update paths to match codebase | _pending_ |

---

## Phase 5 Readiness (tracked from product-manager and project-manager reviews)

These are not code bugs but scope/planning items for Phase 5 disposition:

| # | Item | Flagged By | Notes | Disposition |
|---|------|-----------|-------|-------------|
| P-1 | CEO persona (F12/F13) is entirely unimplemented -- largest Phase 5 deliverable | PM-01, PJ-03 | Analytics service, CEO agent + tools, dashboard endpoints all net-new | _pending_ |
| P-2 | F38 TrustyAI metrics deferred but CEO fair lending panel (S-5-F12-03) depends on it | PM-04, PJ-02 | Pure-Python fallback plan exists at `plans/deferred/f38-trustyai-fairness-metrics.md` | _pending_ |
| P-3 | Seed data needs expansion for CEO dashboard (historical loans, denial reasons, LO performance variation) | PM-02 | Audit fixtures against S-5-F12-01 through S-5-F12-05 acceptance criteria | _pending_ |
| P-4 | F23 Container Deployment not started; Helm chart needs fixes (C-13, W-31, W-34, W-35) | PM-03, PJ-11 | Can parallelize with CEO work (independent) | _pending_ |
| P-5 | LoanType enum: ARM missing (replaced by USDA which was never in product plan) | PM-06 | Affects demo credibility -- public assistant discusses "six products including ARM" | _pending_ |
| P-6 | Phase 5 is 25 stories (largest phase) -- needs sub-chunking into 3 milestones | PJ-12 | Suggested: (a) Analytics backend, (b) CEO experience, (c) Infrastructure | _pending_ |
| P-7 | LangFuse API capabilities unverified -- F39 depends on trace aggregation endpoints | PJ-10 | High-risk assumption; verify before Phase 5 technical design | _pending_ |
| P-8 | No interface contracts for Phases 3-4 -- no single doc for frontend developers | TW-13 | Create `interface-contracts-phase-3.md` and `-phase-4.md` | _pending_ |
