# Test Quality Review -- Pre-Phase 5

**Reviewer:** test-engineer
**Date:** 2026-02-27
**Scope:** All test files (`packages/api/tests/`)
**Test count:** ~850 test functions across 76 test files

---

## Findings

### Coverage Gaps

### [TE-01] Severity: Warning
**File(s):** `packages/api/src/routes/_chat_handler.py`
**Finding:** The `_chat_handler.py` module (256 lines) contains `authenticate_websocket()` and `run_agent_stream()` -- two of the most critical shared functions in the application. `authenticate_websocket` handles JWT validation, role-based WebSocket authorization, and the `AUTH_DISABLED` dev bypass. `run_agent_stream` handles the entire WebSocket streaming loop including JSON parsing, agent invocation, safety shield event processing, tool auth denied events, and audit writing. While tests in `test_borrower_chat.py`, `test_lo_chat.py`, and `test_uw_chat.py` touch the chat endpoints at the route level, neither `authenticate_websocket` nor `run_agent_stream` has direct unit tests exercising their individual code paths (expired token, no token on authenticated endpoint, role mismatch, invalid JSON, safety_blocked event, tool_auth denied event, output_shield override, agent exception handling, disconnection).
**Recommendation:** Add a dedicated `test_chat_handler.py` with unit tests for `authenticate_websocket` covering: valid token, expired token, missing token on required-role endpoint, wrong role, AUTH_DISABLED bypass. For `run_agent_stream`, test: invalid JSON input, missing content field, safety_blocked path, tool_auth_denied path, output_shield override, agent exception fallback, and client disconnect.

### [TE-02] Severity: Warning
**File(s):** `packages/api/src/services/scope.py`
**Finding:** The `apply_data_scope()` function is the central RBAC query filter used by every service method that touches the database. It implements three distinct code paths: `own_data_only` (borrower), `assigned_to` (loan officer), and pass-through (admin/underwriter). No test file directly tests this function. Coverage is only incidental through functional and integration tests that happen to exercise different personas. If the scope filtering logic has a subtle bug (e.g., missing join when `join_to_application` is None vs not-None), the gap would not be caught by focused testing.
**Recommendation:** Add `test_scope.py` with unit tests for `apply_data_scope()` covering: (1) own_data_only with and without `join_to_application`, (2) assigned_to with and without `join_to_application`, (3) full_pipeline (no filters applied), (4) edge case where `scope.user_id` is None with `own_data_only=True`.

### [TE-03] Severity: Warning
**File(s):** `packages/api/src/services/extraction_prompts.py`
**Finding:** The prompt templates (`build_extraction_prompt`, `build_image_extraction_prompt`) and the `HMDA_DEMOGRAPHIC_KEYWORDS` set are untested. These are pure functions/constants that define the extraction pipeline's behavior. A change to `EXTRACTION_FIELDS` or `HMDA_DEMOGRAPHIC_KEYWORDS` could silently break extraction or HMDA isolation with no test failure. The `build_extraction_prompt` function constructs multi-part messages including quality flags and HMDA demographic instructions -- behavior that should be verified.
**Recommendation:** Add `test_extraction_prompts.py` testing: (1) `build_extraction_prompt` returns correct field list per doc type, (2) unknown doc type falls back to "any relevant fields", (3) HMDA demographic extraction instruction is present, (4) `build_image_extraction_prompt` produces valid system message, (5) `HMDA_DEMOGRAPHIC_KEYWORDS` contains all expected keywords.

### [TE-04] Severity: Warning
**File(s):** `packages/api/src/agents/registry.py`
**Finding:** The agent registry has significant logic: config loading, mtime-based cache invalidation, error-resilient reload (keeps last valid graph on YAML error), `_build_graph` dispatch to agent modules, and `list_agents`. The only test coverage is a few references in `test_chat.py` and `test_borrower_chat.py` that use `get_agent` as part of larger chat tests. The cache invalidation logic, the error recovery path (bad YAML with cached graph), and the `clear_agent_cache` / `list_agents` utilities are untested.
**Recommendation:** Add `test_registry.py` testing: (1) `load_agent_config` with valid YAML, (2) `load_agent_config` with missing file raises `FileNotFoundError`, (3) `get_agent` caches and returns same graph on second call, (4) `get_agent` rebuilds when mtime changes, (5) `get_agent` keeps cached graph on YAML error, (6) `clear_agent_cache` empties the cache, (7) `list_agents` returns agent names.

### [TE-05] Severity: Suggestion
**File(s):** `packages/api/src/services/storage.py`
**Finding:** `StorageService` has no direct unit tests. The `build_object_key` static method includes path traversal prevention (`os.path.basename`) which is security-relevant. Integration tests exercise storage via testcontainers MinIO, but the unit-level path traversal guard, the `get_download_url` presigned URL generation, and the `download_file` method are not tested in isolation.
**Recommendation:** Add tests for `StorageService.build_object_key` covering: normal filename, path traversal attempt (`../../etc/passwd`), empty filename fallback, and filename with leading slashes.

### [TE-06] Severity: Warning
**File(s):** `packages/api/src/agents/base.py`
**Finding:** The `build_routed_graph` function in `base.py` (342 lines) is the core of the agent architecture. It implements: input/output safety shields, rule-based classification routing, fast model confidence escalation, tool authorization (RBAC Layer 3), and the tool loop. While `test_safety.py` tests `_low_confidence` and the safety checker, and `test_tool_auth.py` tests tool authorization, the graph construction itself (`build_routed_graph` and `build_agent_graph`) is untested. There are no tests verifying the graph topology: that input_shield routes to classify, that classify routes to the correct agent tier, that agent_fast escalates to agent_capable on low confidence, or that tool_auth blocks unauthorized tools when `tool_allowed_roles` is provided. These are the most critical routing decisions in the system.
**Recommendation:** Add `test_agent_graph.py` with tests that build a graph via `build_routed_graph` with mock LLMs and verify: (1) input_shield blocks unsafe input, (2) classify routes SIMPLE queries to agent_fast, (3) agent_fast escalates to agent_capable on low confidence, (4) tool_auth blocks unauthorized tool calls, (5) output_shield replaces unsafe output. Use in-memory mocks for LLMs, not real API calls.

### Test Quality

### [TE-07] Severity: Warning
**File(s):** `packages/api/tests/test_decision.py:146-322`
**Finding:** The `render_decision` tests use `fake_refresh` callbacks that set the mock object's fields to the expected output values. This means the test is telling the mock what to return and then asserting those same values. For example, `test_render_decision_approve_no_conditions` sets `obj.decision_type = DecisionType.APPROVED` in `fake_refresh`, then asserts `result["decision_type"] == "approved"`. The test never verifies that `render_decision` actually sets `decision_type` to APPROVED based on its logic -- it only verifies the serialization of whatever the mock returns. If the service had a bug where it set `decision_type = DENIED` on an approve action, the mock would override that with `APPROVED` during refresh, and the test would still pass.
**Recommendation:** Restructure `render_decision` tests to verify the arguments passed to `session.add()` or capture the object added to the session before `fake_refresh` overrides its fields. Alternatively, test the pre-commit state of the Decision object to ensure the service sets the correct `decision_type` before the DB round-trip.

### [TE-08] Severity: Warning
**File(s):** `packages/api/tests/test_decision_tools.py:69-111`, `packages/api/tests/test_decision_tools.py:156-196`
**Finding:** Similar to TE-07, the decision tool tests mock `propose_decision` and `render_decision` at the service boundary and then assert on string patterns in the formatted output. For example, `test_render_decision_propose_approve` provides a canned dict from `mock_propose` and then checks `"PROPOSED DECISION" in result` and `"Approved" in result`. This verifies string formatting but not the tool's input validation, parameter forwarding, or error handling logic. A bug in how the tool constructs `UserContext`, passes `denial_reasons`, or handles the `confirmed` flag would not be caught because the service call is fully mocked.
**Recommendation:** For at least the `confirmed=True` path, verify that `render_decision` was called with the correct parameters (check `mock_render.call_args` for `decision`, `rationale`, `denial_reasons`, `override_rationale`). Currently only `mock_propose.assert_awaited_once()` and `mock_render.assert_awaited_once()` are checked, but argument correctness is not verified.

### [TE-09] Severity: Suggestion
**File(s):** `packages/api/tests/test_public.py:5-8`
**Finding:** `test_products_endpoint` asserts only `status_code == 200` and `len(response.json()) > 0`. It does not validate the response structure (field names, types) or verify that the expected product IDs/names are present. If a code change accidentally removed a required field from the product schema or dropped a product from the list, this test would still pass.
**Recommendation:** Extend the assertion to check at least one product's structure: `data[0]` has `id`, `name`, `description`, `min_down_payment_pct`, `typical_rate` fields, and the count matches the expected number of products.

### [TE-10] Severity: Suggestion
**File(s):** `packages/api/tests/test_models.py`
**Finding:** `test_application_relationships` is the only model test. It verifies that ORM relationship names exist on `Application` but does not test any other models (Borrower, Document, Condition, Decision, AuditEvent, KBDocument, KBChunk, ApplicationFinancials). More importantly, it tests relationship naming, not behavior -- a renamed relationship would break callers but not this test (since it checks a set of expected names).
**Recommendation:** This is low-priority at MVP maturity. If model tests are desired, focus on testing model constraints (nullable fields, enum conversions) and computed properties rather than relationship wiring.

### Fixture Patterns

### [TE-11] Severity: Warning
**File(s):** `packages/api/tests/test_condition.py:36-57`, `packages/api/tests/test_condition.py:724-761`, `packages/api/tests/test_decision.py:24-78`
**Finding:** Mock helper functions are duplicated across test files with slight variations. `_mock_condition` (line 36) and `_mock_condition_obj` (line 734) in `test_condition.py` are two different mock constructors for the same entity, defined in the same file, with different return types (MagicMock with `.value` attribute vs MagicMock with real enum). `_uw_user()` is defined independently in both `test_condition.py` (line 764) and `test_decision.py` (line 38). `_mock_app()` is defined in `test_condition.py` (line 724), `test_decision.py` (line 24), and `test_decision_tools.py` (line 23) with different signatures. This duplication means changes to the mock contract (e.g., adding a new required field) must be updated in multiple places.
**Recommendation:** Consolidate shared mock factories into `tests/helpers.py` or a new `tests/factories.py`. At minimum, merge the two condition mock constructors in `test_condition.py` into one, and share `_uw_user()` and `_mock_app()` across the underwriter test files.

### [TE-12] Severity: Suggestion
**File(s):** `packages/api/tests/conftest.py`
**Finding:** The root `conftest.py` is minimal (14 lines) with only `client` and `health_response` fixtures. This is fine for organization, but the `health_response` fixture asserts `status_code == 200` as a side effect, which means a health endpoint failure would cause confusing cascading failures in any test that uses this fixture. The assertion belongs in a test, not a fixture.
**Recommendation:** Remove the `assert response.status_code == 200` from the `health_response` fixture and let the health endpoint tests handle that assertion directly. If the fixture is meant to fail fast when the app is broken, use `pytest.fail()` with a descriptive message instead of a bare assert.

### Test Isolation

### [TE-13] Severity: Suggestion
**File(s):** `packages/api/tests/integration/conftest.py:105-145`
**Finding:** The `_patch_db_module` fixture modifies module-level globals (`db.database.engine`, `db.database.SessionLocal`, etc.) and patches already-imported references in `src.services.extraction`, `src.services.compliance.hmda`, and `src.seed`. This is session-scoped and applied globally via `autouse=True`. While this is necessary for integration test infrastructure, it means the integration test module permanently mutates global state for the entire test session. If unit tests and integration tests run in the same pytest invocation and the integration conftest loads first, the monkey-patching could affect unit tests that import the same modules.
**Recommendation:** Verify that `pytest.ini` or `pyproject.toml` uses markers or directory-based selection to ensure integration tests only run when explicitly requested (e.g., `-m integration`). The current `pytestmark = pytest.mark.integration` marker is present, but its enforcement depends on the test runner configuration. Document the isolation requirement.

### Test Organization

### [TE-14] Severity: Warning
**File(s):** `packages/api/tests/test_condition.py` (1317 lines)
**Finding:** `test_condition.py` is the largest test file at 1317 lines and 50 test functions. It covers: condition schema validation, `get_conditions` service, `respond_to_condition` service, `check_condition_documents` service, `link_document_to_condition` service, borrower agent tools (`list_conditions`, `respond_to_condition_tool`, `check_condition_satisfaction`), `issue_condition` service, all underwriter lifecycle operations (`review_condition`, `clear_condition`, `waive_condition`, `return_condition`), and `get_condition_summary`. This file mixes borrower-side and underwriter-side concerns, schema tests and service tests, and it defines two separate sets of mock helpers (`_mock_condition` at line 36, `_mock_condition_obj` at line 734, `_mock_app` at line 724, `_uw_user` at line 764).
**Recommendation:** Split into: (1) `test_condition_schemas.py` for the 3 schema tests, (2) `test_condition_borrower.py` for borrower-facing service functions and tools, (3) `test_condition_underwriter.py` for underwriter lifecycle operations and summary. This keeps each file focused on a single concern and under 500 lines.

### Specific Feature Area Analysis

### [TE-15] Severity: Suggestion
**File(s):** `packages/api/tests/test_decision.py`
**Finding:** The AI comparison logic in the decision service is thoroughly tested. `test_render_decision_ai_agreement` verifies agreement when UW and AI both approve. `test_render_decision_ai_override` verifies disagreement and checks the override audit event with `high_risk=True`. The `_ai_category` mapping is tested for all variants including None and unknown strings. The `propose_decision` preview path is tested for non-persistence (verifying `session.add.assert_not_called()` and `session.commit.assert_not_awaited()`). The one gap is testing the `_get_ai_recommendation` function when there are multiple audit events and only the most recent with the matching tool name should be returned -- the current test only covers the single-event and no-event cases.
**Recommendation:** Add a test for `_get_ai_recommendation` with multiple audit events where only one has `tool == "uw_preliminary_recommendation"`, and verify the correct event is selected.

### [TE-16] Severity: Suggestion
**File(s):** `packages/api/tests/test_condition.py`
**Finding:** The condition lifecycle tests cover the full state machine: OPEN -> RESPONDED -> UNDER_REVIEW -> CLEARED, OPEN -> RESPONDED -> UNDER_REVIEW -> returned to OPEN (with iteration increment), and OPEN -> WAIVED (with severity restriction). However, there is no test for attempting to clear a WAIVED condition (already-terminal) or attempting to review a CLEARED condition. While `test_waive_condition_blocked_terminal` covers the waive-a-cleared path, the reverse (clear-a-waived) and other invalid terminal state transitions are not verified.
**Recommendation:** Add tests for `clear_condition` on a WAIVED condition and `review_condition` on a CLEARED condition to fully exercise terminal state guards. Low priority -- the existing tests cover the main paths.

### [TE-17] Severity: Suggestion
**File(s):** `packages/api/tests/test_compliance_checks.py`
**Finding:** The compliance check pure functions are the best-tested area of the codebase. `TestCheckAtrQm` has 11 tests covering all DTI tiers, boundary conditions at 0.43 and 0.50, missing documents (income, asset, employment individually), combined elevated DTI with missing docs, and the null DTI case. `TestCheckTrid` tests LE and CD timing with exact business-day boundary tests. `TestBusinessDaysBetween` tests weekday spans, weekend crossings, same-day, full-week, and reverse-date edge cases. These are exemplary pure function tests.
**Recommendation:** None -- this is the quality benchmark other test files should target.

### [TE-18] Severity: Warning
**File(s):** `packages/api/tests/test_compliance_check_tool.py`
**Finding:** The compliance check tool tests use deeply nested `with` blocks for patching (4-6 patches per test). Each test class (`TestComplianceCheckEcoa`, `TestComplianceCheckAtrQm`, etc.) repeats the same mock setup: `mock_app`, `state`, `patch get_application`, `patch list_documents`, `patch write_audit_event`, `patch SessionLocal`, `_mock_session_with_fins`. This boilerplate makes the tests hard to read and maintain. The actual assertion logic is often just 3-4 lines buried under 20+ lines of setup.
**Recommendation:** Extract the common mock setup into a pytest fixture or a context manager factory that handles the 4-6 patches, accepting only the variable parts (app stage, financials, docs, regulation_type) as parameters. This would reduce each test to ~10 lines of meaningful code.

### [TE-19] Severity: Warning
**File(s):** `packages/api/tests/test_uw_tools.py`
**Finding:** Same pattern as TE-18. The underwriter tool tests (`uw_risk_assessment`, `uw_preliminary_recommendation`) each require 4-5 `patch()` calls with identical SessionLocal mock setup. The `TestUwPreliminaryRecommendation` class has 8 tests, each with ~35 lines of mock setup and only ~5 lines of assertions. The test for `test_recommends_approve` is 50 lines long; without the boilerplate, the meaningful test logic would be ~8 lines.
**Recommendation:** Create a shared helper or fixture that sets up the common mock context (session, app, borrower, documents, financials) and returns a callable that runs the tool invocation. Tests would then only specify the variable inputs (income, debts, credit, employment_status, loan_amount, property_value, doc_count) and expected output patterns.

### [TE-20] Severity: Warning
**File(s):** `packages/api/tests/test_kb_search.py`, `packages/api/tests/test_kb_conflict.py`, `packages/api/tests/test_kb_tool.py`, `packages/api/tests/test_kb_ingestion.py`
**Finding:** The KB feature has solid test coverage across 4 files: vector search with tier boosting (5 tests), conflict detection heuristics (6 tests), the kb_search tool (5 tests), and the ingestion pipeline (7 tests including frontmatter parsing, markdown chunking, and full pipeline). The `_make_result` helper is duplicated between `test_kb_conflict.py` and `test_kb_tool.py` with slightly different default parameter values.
**Recommendation:** Deduplicate `_make_result` into a shared helper. The conflict detection tests could also benefit from a test for multiple simultaneous conflict types (e.g., a result set that triggers both `numeric_threshold` and `same_tier`).

### [TE-21] Severity: Warning
**File(s):** `packages/api/src/middleware/pii.py`
**Finding:** PII masking middleware is tested in integration (`tests/integration/test_pii_masking.py`, 5 tests) but has no unit tests for the middleware class itself. The PII masking logic transforms response bodies by replacing sensitive fields -- if the middleware's regex or field detection has a bug (e.g., it masks non-PII fields or fails to mask PII in nested JSON structures), the integration test may miss it because it only tests through specific endpoints.
**Recommendation:** Add unit tests for the PII masking function directly, testing: SSN masking, email masking, DOB masking, partial masking (last-4 for SSN), and nested JSON object traversal.

### [TE-22] Severity: Suggestion
**File(s):** `packages/api/tests/functional/conftest.py:55-97`
**Finding:** The `make_upload_client` fixture uses a list-based patcher cleanup pattern that is fragile -- if the test raises before all patchers are started, the `yield` block may try to stop patchers that were never started (though the current implementation avoids this by starting all patchers before yield). However, the fixture also attaches internal state to the TestClient via private attributes (`client._mock_storage`, `client._mock_extraction_svc`, `client._mock_create_task`), which is an unusual pattern that couples the fixture to the client implementation.
**Recommendation:** Return the mocks as a separate named tuple alongside the client rather than monkey-patching attributes onto the TestClient. This is minor -- the current pattern works.

### [TE-23] Severity: Suggestion
**File(s):** `packages/api/tests/integration/conftest.py:182-204`
**Finding:** The integration test infrastructure is well-architected: session-scoped testcontainers for PostgreSQL (pgvector) and MinIO, real Alembic migrations, function-scoped sessions with savepoint rollback for isolation, and proper dependency override cleanup. The `truncate_all` fixture at line 412 provides an alternative cleanup strategy for tests where services create their own sessions (bypassing the savepoint). This is a thoughtful design that correctly handles the two main patterns of DB access (injected session vs. service-created session).
**Recommendation:** None -- this is well-designed test infrastructure.

### [TE-24] Severity: Warning
**File(s):** `packages/api/src/services/disclosure.py`
**Finding:** The disclosure service has tests in `test_disclosure.py` (8 tests), but examining the test file listing, only happy paths and not-found cases appear to be covered based on the test count. The disclosure acknowledgment is a compliance-sensitive feature (borrowers acknowledge receipt of disclosures) that should verify: duplicate acknowledgment handling, acknowledgment by wrong user, acknowledgment of non-existent disclosure, and timestamp recording.
**Recommendation:** Verify that edge cases for disclosure acknowledgment are covered. If not, add tests for: duplicate acknowledgment (idempotency), wrong user attempting to acknowledge, and verifying the audit event data for acknowledgment.

### [TE-25] Severity: Warning
**File(s):** `packages/api/src/agents/borrower_assistant.py`, `packages/api/src/agents/loan_officer_assistant.py`, `packages/api/src/agents/underwriter_assistant.py`, `packages/api/src/agents/public_assistant.py`
**Finding:** The four agent assistant modules (which define `build_graph()` functions that wire tools to the LangGraph graph) have no direct unit tests verifying that the correct tools are registered for each agent. A misconfiguration (wrong tool list, missing tool, or wrong `allowed_roles` mapping) would only be caught during live testing. For example, if `loan_officer_assistant.py` accidentally included an underwriter tool, or if `underwriter_assistant.py` was missing the compliance_check tool, no automated test would catch it.
**Recommendation:** Add a test per agent module that calls `build_graph()` with a mock config and verifies the tool list contains exactly the expected tools. This is a lightweight smoke test that prevents tool misregistration.
