# Pre-Phase 3 Test Quality Review

**Reviewer:** Test Engineer
**Date:** 2026-02-26
**Scope:** All test files in packages/api/tests/ (unit, functional, integration) and packages/ui/src/ (frontend)
**Test count at review time:** 564 passing

---

## TEST-001: test_tool_auth.py tests replicate logic instead of testing actual code

**Severity:** Critical
**Location:** packages/api/tests/test_tool_auth.py:104-170

**Description:** Three async tests (test_tool_auth_node_allows_when_role_in_allowed, test_tool_auth_node_blocks_when_role_not_in_allowed, test_tool_auth_node_allows_when_no_roles_defined) manually replicate the authorization check logic inline rather than invoking the actual tool_auth node function from src/agents/base.py. These tests construct the same if/else logic that the production code uses, then assert on the result of their own copy. If the production logic changes, these tests will still pass because they test a snapshot of the logic, not the actual code path.

**Recommendation:** Extract the tool_auth node function from the compiled graph (or import it directly if refactored) and invoke it with test state objects. The tests should call the real function, not a reimplementation of it.

---

## TEST-002: test_tool_auth_logs_denial tests nothing

**Severity:** Critical
**Location:** packages/api/tests/test_tool_auth.py:174-193

**Description:** test_tool_auth_logs_denial patches src.agents.base.logger, then directly calls mock_logger.warning(...) with the expected arguments, then asserts that mock_logger.warning was called. This test verifies that MagicMock records calls -- it does not exercise any production code. The actual tool_auth denial logging is never invoked.

**Recommendation:** Delete this test and replace it with one that runs the actual tool_auth node with an unauthorized role, then asserts the logger was called. Alternatively, run a full graph invocation with a blocked tool call and verify the log output.

---

## TEST-003: test_public_assistant_config_extracts_allowed_roles tests reimplemented logic

**Severity:** Warning
**Location:** packages/api/tests/test_tool_auth.py:196-216

**Description:** This test constructs a config dict and manually iterates over it to build tool_allowed_roles, replicating the extraction logic from public_assistant.build_graph. It tests a copy of the logic, not the actual function.

**Recommendation:** Call the actual config extraction code from public_assistant or the shared utility, passing a test config and asserting on the output.

---

## TEST-004: Frontend has virtually no test coverage

**Severity:** Critical
**Location:** packages/ui/src/ (missing tests)

**Description:** The entire frontend package has only 1 test file (hero.test.tsx) with 2 trivial tests that check if text renders. There are no tests for routing, hooks, services, API integration, form interactions, state management, or any interactive behavior. While the CLAUDE.md notes the frontend may be replaced, the current implementation is the reference and has zero meaningful test coverage.

**Recommendation:** Given the frontend is explicitly noted as potentially replaceable, this is acknowledged as a known gap. If the frontend will ship with Phase 3, add at minimum: (1) smoke tests for each route rendering, (2) tests for any custom hooks wrapping TanStack Query, (3) tests for form validation logic if any exists client-side.

---

## TEST-005: No tests for src/services/storage.py (MinIO client)

**Severity:** Warning
**Location:** missing test for packages/api/src/services/storage.py

**Description:** The StorageService class (MinIO S3 operations: upload, download, delete, build_object_key) has no dedicated unit tests. It is exercised indirectly through integration tests (test_documents.py uploads to real MinIO), but error paths (connection failures, bucket not found, permission denied, download of non-existent key) are untested.

**Recommendation:** Add unit tests for StorageService with mocked boto3/aioboto3 client covering: upload success, upload failure, download success, download non-existent key, build_object_key format validation.

---

## TEST-006: No tests for src/services/scope.py (data scope SQL filter)

**Severity:** Warning
**Location:** missing test for packages/api/src/services/scope.py

**Description:** The data scope filter (apply_data_scope) is a security-critical function that modifies SQLAlchemy queries based on user role and ownership. While its behavior is exercised extensively through functional and integration tests that verify visibility outcomes, the function itself has no dedicated unit tests. Edge cases like malformed DataScope objects, null user_id, or unexpected role values are not directly tested.

**Recommendation:** Add unit tests for apply_data_scope with mock queries and various DataScope configurations to verify the correct WHERE clauses are generated. Focus on edge cases: empty user_id, unknown role, scope with conflicting flags.

---

## TEST-007: No tests for src/services/application.py

**Severity:** Warning
**Location:** missing test for packages/api/src/services/application.py

**Description:** The application service layer (create_application, get_application, list_applications, update_application) has no direct unit tests. These functions are tested indirectly through integration tests in test_application_crud.py, but error handling within the service (e.g., duplicate handling, constraint violations, concurrent updates) is not covered at the unit level.

**Recommendation:** Given that integration tests provide reasonable coverage of the service layer, this is lower priority. Consider adding unit tests for edge cases not covered by integration tests (e.g., concurrent update race conditions, handling of all ApplicationStage transitions).

---

## TEST-008: No tests for src/admin.py (SQLAdmin configuration)

**Severity:** Info
**Location:** missing test for packages/api/src/admin.py

**Description:** The SQLAdmin configuration (admin panel views) has no tests. This is an admin-only internal tool, so the blast radius is low.

**Recommendation:** Defer. SQLAdmin is a read-only dashboard for development. A smoke test that the admin app initializes without errors would be sufficient if prioritized.

---

## TEST-009: No tests for src/core/config.py (Settings)

**Severity:** Info
**Location:** missing test for packages/api/src/core/config.py

**Description:** The Settings class (Pydantic BaseSettings) has no dedicated tests verifying that environment variables map correctly to settings fields, that defaults are correct, or that validation works for misconfigured environments.

**Recommendation:** Add a test that instantiates Settings with a controlled environment and verifies critical defaults (AUTH_DISABLED, DATABASE_URL parsing, MINIO settings). Low priority since the settings are implicitly tested by every test that uses them.

---

## TEST-010: No tests for src/inference/client.py (LLM client wrapper)

**Severity:** Warning
**Location:** missing test for packages/api/src/inference/client.py

**Description:** The LLM client wrapper (get_completion, get_model_for_tier) has no direct tests. It is mocked everywhere it is used. There are no tests verifying: model tier selection logic, retry behavior, timeout handling, or response parsing.

**Recommendation:** Add unit tests with mocked HTTP client verifying: correct model selection per tier, retry on transient failures, timeout enforcement, handling of malformed LLM responses.

---

## TEST-011: No tests for src/services/extraction_prompts.py

**Severity:** Info
**Location:** missing test for packages/api/src/services/extraction_prompts.py

**Description:** The extraction prompt templates have no tests. These are static string formatters, so the risk is low. The extraction pipeline tests indirectly validate the output format expectations.

**Recommendation:** Defer. If prompt templates become dynamic or parameterized in Phase 3+, add tests then.

---

## TEST-012: No direct tests for src/agents/borrower_assistant.py build_graph

**Severity:** Warning
**Location:** missing test for packages/api/src/agents/borrower_assistant.py

**Description:** The borrower_assistant.build_graph function is tested indirectly via test_borrower_chat.py (which verifies the graph compiles and nodes exist), but there are no tests that invoke the graph with realistic inputs and verify the routing logic, tool selection, or state transitions. The public assistant has similar gaps.

**Recommendation:** Add at least one smoke test that invokes borrower_assistant.build_graph and runs a simple message through it with mocked LLMs, verifying the graph routes through expected nodes.

---

## TEST-013: No tests for src/routes/chat.py WebSocket handler

**Severity:** Warning
**Location:** missing test for packages/api/src/routes/chat.py

**Description:** The prospect chat WebSocket handler (chat.py) has no tests. The borrower_chat.py route has some WebSocket tests in test_borrower_chat.py, but the public prospect chat route is untested. WebSocket error paths (invalid JSON, connection drops, agent errors during streaming) are not tested for either handler.

**Recommendation:** Add WebSocket tests using httpx's AsyncClient websocket support for the prospect chat route. Cover: successful connection, invalid message format, agent error during processing, connection timeout.

---

## TEST-014: test_models.py has only 1 trivial test

**Severity:** Warning
**Location:** packages/api/tests/test_models.py

**Description:** test_models.py contains a single test (test_application_relationships_exist) that checks whether relationship attribute names exist on the Application model. It does not test relationship loading, cascade behavior, or model validation. The integration tests in test_migrations.py provide much better coverage of model constraints and cascades.

**Recommendation:** Either remove test_models.py (the integration tests cover models thoroughly) or expand it with meaningful tests for model methods/properties if any exist.

---

## TEST-015: Flaky test risk from time.sleep in test_model_routing.py

**Severity:** Warning
**Location:** packages/api/tests/test_model_routing.py (hot-reload tests)

**Description:** The hot-reload tests in test_model_routing.py use time.sleep(0.05) to ensure file modification time changes are detectable. On slow CI systems or filesystems with 1-second mtime granularity (e.g., some NFS mounts, HFS+), 50ms may not produce a detectable mtime change, causing intermittent failures.

**Recommendation:** Instead of time.sleep, directly manipulate the cached mtime/hash to simulate staleness, or use os.utime to explicitly set a future mtime. This makes the test deterministic regardless of filesystem granularity.

---

## TEST-016: Functional tests use MagicMock ORM objects that bypass schema validation

**Severity:** Warning
**Location:** packages/api/tests/functional/data_factory.py

**Description:** The data_factory.py creates MagicMock objects that mimic ORM models (make_app_sarah_1, make_borrower_sarah, etc.). These mocks return hardcoded values from attributes but do not validate against actual SQLAlchemy model definitions or Pydantic response schemas. If a model field is renamed or its type changes, the mocks will continue to return the old field names/values, and the functional tests will pass while production code fails.

**Recommendation:** Consider using actual ORM model constructors (without a database) for data factories where possible (SQLAlchemy models can be instantiated without a session). Where mocks are necessary, add a validation step or cross-reference test that verifies mock attribute names match the actual model's column names.

---

## TEST-017: Functional test mock sessions have fragile side_effect chains

**Severity:** Warning
**Location:** packages/api/tests/functional/test_completeness_flow.py:22-38, test_status_flow.py:20-48, test_condition_flow.py:40-84

**Description:** Multiple functional test files build mock sessions with ordered side_effect lists (e.g., [app_result, doc_result, app_result_2, count_result]). These depend on the exact number and order of session.execute calls in the production code. If the service adds a query (e.g., a cache check or a logging query), all side_effect chains break silently (IndexError or wrong result returned to wrong query).

**Recommendation:** This is inherent to the mock-based functional test approach. The integration tests provide the safety net here. Document this fragility in the functional test README or conftest, and ensure any service layer change is always validated against integration tests, not just functional tests.

---

## TEST-018: Missing async markers on some async test functions

**Severity:** Warning
**Location:** packages/api/tests/test_completeness.py, packages/api/tests/test_freshness.py

**Description:** Several unit test files have async test functions decorated with @patch but may be missing explicit @pytest.mark.asyncio markers. The tests use pytest-asyncio which may auto-detect async functions depending on configuration, but relying on auto-detection is fragile if the pytest-asyncio mode changes.

**Recommendation:** Verify pytest-asyncio mode is set to "auto" in pyproject.toml. If not, add explicit @pytest.mark.asyncio markers to all async test functions. Using a pytestmark = pytest.mark.asyncio at module level is the cleanest approach for files that are entirely async.

---

## TEST-019: No tests for conversation service initialization flow

**Severity:** Warning
**Location:** packages/api/src/services/conversation.py

**Description:** The ConversationService has tests for get_conversation_history and thread ownership (test_conversation.py, test_conversation_persistence.py), but the initialization flow (connecting to PostgreSQL for checkpointing, handling connection failures, lazy initialization) is not tested. The test_conversation_persistence.py uses MemorySaver instead of AsyncPostgresSaver, so the actual production initialization path is untested.

**Recommendation:** Add a unit test that verifies ConversationService.initialize() handles connection failures gracefully (returns False or logs error without crashing).

---

## TEST-020: No tests for disclosure acknowledgment integration path

**Severity:** Info
**Location:** packages/api/tests/integration/ (missing)

**Description:** Disclosure acknowledgment has unit tests (test_disclosure.py with 5 tests) but no integration test against real PostgreSQL. The unit tests use mock sessions. The audit event creation during disclosure acknowledgment is not verified end-to-end.

**Recommendation:** Add an integration test that calls the disclosure endpoint and verifies both the disclosure record and the corresponding audit event are created with correct data.

---

## TEST-021: No tests for rate lock integration path

**Severity:** Info
**Location:** packages/api/tests/integration/ (missing)

**Description:** Rate lock has unit tests (test_rate_lock.py with 10 tests) but no integration test. The lock/unlock/status transitions and concurrent locking behavior are not tested against real PostgreSQL constraints.

**Recommendation:** Add integration tests for rate lock lifecycle: create lock, check status, attempt concurrent lock on same application, expire behavior.

---

## TEST-022: Duplicate _post_upload helper in two functional test files

**Severity:** Info
**Location:** packages/api/tests/functional/test_extraction_flow.py:21-28, packages/api/tests/functional/test_document_upload_flow.py:24-31

**Description:** The _post_upload helper function is duplicated identically in two functional test files. If the upload endpoint contract changes (e.g., new required field), both must be updated independently.

**Recommendation:** Move _post_upload to a shared test helper module (e.g., tests/functional/helpers.py) and import it in both files.

---

## TEST-023: Integration test client cleanup relies on manual aclose()

**Severity:** Warning
**Location:** packages/api/tests/integration/ (all files using client_factory)

**Description:** Every integration test that uses client_factory calls await client.aclose() at the end. If a test fails before reaching the aclose() call, the async client is not closed, potentially leaking resources. In a large test suite, this could cause connection pool exhaustion under failure scenarios.

**Recommendation:** Make client_factory return a context manager or use a fixture that auto-closes. Alternatively, wrap test bodies in try/finally to ensure cleanup. Example:
```python
async with await client_factory(persona) as client:
    resp = await client.get(...)
```

---

## TEST-024: No negative test for audit hash chain with TRUNCATE bypass

**Severity:** Info
**Location:** packages/api/tests/integration/test_audit_trigger.py

**Description:** The append-only trigger tests verify INSERT allowed, UPDATE blocked, and DELETE blocked. However, the audit_cleanup fixture uses TRUNCATE (which bypasses row-level triggers). There is no test or documentation noting that TRUNCATE is a known bypass of the append-only guarantee. In production, TRUNCATE permission should be restricted.

**Recommendation:** Add a comment in test_audit_trigger.py documenting that TRUNCATE bypasses the append-only trigger by design (PostgreSQL behavior). Consider adding a test or documentation note that production deployments should revoke TRUNCATE permission on audit_events.

---

## TEST-025: No tests for main.py startup/lifespan events

**Severity:** Warning
**Location:** missing test for packages/api/src/main.py

**Description:** The FastAPI application startup (lifespan events, middleware registration, router inclusion, CORS configuration) has no tests. If a router import fails or middleware is misconfigured, this would only be caught by running the server. The health tests exercise the running app but do not verify startup behavior (e.g., that all expected routers are registered).

**Recommendation:** Add a smoke test that imports the FastAPI app, verifies the expected number of routes are registered, and checks that key middleware (auth, CORS) is present.

---

## TEST-026: No error path tests for extraction pipeline LLM failures

**Severity:** Warning
**Location:** packages/api/tests/integration/test_extraction_pipeline.py

**Description:** The integration extraction tests cover: text extraction, row creation, status update, HMDA routing, bad JSON handling, and vision fallback. However, they do not test: LLM timeout/connection error, LLM returning valid JSON with unexpected schema, extraction with 0 fields returned, partial HMDA data (e.g., race present but ethnicity missing).

**Recommendation:** Add integration tests for: (1) LLM raises ConnectionError -> document status = PROCESSING_FAILED, (2) LLM returns valid JSON with empty extractions list, (3) partial HMDA fields routed correctly.

---

## TEST-027: Functional tests require monkeypatch for AUTH_DISABLED on every denial test

**Severity:** Info
**Location:** packages/api/tests/functional/ (multiple files)

**Description:** Every test that verifies 403 denial must include a monkeypatch block setting AUTH_DISABLED=False. This pattern is repeated 20+ times across functional tests. If a developer forgets this monkeypatch, the test will pass (200) even though the denial logic is broken, because AUTH_DISABLED=True bypasses auth entirely.

**Recommendation:** Consider adding a functional test conftest fixture that sets AUTH_DISABLED=False by default, with an explicit marker or fixture to opt-in to the disabled state when needed. This inverts the default so auth-bypass tests are explicit rather than auth-enforcement tests.

---

## TEST-028: No WebSocket reconnection or error recovery tests

**Severity:** Warning
**Location:** packages/api/tests/ (missing)

**Description:** WebSocket tests (test_borrower_chat.py) verify connection establishment and basic message exchange, but do not test: reconnection after server-side error, handling of malformed incoming messages, behavior when the LLM agent raises an exception mid-stream, connection timeout enforcement, or concurrent WebSocket connections from the same user.

**Recommendation:** Add WebSocket tests for: (1) server sends error frame on agent exception, (2) client sends invalid JSON -> server responds with error, (3) connection dropped mid-response -> no server crash.

---

## TEST-029: No tests for routes/_chat_handler.py shared handler

**Severity:** Warning
**Location:** missing test for packages/api/src/routes/_chat_handler.py

**Description:** The shared chat handler module (_chat_handler.py) that is imported by both chat.py and borrower_chat.py has no direct tests. Its error handling, message parsing, and response formatting logic are only tested indirectly through the WebSocket tests (which have limited coverage themselves per TEST-028).

**Recommendation:** Add unit tests for the chat handler's message parsing, response formatting, and error handling functions in isolation.

---

## TEST-030: Integration test seeding runs full seed_demo_data repeatedly

**Severity:** Info
**Location:** packages/api/tests/integration/test_seeding.py

**Description:** Each test in test_seeding.py calls seed_demo_data(force=True), creating 7 borrowers, 28 applications, and HMDA data from scratch. Combined with the truncate_all fixture, this is expensive. The 5 tests in this file likely account for a significant portion of integration test runtime.

**Recommendation:** Consider using a module-scoped seed fixture that seeds once and shares across tests in the file, with individual tests being read-only where possible.
