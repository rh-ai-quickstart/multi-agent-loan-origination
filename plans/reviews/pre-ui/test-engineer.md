# Test Engineer Review -- Pre-UI

**Reviewer:** Test Engineer
**Date:** 2026-03-02
**Scope:** `packages/api/tests/`, `scripts/live-tests.py`
**Total tests observed:** ~991 across 87 files

---

## Summary

The test suite is structurally sound. The three-tier architecture (unit / functional / integration) is well-executed, the `seed_data` fixture with savepoint rollback is solid, and critical paths like data-scope isolation, PII masking, and the audit hash chain all have real-SQL coverage. The findings below are real gaps and correctness issues -- not style preferences.

---

## Critical

### TE-01 -- `@pytest.mark.asyncio` decorators conflict with `asyncio_mode = "auto"`

**File:** 29 test files (sample: `tests/test_analytics.py:64`, `tests/test_decision.py:56`, `tests/test_compliance_check_tool.py:63`)

`pyproject.toml` sets `asyncio_mode = "auto"`, which means every `async def test_*` is automatically treated as an asyncio test. The 309 explicit `@pytest.mark.asyncio` decorators are redundant but also silently mask a correctness risk: if `asyncio_mode` is ever changed (e.g., to `strict`), the unmarked async tests in integration files would silently convert to synchronous functions and pass vacuously without awaiting anything. The integration conftest uses `pytest_asyncio.fixture` correctly, but the inconsistency makes the intent unclear.

**Risk to UI:** If an integration test passes vacuously (sync mode, no await), a real DB bug it was meant to catch goes undetected before the UI starts consuming those endpoints.

**Fix:** Either remove all 309 `@pytest.mark.asyncio` decorators (keep `auto` mode), or switch `asyncio_mode = "strict"` and keep decorators only on tests that explicitly need them. Consistency matters more than which option is chosen. Removing the decorators is lower risk and less churn.

---

### TE-02 -- `make_mock_session` returns the same `execute()` result for all queries; multi-query routes silently get wrong data

**File:** `tests/functional/mock_db.py:20-49`, exercised throughout `tests/functional/`

`make_mock_session(items=..., single=..., count=...)` wires a single `mock_result` to every `session.execute()` call. Routes that execute more than one query (e.g., list + count, or application lookup + condition query) all receive the same result object. The condition flow tests work around this with `_make_conditions_session` (uses `side_effect=[app_result, cond_result]`) -- but most functional tests that test multi-query routes use the simpler `make_mock_session`, meaning the second query silently gets the same result as the first.

**Concrete example:** `test_lo_sees_docs_for_assigned_app` in `test_lo_workflow_actions.py:21` calls `make_mock_session(items=docs, count=2)`. The document list endpoint runs an application-scope query first, then a documents query. Both `execute()` calls get the same `mock_result` -- the first query (application lookup) happens to succeed only because `unique().scalar_one_or_none()` is wired to `items[0]`, which is a Document object, not an Application. The test passes for the wrong reason.

**Fix:** `make_mock_session` should accept a `side_effects` list for sequential execute calls, or document clearly that it only works for single-query routes and flag multi-query routes. The `_make_conditions_session` pattern in `test_condition_flow.py:44-88` is the right approach and should be generalized.

---

### TE-03 -- No integration tests for the decisions route layer (RBAC, 403 enforcement)

**File:** `tests/test_decisions_route.py` (all tests), `tests/integration/test_decisions.py`

`test_decisions_route.py` patches `get_decisions` at the route level and tests only response shape. It never tests role enforcement. The integration test file (`test_decisions.py`) tests the service layer only -- no HTTP calls. There is no test that:

1. Verifies a borrower cannot GET `/api/applications/{id}/decisions` (should 403)
2. Verifies a LO cannot POST a decision (should 403)
3. Verifies only underwriters can call the decision render endpoint

These are security-critical paths that the UI will invoke directly. The existing `test_decisions_route.py` tests pass regardless of what roles are enforced because the mock completely bypasses auth.

**Fix:** Add functional tests (following `test_cross_persona_isolation.py` pattern) that exercise the decisions endpoints with AUTH_DISABLED=False and verify role gating returns 403 for non-underwriter roles.

---

## Warning

### TE-04 -- `_local_condition_mock` in `test_condition_flow.py` duplicates `make_mock_condition` from `factories.py`

**File:** `tests/functional/test_condition_flow.py:20-41`, `tests/factories.py:11-58`

`_mock_condition()` in `test_condition_flow.py` is a near-identical duplicate of `make_mock_condition()` in `factories.py`. Both create mock `Condition` ORM objects with the same fields. If the `Condition` schema adds a field (which the UI will surface), only one location gets updated and the other silently returns incomplete data.

**Fix:** Remove `_mock_condition` from `test_condition_flow.py` and import `make_mock_condition` from `tests.factories`. They have slightly different signatures but the same intent.

---

### TE-05 -- Integration tests for analytics use an inline `_seed_analytics_data` helper that bypasses `seed_data` isolation

**File:** `tests/integration/test_analytics.py:23-120`

`_seed_analytics_data` inserts rows into `applications`, `decisions`, and `conditions` directly via `db_session`, but `test_analytics.py` does NOT use the savepoint rollback provided by `db_session`. Each test class calls `await _seed_analytics_data(db_session)` at the start without cleanup. Because `db_session` uses savepoint rollback (the outer transaction is rolled back after each test), this is actually safe -- but only because the session fixture handles it. The issue is that counts from one test's seed rows accumulate within the same test function scope, and the `total_applications` assertion (`== 3`) will fail if the shared PostgreSQL container has leftover rows from a prior test that used `truncate_all` but didn't clean analytics-seeded rows.

**Concrete risk:** `TestPipelineSummaryIntegration.test_should_count_stages_from_real_data` asserts `result.total_applications == 3`. If any prior test in the same session (same container, different savepoint) committed rows that weren't rolled back, the count drifts. This is especially likely if tests are run in parallel or if `truncate_all` tests run before analytics tests.

**Fix:** The analytics seeding tests should assert `>= 3` and check for presence of specific stage values rather than exact totals, OR use `truncate_all` explicitly, OR add the seeded rows to `seed_data` so the baseline is known.

---

### TE-06 -- No test for the `confirm=true` decision path in `uw_render_decision` tool

**File:** `tests/test_decision_tools.py`

`test_decision_tools.py` tests the `proposed` phase (confirm=False) of `uw_render_decision` but there are no tests for the `confirm=True` path -- the path that actually persists the decision record. The mock for the compliance gate check (`comp_event.event_data = {"status": "PASS"}`) is present only in the proposal tests. The confirmed-decision path (which calls `render_decision`) is indirectly covered by `test_decision.py`, but `uw_render_decision` itself is never tested end-to-end with `confirmed=True`. The UI's decision confirmation flow maps directly to this path.

**Fix:** Add at least one `async def test_render_decision_confirmed_approve` test that exercises `uw_render_decision.ainvoke({"application_id": 100, "decision_type": "approve", ..., "confirmed": True, ...})` and verifies the tool calls `render_decision` (not `propose_decision`).

---

### TE-07 -- `test_analytics.py` unit tests use a fragile `_mock_execute_results` helper that orders results by call sequence, not semantics

**File:** `tests/test_analytics.py:27-52`

`_mock_execute_results` produces a list of mock results consumed in strict sequential order by `execute()` calls. If `get_pipeline_summary` ever reorders its queries, all unit tests silently return wrong data. For example, `test_should_calculate_pull_through_rate` provides `[(ApplicationStage.CLOSED, 8)], 20, 8, 30.0, (None,0)...` in a specific order. If `analytics.py` adds a new query between stage counts and initiated count, every mocked test produces wrong results but may still pass if assertions happen to match.

This is a structural weakness in mock-based analytics tests, not a bug today -- but it's exactly the kind of brittle test the integration tests in `test_integration/test_analytics.py` exist to complement. The gap is that the unit tests provide false confidence because they can pass with wrong data ordering.

**Fix:** Add an inline comment in each analytics unit test explaining which query position each mock result corresponds to, so divergence is immediately visible when the service changes.

---

### TE-08 -- `truncate_all` fixture in `integration/conftest.py` omits `conversations` table

**File:** `tests/integration/conftest.py:413-426`

`truncate_all` truncates: `hmda.demographics, hmda.loan_data, kb_chunks, kb_documents, document_extractions, documents, conditions, decisions, rate_locks, application_financials, application_borrowers, applications, borrowers, audit_events, audit_violations, demo_data_manifest`. It does NOT include any `conversations` or `checkpoints` table. If conversation checkpoints are stored in PostgreSQL (via `AsyncPostgresSaver`), seeding tests that trigger conversation endpoints will leave orphaned checkpoint rows that persist across tests using `truncate_all`.

**Fix:** Verify whether checkpoint tables exist in the schema (likely `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`) and add them to the `truncate_all` TRUNCATE if so.

---

### TE-09 -- Chat route authentication tests are unit-level only; no test exercises the full WS auth-to-message flow with a real role violation

**File:** `tests/test_borrower_chat.py`, `tests/test_lo_chat.py`, `tests/test_uw_chat.py`

Each chat module has tests for the `authenticate_websocket` function in isolation and for the REST history endpoint's role gate. But there is no test that:

1. Opens a WebSocket connection with a valid token for the wrong role
2. Verifies the server sends a `{"type": "error"}` frame before closing

`test_authenticate_websocket_rejects_wrong_role` tests the `authenticate_websocket` coroutine directly, not through `TestClient.websocket_connect()`. The chat handler may call `ws.close()` without first sending an error frame, or may do both in the wrong order. The UI will receive a WebSocket closure with no payload and have to guess why.

**Fix:** Add one WebSocket protocol test per authenticated chat endpoint (borrower, LO, UW) that uses `TestClient.websocket_connect` with AUTH_DISABLED=False and a mismatched-role token. Assert the server sends an error frame OR closes with the correct code (4003) before the connection drops.

---

### TE-10 -- `test_decisions_route.py` uses `"approve"` (lowercase) as `decision_type` but the enum value is `"approved"`

**File:** `tests/test_decisions_route.py:22`

The `_mock_decisions` fixture sets `"decision_type": "approve"` in the first mock decision. However, `DecisionType.APPROVED.value` is `"approved"` and the route's `response_model` is a Pydantic schema that validates this enum field. The test asserts `body["data"][0]["id"] == 1` but never asserts `body["data"][0]["decision_type"]`, so the inconsistency is invisible. When the UI reads `decision_type` from the API and expects `"approved"`, it would match the real API (which uses the correct enum) but not the mock. This is a documentation/confusion hazard that can mislead developers reading the test.

**Fix:** Correct the mock fixture to use `"approved"` (the actual enum value) and add an assertion on `decision_type` to make the contract explicit: `assert body["data"][0]["decision_type"] == "approved"`.

---

## Suggestion

### TE-11 -- Redundant `@pytest.mark.asyncio` decorators make test intent noisier

As noted in TE-01, `asyncio_mode = "auto"` is configured globally. The 309 `@pytest.mark.asyncio` decorators in unit and integration tests add noise without value. Removing them would make tests cleaner and make `asyncio_mode = "auto"` more legible.

**Not a bug today** -- just churn risk when the config is changed.

---

### TE-12 -- Missing edge case: `check_trid` with weekend-spanning LE delivery that still passes

**File:** `tests/test_compliance_checks.py` (TestCheckTrid)

The TRID LE delivery tests cover: on-time (Mon -> Wed = 2 days), late (Mon -> Mon+7 = 5 days), and missing. There is no test for a case where the delivery spans a weekend but still lands within the 3-business-day window (e.g., Thursday -> following Tuesday = 2 business days, PASS). Since `_business_days_between` has its own tests, this is low risk -- but the TRID integration between `check_trid` and `_business_days_between` for weekend-spanning passes is not explicitly covered.

---

### TE-13 -- `test_auth.py` is only 5 tests; the JWT decode path has minimal coverage

**File:** `tests/test_auth.py`

With 5 tests for the auth middleware, only basic paths are covered (e.g., `AUTH_DISABLED=True` bypass, missing header). There are no tests for:
- Expired JWT returns 401 with correct RFC 7807 body
- JWT with missing `realm_access.roles` claim
- JWT with valid structure but unknown role string

These are the failure modes the UI's login flow will encounter. Low priority for MVP, but worth noting as coverage debt before the UI auth integration.
