# Consolidated Review: Pre-UI

**Reviews consolidated:** code-reviewer, security-engineer, architect, tech-lead, backend-developer, database-engineer, api-designer, test-engineer, performance-engineer, devops-engineer, debug-specialist, technical-writer, project-manager, orchestrator
**Date:** 2026-03-02
**Verdicts:** All reviewers: APPROVE or REQUEST_CHANGES (see individual files)

## Summary

- Total raw findings across all reviews: 177
- De-duplicated findings: 103
- Reviewer disagreements: 5
- Breakdown: 25 Critical, 50 Warning, 28 Suggestion

---

## Triage Required

### Critical (must fix before proceeding)

| # | Finding | Flagged By | Location | Suggested Resolution | Disposition |
|---|---------|-----------|----------|---------------------|-------------|
| C-1 | `decision_proposals` written to LangGraph state but not declared in `AgentState` -- silently dropped between graph nodes, breaking two-phase human-in-the-loop decision flow | Tech Lead (TL-01) | `agents/base.py:102`, `agents/decision_tools.py:211` | Add `decision_proposals: dict` to `AgentState` with default `{}` | **Fix** |
| C-2 | N+1 queries in `get_lo_performance`: 7N+1 DB round trips (6 counts + 1 avg per LO) | Perf (PE-01), DB (DB-01), Code (CR-06), Tech Lead (TL-07) | `services/analytics.py:422-518` | Consolidate into GROUP BY queries with conditional aggregation (see PE-01 sketch) | Defer -- demo scale (5-10 LOs) is acceptable |
| C-3 | PII masking bypassed on WebSocket -- CEO chat tool responses stream unmasked PII; middleware only intercepts HTTP | Security (SE-01) | `routes/_chat_handler.py`, `middleware/pii.py` | Apply PII masking to WebSocket output before `ws.send_json` | **Fix** |
| C-4 | `audit_export` writes audit event with null `user_id`/`user_role` -- compliance gap for bulk export | Security (SE-02), Backend (BE-01) | `routes/audit.py:187` | Add `user: CurrentUser` dependency, pass to `write_audit_event` | **Fix** |
| C-5 | `audit_export` CSV format bypasses PII masking (middleware only processes `application/json`); CEO gets raw PII in CSV | Backend (BE-02), Orchestrator (OR-11) | `routes/audit.py:163`, `middleware/pii.py:111` | Apply PII masking in `export_events` service before serialization, or restrict CSV to admin-only | **Fix** |
| C-6 | `audit_export` has no `response_model` -- OpenAPI spec has no contract for this endpoint | API Designer (AD-01) | `routes/audit.py:163` | Add `responses` metadata documenting both JSON and CSV content types | Improvement |
| C-7 | `build_agent_graph` creates `ChatOpenAI` for embedding tier (non-chat model) | Tech Lead (TL-02) | `agents/base.py:366-373` | Filter to `_CHAT_TIERS = {"fast_small", "capable_large"}` in the loop | Defer -- currently harmless |
| C-8 | `_compute_turn_times` issues 4 sequential independent queries | Perf (PE-02) | `services/analytics.py:107-183` | Merge into UNION ALL or use `asyncio.gather` | Defer -- demo scale acceptable |
| C-9 | `create_async_engine` has no pool parameters -- default pool_size=5, no `pool_pre_ping` | DB (DB-02) | `packages/db/src/db/database.py:16-22` | Add `pool_size=10, max_overflow=20, pool_timeout=30, pool_pre_ping=True`; expose in `DatabaseSettings` | Improvement |
| C-10 | `add_borrower` double commit -- junction row committed before audit event; crash between commits creates unaudited state change | Debug (DS-02), DB (DB-04) | `services/application.py:299-314` | Write audit event before single commit; same fix for `remove_borrower` | **Fix** |
| C-11 | Orphaned S3 object when `session.commit()` fails after successful S3 upload -- inverse of deferred W-23 | Debug (DS-01) | `services/document.py:197-217` | Wrap commit in try/except; on failure, delete S3 object as compensation | Defer -- edge case unlikely in demo |
| C-12 | API Containerfile installs `[dev]` extras in production image (pytest, ruff in prod) | DevOps (DO-01) | `packages/api/Containerfile:21` | Use `uv pip install --system -e .` (no dev) in runtime stage | Defer -- image size, not functional |
| C-13 | Helm database init ConfigMap embeds hardcoded role passwords (`lending_pass`, `compliance_pass`) in plain text | DevOps (DO-02) | `deploy/helm/.../database-configmap.yaml:22-24` | Source from Secret or add comment that these must match `COMPLIANCE_DATABASE_URL` | Defer -- demo credentials acceptable |
| C-14 | `@pytest.mark.asyncio` decorators (309 instances) conflict with `asyncio_mode = "auto"` -- creates silent vacuous-pass risk if mode changes | Test (TE-01) | 29 test files | Remove all 309 decorators (keep `auto` mode) or switch to `strict` | Defer -- tests pass today |
| C-15 | `make_mock_session` returns same `execute()` result for all queries -- multi-query route tests pass for wrong reason | Test (TE-02) | `tests/functional/mock_db.py:20-49` | Generalize `_make_conditions_session` pattern with `side_effects` list | Defer -- tests pass today |
| C-16 | No RBAC integration tests for decisions route -- borrower 403 and LO 403 paths untested | Test (TE-03) | `tests/test_decisions_route.py` | Add functional tests with AUTH_DISABLED=False verifying role gating | Defer -- not a runtime bug |
| C-17 | requirements.md marks F38 (TrustyAI) and F26 (adversarial defenses) as complete despite being deferred | PM (PJ-01) | `plans/requirements.md:511,514` | Change checkmarks to "Deferred" markers with pointers to deferral docs | **Fix** |
| C-18 | No fairness endpoint for CEO dashboard -- S-5-F12-03 and S-5-F13-09 have no backend; frontend will hit dead end | PM (PJ-02) | `routes/analytics.py`, `agents/ceo_tools.py` | Add stub endpoint returning "Insufficient data" or explicitly mark stories as deferred | Improvement |
| C-19 | CORS default `["http://localhost:5173"]` blocks containerized UI on port 3000; `compose.yml` does not set `ALLOWED_HOSTS` | Orchestrator (OR-02) | `core/config.py:33`, `compose.yml:89` | Add `http://localhost:3000` to default or set in compose.yml | **Fix** |
| C-20 | Borrower cannot see their own decision outcome via REST -- excluded from decisions endpoint RBAC | Orchestrator (OR-01) | `routes/decisions.py:19-29` | Add `UserRole.BORROWER` with data scope filtering, or create borrower-facing decision summary endpoint | **Fix** |
| C-21 | API README missing Phase 5 routes: CEO chat, analytics, model monitoring (entire subsystem undocumented) | Tech Writer (TW-01) | `packages/api/README.md` | Add CEO agent row, CEO chat/history entries, analytics + model monitoring REST sections | **Fix** |
| C-22 | Root README is still the AI QuickStart template -- not a Summit Cap readme | Tech Writer (TW-02) | `README.md:1-4, 474-560` | Replace with Summit Cap README: project description, Quick Start, Architecture, Personas | **Fix** |
| C-23 | Root README development URLs show wrong DB port (5432 vs actual 5433) and wrong frontend port (3000 vs 5173) | Tech Writer (TW-03), Orchestrator (OR implied via TW-05) | `README.md:132, 204, 238, 398` | Change to `localhost:5433` for DB, `localhost:5173` for frontend, add `localhost:6006` for Storybook | **Fix** |
| C-24 | `POST /admin/seed` accepts `force` as query parameter on a POST (violates convention: POST uses body) | API Designer (AD-02) | `routes/admin.py:16-38` | Create `SeedRequest(BaseModel)` with `force: bool` field | Defer -- not breaking |
| C-25 | Health endpoint returns bare array `[{...}]` instead of standard envelope | API Designer (AD-03) | `routes/health.py:24-44` | Wrap in envelope or document as intentional deviation | Defer -- not breaking |

---

### Warning (should fix)

| # | Finding | Flagged By | Location | Suggested Resolution | Disposition |
|---|---------|-----------|----------|---------------------|-------------|
| W-1 | `get_decision` route fetches ALL decisions then filters by ID in Python -- O(N) vs O(1) | Code (CR-01), Backend (BE-04), Orchestrator (OR-05) | `routes/decisions.py:76-84` | Add `get_decision_by_id` service function with direct SQL WHERE | Improvement |
| W-2 | `ALLOWED_CONTENT_TYPES` defined redundantly in `document.py` and `storage.py` | Code (CR-02), Architect (AR-02) | `services/document.py:24`, `services/storage.py:22` | Remove copy from `storage.py` | **Fix** |
| W-3 | `log_observability_status` uses WARNING level for informational startup messages | Code (CR-03) | `observability.py:84-89` | Change to `logger.info()` | **Fix** |
| W-4 | `_PII_FIELD_MASKERS` initialized as empty dict then reassigned -- fragile pattern | Code (CR-04) | `middleware/pii.py:25,61` | Remove empty init on line 25; define once on line 61 | Improvement |
| W-5 | `_percentile` re-sorts input on every call; callers pass pre-sorted lists (3x redundant sort per metric set) | Code (CR-05) | `services/model_monitoring.py:78-89` | Remove `sorted()` call, trust caller; update docstring | Defer |
| W-6 | `disclosure_status` tool has repeated deferred import inside loop body | Code (CR-08) | `agents/borrower_tools.py:339,348` | Move import to function top or module level | Defer |
| W-7 | Unused `import logging` and `logger` in `condition_tools.py` | Code (CR-07) | `agents/condition_tools.py:13,32` | Remove unused import and logger | **Fix** |
| W-8 | No security response headers (X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy) | Security (SE-03) | `main.py:58-75` | Add Starlette middleware setting minimum headers | Improvement |
| W-9 | Conversation history thread ownership verification function exists but is never called | Security (SE-04) | `routes/_chat_handler.py:334`, `services/conversation.py:134` | Call `verify_thread_ownership` in history endpoint | Defer |
| W-10 | LangFuse pagination unbounded -- no max_pages guard, potential OOM on large time ranges | Security (SE-05), Debug (DS-05), Tech Lead (TL-16) | `services/langfuse_client.py:100-117` | Add `_MAX_PAGES = 50` guard and type check on `totalPages` | Improvement |
| W-11 | Dual `Settings` classes with duplicated DB URL defaults; DB package missing `env_file` | Architect (AR-01, AR-08) | `core/config.py:19`, `packages/db/src/db/config.py:10` | Add `env_file` to `DatabaseSettings` or add startup assertion | Defer |
| W-12 | `intake.py` imports `mask_ssn` from middleware layer -- dependency direction violation | Architect (AR-03) | `services/intake.py:20` | Move `mask_ssn` to `core/masking.py` | Defer |
| W-13 | Document upload content-type validation duplicated in route and service layers | Architect (AR-04) | `routes/documents.py:72-78`, `services/document.py:168` | Remove route-level check; let service own validation | Defer |
| W-14 | `_chat_handler.py` imports private (`_` prefixed) functions from `middleware.auth` | Architect (AR-05) | `routes/_chat_handler.py:20` | Promote to public API or extract `core.auth.decode_and_resolve()` | Defer |
| W-15 | Model monitoring route sub-endpoints each fetch full summary then discard 3/4 of it | Architect (AR-06), Backend (BE-11), API Designer (AD-16) | `routes/model_monitoring.py:55-111` | Remove sub-endpoints (use summary only) or add category filter param to service | Defer |
| W-16 | CEO model monitoring tools each call `get_model_monitoring_summary` independently (4x fetch on "full report") | Tech Lead (TL-04), Debug (DS-09), Perf (PE-15) | `agents/ceo_tools.py:486-657` | Accept for MVP (60s cache mitigates); consider single `ceo_model_health` tool later | Defer |
| W-17 | `session_id` read from agent state but never populated -- KB search audit events have null session correlation | Tech Lead (TL-03) | `agents/compliance_tools.py:51`, `agents/base.py:102` | Add `session_id: str` to `AgentState` and pass from chat handler | Defer |
| W-18 | `tool_auth` denial injects `AIMessage` confusing LLM conversation history | Tech Lead (TL-05) | `agents/base.py:248-258` | Use `SystemMessage` or `ToolMessage` with error status | Defer |
| W-19 | CEO audit tools write audit events outside the tool's session scope -- failed fetches unaudited | Tech Lead (TL-06) | `agents/ceo_tools.py:490-498, 538-551` | Wrap entire operation in single try/except with audit on failure | Defer |
| W-20 | `ceo_audit_search` fetches 100 events but displays only 50; header shows misleading count | Tech Lead (TL-10) | `agents/ceo_tools.py:412, 438` | Reduce limit to 50 or display all fetched events | Defer |
| W-21 | `InjectedState` default value inconsistency across tool modules (None vs {} vs no default) | Tech Lead (TL-09) | Multiple tool files | Standardize on no default (correct for InjectedState) | Defer |
| W-22 | CEO application lookup LIKE wildcards `%` and `_` not escaped in user input | Tech Lead (TL-08), Security (SE-06) | `agents/ceo_tools.py:228` | Escape wildcards before interpolation | Improvement |
| W-23 | PIIMaskingMiddleware copies stale `Content-Length` header after rewriting body | Backend (BE-03) | `middleware/pii.py:130` | Strip `content-length` from headers dict before rebuilding Response | **Fix** |
| W-24 | `update_application` PATCH with both stage + fields can create partially-updated state | Backend (BE-05) | `routes/applications.py:367` | Add comment documenting ordering dependency; consider single service call | Defer |
| W-25 | Health endpoint swallows all DB import errors silently -- misconfigured DB goes undetected | Backend (BE-08) | `routes/health.py:12-16` | Log the specific import exception at WARNING level | Defer |
| W-26 | Initial migration downgrade chain broken: re-added `borrower_id` is nullable vs original non-null | DB (DB-03) | Alembic migration `fe5adcef3769`, `f6a7b8c9d0e1` | Add `# DATA LOSS WARNING` comment; raise on downgrade if multi-borrower apps exist | Defer |
| W-27 | `HmdaLoanData.application_id` has no FK constraint -- orphaned rows on delete | DB (DB-05) | `models.py:448` | Add FK from `hmda.loan_data.application_id` to `public.applications.id` | Defer |
| W-28 | `_compute_top_denial_reasons` pulls all denial JSONB rows into Python for counting | DB (DB-07), Perf (PE-06) | `services/analytics.py:305-362` | Use `jsonb_array_elements_text` + GROUP BY in SQL | Defer |
| W-29 | Missing index on `audit_events.timestamp` -- time-range queries do full table scans | DB (DB-08) | `models.py:331`, `services/audit.py:240` | Add migration: `CREATE INDEX ix_audit_events_timestamp` | Defer |
| W-30 | `DocumentExtraction` has no unique constraint on `(document_id, field_name)` -- re-extraction appends duplicates | DB (DB-09) | `models.py:304-322` | Add unique constraint + upsert in extraction service | Defer |
| W-31 | `KBChunk.embedding` nullable -- partial ingestion silently excluded from search | DB (DB-10) | `models.py:402` | Make NOT NULL; ingestion should fail atomically | Defer |
| W-32 | `upload_document` returns `None` but declares `-> Document` return type | DB (DB-06), Debug (DS-07), Code (CR-14) | `services/document.py:149-187` | Change return type to `Document | None` | **Fix** |
| W-33 | `RateLockResponse.status` uses `str` instead of enum (not covered by deferred S-21) | API Designer (AD-04) | `schemas/rate_lock.py:12` | Define `RateLockStatus` enum | **Fix** |
| W-34 | `DecisionTraceResponse.denial_reasons` typed `list | dict | None` -- untyped union in OpenAPI | API Designer (AD-05) | `schemas/audit.py:71` | Change to `list[str] | None` | **Fix** |
| W-35 | `HmdaCollectionResponse.conflicts` typed `list[dict] | None` -- opaque schema | API Designer (AD-06) | `schemas/hmda.py:33` | Define `HmdaDemographicConflict` schema | **Fix** |
| W-36 | `AuditEventItem.event_data` typed `dict | str | None` -- incompatible union | API Designer (AD-07) | `schemas/audit.py:19` | Normalize to `dict[str, object] | None` | **Fix** |
| W-37 | `SeedStatusResponse.summary` typed `dict | None` -- opaque blob | API Designer (AD-08) | `schemas/admin.py:29` | Define `SeedSummary` schema | **Fix** |
| W-38 | `DecisionTraceResponse.events_by_type` typed `dict[str, list]` -- untyped inner list | API Designer (AD-09) | `schemas/audit.py:73` | Change to `dict[str, list[AuditEventItem]]` | **Fix** |
| W-39 | PATCH `/applications/{id}` conflates field updates and stage transitions in one endpoint | API Designer (AD-10), Orchestrator (OR-09) | `routes/applications.py:336-399` | Expose `POST /applications/{id}/stage-transitions` or document `stage` field behavior | Defer -- breaking change |
| W-40 | WebSocket auth and message protocol not documented in OpenAPI or companion doc | API Designer (AD-12), Orchestrator (OR-06) | `routes/_chat_handler.py` | Create `docs/websocket-protocol.md` or add to API README | **Fix** |
| W-41 | Audit endpoint paths use singular nouns (`/application/`, `/decision/`) vs convention plural | API Designer (AD-13) | `routes/audit.py:74` | Rename to `/applications/` and `/decisions/` | Defer -- breaking change |
| W-42 | Audit session endpoint uses query parameter for resource ID instead of path parameter | API Designer (AD-14) | `routes/audit.py:56-71` | Move to `GET /audit/sessions/{session_id}` | Defer -- breaking change |
| W-43 | Response envelope inconsistency: 6+ different patterns across endpoint families | API Designer (AD-17), Orchestrator (OR-04) | Multiple routes/schemas | Document the three response patterns with explicit endpoint lists | **Fix** |
| W-44 | Unindexed JSONB lookups on `audit_events.event_data["to_stage"]` in hot analytics paths | Perf (PE-03) | `services/analytics.py:136-151` | Add partial index on `event_data->>'to_stage'` WHERE `event_type = 'stage_transition'` | Defer |
| W-45 | PIIMaskingMiddleware buffers entire response body in memory; O(n^2) bytes concatenation | Perf (PE-04), Debug (DS-06) | `middleware/pii.py:102-135` | Use `b"".join(chunks)` list pattern instead of `+=` loop | **Fix** |
| W-46 | `get_pipeline_summary` issues 5 sequential queries that can be merged to 1-2 | Perf (PE-05) | `services/analytics.py:40-104` | Merge scalar queries into single conditional aggregate | Defer |
| W-47 | `agent_capable` calls `bind_tools` on every LLM invocation (re-serializes tool schemas) | Perf (PE-07) | `agents/base.py:202-207` | Pre-bind tools once at graph construction time | Improvement |
| W-48 | `get_agent` performs filesystem stat() on every 5s debounce window per chat message | Perf (PE-08) | `agents/registry.py:62-106` | Add `AGENT_HOT_RELOAD=false` flag for production | Defer |
| W-49 | Chat handler opens new DB session per audit event within a single agent turn | Perf (PE-09) | `routes/_chat_handler.py:124-137` | Batch audit events per turn or share session | Defer |
| W-50 | `func.to_char` on `created_at` prevents index use in denial trend grouping | Perf (PE-10) | `services/analytics.py:261-302` | Use `date_trunc` instead; format in Python | Defer |
| W-51 | Application loaded 2-3x per status request (chained `get_application` calls) | Perf (PE-11) | `services/status.py:98-181`, `routes/applications.py:208` | Refactor `check_completeness` to accept pre-loaded Application | Defer |
| W-52 | UI Containerfile uses `pnpm@latest` with `--no-frozen-lockfile` -- non-deterministic build | DevOps (DO-03) | `packages/ui/Containerfile:19,23` | Pin pnpm version, use `--frozen-lockfile` | Defer |
| W-53 | API Containerfile copies entire `/usr/local/bin` from builder (includes dev tooling) | DevOps (DO-04) | `packages/api/Containerfile:37` | Copy only `uvicorn` and `alembic` binaries | Defer |
| W-54 | API has no compose dependency on Keycloak when auth profile is active | DevOps (DO-05) | `compose.yml:83-87` | Document startup ordering or add conditional dependency | Defer |
| W-55 | `langfuse-worker` has no liveness/readiness probes in Helm chart | DevOps (DO-06) | `deploy/helm/.../langfuse.yaml:197-347` | Add probes | Defer |
| W-56 | LangFuse Helm template embeds DB credentials in plain-text env value (not from Secret) | DevOps (DO-07) | `deploy/helm/.../langfuse.yaml:55, 223` | Construct URL in Secret and reference via secretKeyRef | Defer |
| W-57 | MinIO in Helm chart has no security context -- runs as root | DevOps (DO-08) | `deploy/helm/.../minio.yaml:20-23` | Apply `runAsNonRoot` security context | Defer |
| W-58 | Keycloak Helm deploys with `start-dev` (H2 in-memory, data lost on restart) | DevOps (DO-09) | `deploy/helm/.../keycloak.yaml:33-35` | Document limitation or switch to `start` with external DB | Defer |
| W-59 | `deploy.sh` passes empty string for unset env vars -- overrides `values.yaml` defaults | DevOps (DO-10) | `scripts/deploy.sh:55-91` | Use `${VAR:+--set key="$VAR"}` pattern | Defer |
| W-60 | `smoke-test.sh` prefers docker over podman (opposite of Makefile) | DevOps (DO-11) | `scripts/smoke-test.sh:15` | Align detection order with Makefile (podman first) | Defer |
| W-61 | Redis and ClickHouse in Helm use unqualified image names (no registry prefix) | DevOps (DO-12) | `deploy/helm/.../redis.yaml:26` | Add `docker.io/` prefix or use values.yaml image entries | Defer |
| W-62 | Agent graph cache has no thread-safety guard for concurrent rebuilds | Debug (DS-03) | `agents/registry.py:62-106` | Add `asyncio.Lock` per agent name | Improvement |
| W-63 | `StorageService._ensure_bucket` swallows all `ClientError` including permission errors | Debug (DS-04) | `services/storage.py:57-63` | Check error code; only handle `NoSuchBucket`/`404` | Improvement |
| W-64 | `lo_application_detail` accesses ORM attributes after session close -- fragile eager-load dependency | Debug (DS-08) | `agents/loan_officer_tools.py:80-123` | Access and format all ORM attributes inside `async with` block | Improvement |
| W-65 | `_extract_text_from_pdf_sync` does not close PDF handle on exception | Debug (DS-12) | `services/extraction.py:190-201` | Use try/finally to ensure `pdf.close()` | **Fix** |
| W-66 | UI README references non-existent `quick-stats/` component | Tech Writer (TW-04) | `packages/ui/README.md:45, 86, 250` | Remove from directory listing and component lists | Improvement |
| W-67 | API README missing 6 environment variables from `config.py` | Tech Writer (TW-06) | `packages/api/README.md:204-214` | Add DB_ECHO, APP_NAME, UPLOAD_MAX_SIZE_MB, S3_REGION, SAFETY_API_KEY, JWKS_CACHE_TTL | Defer |
| W-68 | API README `config/agents/` path is ambiguous (project root vs package root) | Tech Writer (TW-07) | `packages/api/README.md:35, 152` | Clarify as relative to project root | Defer |
| W-69 | Demo walkthrough omits CEO model monitoring capability (F39) | Tech Writer (TW-08) | `plans/demo-walkthrough.md:40-48` | Add model monitoring bullet to CEO section | Improvement |
| W-70 | AUTH_DISABLED dev user always ADMIN -- no way to test per-role UI views without Keycloak | Orchestrator (OR-03) | `middleware/auth.py:146-152` | Accept `X-Dev-Role` header when `AUTH_DISABLED=true` | **Fix** |
| W-71 | S-5-F13-07 comparative analytics has no dedicated tool; LLM must chain two calls and compute delta | PM (PJ-03) | `agents/ceo_tools.py` | Add `ceo_comparative_summary` tool or date-range param to `get_pipeline_summary` | Defer |
| W-72 | Audit PII masking is middleware-only (S-5-F13-04 requires service-layer masking for event_data JSONB) | PM (PJ-04) | `middleware/pii.py`, `services/audit.py` | Add service-layer sanitization of event_data for CEO role | Defer |
| W-73 | requirements.md Story Map lists F26 stories as P0 with no deferral marker | PM (PJ-05) | `plans/requirements.md:126-129` | Add Status column or deferral note | Defer |
| W-74 | Duplicate `_local_condition_mock` in `test_condition_flow.py` duplicates `make_mock_condition` from factories | Test (TE-04) | `tests/functional/test_condition_flow.py:20-41` | Import from `tests.factories` | Defer |
| W-75 | Analytics integration tests use inline seeder that risks count drift across test sessions | Test (TE-05) | `tests/integration/test_analytics.py:23-120` | Assert `>= N` or add explicit truncation | Defer |
| W-76 | No test for `confirmed=True` decision path in `uw_render_decision` tool | Test (TE-06) | `tests/test_decision_tools.py` | Add confirmed-approve test exercising `render_decision` | Defer |
| W-77 | Analytics unit tests use fragile sequential mock ordering -- silently returns wrong data if query order changes | Test (TE-07) | `tests/test_analytics.py:27-52` | Add inline comments mapping each mock result to its query | Defer |
| W-78 | `truncate_all` fixture omits conversation/checkpoint tables | Test (TE-08) | `tests/integration/conftest.py:413-426` | Add `checkpoints`, `checkpoint_writes`, `checkpoint_blobs` if they exist | Defer |
| W-79 | No WebSocket protocol test with mismatched-role token (auth-to-message flow) | Test (TE-09) | `tests/test_borrower_chat.py` et al. | Add WS test with wrong-role token verifying error frame or close code 4003 | Defer |
| W-80 | `test_decisions_route.py` uses `"approve"` instead of enum value `"approved"` | Test (TE-10) | `tests/test_decisions_route.py:22` | Fix to `"approved"` and add `decision_type` assertion | **Fix** |

---

### Reviewer Disagreements

| # | Issue | Location | Position A | Position B | Disposition |
|---|-------|----------|-----------|-----------|-------------|
| D-1 | N+1 in `get_lo_performance` severity | `services/analytics.py:422` | PE, DB: **Critical** (hot path, 7N+1) | CR, TL: **Warning** (acceptable at demo scale) | Defer -- demo scale |
| D-2 | Audit export CSV PII bypass severity | `routes/audit.py:163` | BE: **Critical** (data leak path) | OR: **Suggestion** (minor export path) | **Fix** (resolved via C-5) |
| D-3 | LangFuse pagination unbounded severity | `services/langfuse_client.py:100` | SE, DS: **Warning** (DoS/OOM risk) | TL: **Suggestion** (add max_pages) | Improvement (resolved via W-10) |
| D-4 | `upload_document` None return severity | `services/document.py:187` | DB, DS: **Warning** (type safety) | CR: **Suggestion** (style) | **Fix** (resolved via W-32) |
| D-5 | CEO app lookup LIKE wildcards severity | `agents/ceo_tools.py:228` | TL: **Warning** (correctness) | SE: **Suggestion** (low risk) | Improvement (resolved via W-22) |

---

### Suggestions (improve if approved)

| # | Finding | Flagged By | Location | Suggested Resolution | Disposition |
|---|---------|-----------|----------|---------------------|-------------|
| S-1 | `_apply_filters` in application service lacks type annotations | Code (CR-09) | `services/application.py:82` | Add `Select` type annotations | Defer |
| S-2 | `_business_days_between` imports `timedelta` inside function body (already at module level) | Code (CR-11) | `services/compliance/checks.py:62` | Move to module-level import | Defer |
| S-3 | `risk_tools.py` functions accept untyped `app` and `financials_rows` parameters | Code (CR-12) | `agents/risk_tools.py:31,147` | Add `Application` and `list[Borrower]` annotations | Defer |
| S-4 | `disclosure_tools.py` helpers have incomplete parameter type annotations | Code (CR-13) | `agents/disclosure_tools.py:39,128` | Add `AsyncSession`, `UserContext`, `Application` annotations | Defer |
| S-5 | `_SEVERITY_LABELS` / `_STATUS_LABELS` dicts duplicate what `format_enum_label` provides | Code (CR-15, CR-16) | `agents/loan_officer_tools.py:50`, `agents/borrower_tools.py:95` | Use `format_enum_label()` from `shared.py` | Defer |
| S-6 | `run_all_checks` returns plain `dict` instead of typed `ComplianceReport` dataclass | Code (CR-17) | `services/compliance/checks.py:272` | Define `ComplianceReport` dataclass | Defer |
| S-7 | `format_enum_label` in `shared.py` not used by `ceo_tools.py` (inline `.replace('_',' ').title()`) | Tech Lead (TL-13) | `agents/ceo_tools.py:71, 82` | Replace inline calls with `format_enum_label()` | Defer |
| S-8 | `safety.py` says "fail-closed" but `base.py` says "fail-open" -- stale docstring | Tech Lead (TL-14) | `agents/base.py:14` | Update base.py docstring to match actual fail-closed behavior | Defer |
| S-9 | `_HEDGING_PHRASES` may cause false escalations for mortgage domain ("consult your loan officer") | Tech Lead (TL-15) | `agents/base.py:49-60` | Consider domain-tuning or allow-list | Defer |
| S-10 | Keycloak realm has `sslRequired: "none"` -- fine for dev but needs prod note | Security (SE-07) | `config/keycloak/summit-cap-realm.json:3` | Add dev-only comment; document prod change | Defer |
| S-11 | Audit search `event_type` accepts arbitrary strings (minor info disclosure) | Security (SE-08) | `routes/audit.py:133` | Validate against known event type set | Defer |
| S-12 | No explicit import layering documentation for the API package | Architect (AR-09) | Project-wide | Add package-internal layer diagram to architecture.md | Defer |
| S-13 | `_chat_handler.py` underscore prefix inconsistent with its role as shared infrastructure | Architect (AR-10) | `routes/_chat_handler.py` | Rename to `chat_factory.py` or `chat_support.py` | Defer |
| S-14 | Conversation service singleton bypasses FastAPI dependency injection (along with Storage, Extraction) | Architect (AR-07) | `services/conversation.py:187` | Document the three lifecycle patterns as intentional | Defer |
| S-15 | `admin.seed_data` returns 200 instead of 201 for POST that creates resources | Backend (BE-09) | `routes/admin.py:19` | Change to 201 or document exception | Defer |
| S-16 | `get_document_content` returns a file path, not content -- semantic mismatch for frontend | Backend (BE-10) | `routes/documents.py:192` | Return presigned URL or rename to `get_document_path` | Defer |
| S-17 | `PATCH /applications/{id}` conflates stage transition with completeness endpoint routing | API Designer (AD-11) | `routes/documents.py:172` | Move completeness to applications router | Defer |
| S-18 | `ConversationHistoryResponse.data` uses standard envelope key but has no pagination | API Designer (AD-21) | `schemas/conversation.py:14` | Add pagination or rename to `messages` | Defer |
| S-19 | Analytics endpoints return raw objects without `data` envelope (documented consistency gap) | API Designer (AD-22) | `routes/analytics.py` | Document as intentional deviation | Defer |
| S-20 | `DELETE /applications/{id}/borrowers/{bid}` returns body instead of 204 | API Designer (AD-23) | `routes/applications.py:456` | Adopt convention and document, or change to 204 | Defer |
| S-21 | `DocumentFilePathResponse` leaks internal storage path to frontend | API Designer (AD-19) | `schemas/document.py:48-51` | Return presigned URL or ready-to-use download URL | Defer |
| S-22 | No API version prefix (`/v1/`) -- consistent but undocumented strategy | API Designer (AD-20) | `routes/public.py:14` | Document versioning strategy | Defer |
| S-23 | `get_lo_performance` uses string literal `"cleared"` instead of `ConditionStatus.CLEARED` | DB (DB-12) | `services/analytics.py:499` | Use enum value | Defer |
| S-24 | `add_borrower` race condition between duplicate check and insert (IntegrityError surfaces as 500) | DB (DB-13) | `services/application.py:283-299` | Add try/except for IntegrityError | Defer |
| S-25 | Migration `650767a5a0cd` missing AI assistance comment | DB (DB-11) | Alembic migration | Add comment | Defer |
| S-26 | UI README and DB README have "Generated with AI QuickStart CLI" footer | Tech Writer (TW-09) | `packages/ui/README.md:663`, `packages/db/README.md:448` | Remove | Defer |
| S-27 | DB README project structure listing is incomplete | Tech Writer (TW-10) | `packages/db/README.md:55-70` | Update to match actual files | Defer |
| S-28 | `_extract_text_from_pdf_sync` and `_pdf_first_page_to_image_sync` share the same unclosed-handle pattern | Debug (DS-12 extended) | `services/extraction.py:214-227` | Apply try/finally to both functions | Defer |

---

## Cross-References

For finding details, suggested code changes, and full context, see the individual review files in `plans/reviews/pre-ui/`:

| Reviewer | File | Criticals | Warnings | Suggestions |
|----------|------|-----------|----------|-------------|
| Code Reviewer | `code-reviewer.md` | 0 | 8 | 9 |
| Security Engineer | `security-engineer.md` | 2 | 3 | 4 |
| Architect | `architect.md` | 0 | 7 | 3 |
| Tech Lead | `tech-lead.md` | 2 | 8 | 7 |
| Backend Developer | `backend-developer.md` | 2 | 4 | 3 |
| Database Engineer | `database-engineer.md` | 2 | 8 | 4 |
| API Designer | `api-designer.md` | 3 | 14 | 6 |
| Test Engineer | `test-engineer.md` | 3 | 7 | 3 |
| Performance Engineer | `performance-engineer.md` | 2 | 9 | 4 |
| DevOps Engineer | `devops-engineer.md` | 2 | 10 | 4 |
| Debug Specialist | `debug-specialist.md` | 2 | 9 | 4 |
| Technical Writer | `technical-writer.md` | 3 | 5 | 2 |
| Project Manager | `project-manager.md` | 2 | 3 | 1 |
| Orchestrator | `orchestrator.md` | 2 | 8 | 6 |
