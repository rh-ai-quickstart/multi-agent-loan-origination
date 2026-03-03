# Architecture Review -- Pre-Phase 5

**Reviewer:** architect
**Date:** 2026-02-27
**Scope:** Full codebase (`packages/api/src/`, `packages/db/`, `compose.yml`, Helm charts)
**Test status:** 739 tests passing on main

---

## Findings

### [AR-01] Severity: Warning
**Component(s):** `agents/decision_tools.py`, `agents/underwriter_tools.py`, `agents/compliance_check_tool.py`
**Finding:** Agent tool modules bypass the service layer and execute raw SQLAlchemy queries directly against DB models. Six instances identified:

1. `decision_tools.py` lines 18-23, 55-65, 279-322, 311-322, 431-442, 586-597 -- imports `ApplicationBorrower`, `AuditEvent`, `Borrower`, `Decision` from `db` and runs `select()` queries directly for adverse action notice generation, LE/CD generation, and the compliance gate.
2. `underwriter_tools.py` lines 148-155, 471-478, 631-638 -- inline `from db import ApplicationFinancials` + raw `select()` inside three tool functions (`uw_application_detail`, `uw_risk_assessment`, `uw_preliminary_recommendation`).
3. `compliance_check_tool.py` lines 124-130 -- inline `from db import ApplicationFinancials` + raw `select()` inside `compliance_check`.

The architecture specifies `routes -> services -> models` as the dependency direction. Agent tools should function analogously to routes (they are the "controller" layer for the agent path) and delegate to services. Instead, these tools contain embedded queries with inline imports, ORM joins, and business logic that belongs in the service layer.

**Impact:** If the `ApplicationFinancials` query pattern or borrower lookup changes, it must be updated in 6+ scattered tool files rather than one service function. The `_compliance_gate` function in `decision_tools.py` queries `AuditEvent` directly -- this compliance-critical logic is buried in a tool file rather than living in a testable service. The adverse action notice and LE/CD generation tools contain substantial business logic (fee calculations, notice formatting) that should be service-layer functions.

**Recommendation:** Extract the following into dedicated service functions:
- `services/financials.py` -- `get_financials_for_application(session, application_id)` (replaces 4 inline queries)
- `services/decision.py` -- `get_borrower_for_notice(session, application_id)` (replaces 2 inline borrower lookups in adverse action + LE/CD)
- `services/decision.py` -- `check_compliance_gate(session, application_id)` (moves `_compliance_gate` out of tool layer)
- `services/decision.py` -- `generate_loan_estimate(session, user, application_id)` and `generate_closing_disclosure(...)` (moves LE/CD generation logic out of tools)

### [AR-02] Severity: Warning
**Component(s):** `agents/underwriter_tools.py`, `agents/borrower_tools.py`, `agents/loan_officer_tools.py`, `agents/condition_tools.py`, `agents/decision_tools.py`, `agents/compliance_check_tool.py`
**Finding:** The `_user_context_from_state()` helper function is copy-pasted identically across 6 tool modules. Each copy constructs a `UserContext` from the LangGraph agent state dict using the same logic: extract `user_id`, `user_role`, call `UserRole(role_str)`, call `build_data_scope()`, and assemble the `UserContext`.

All 6 implementations are character-for-character identical except for the default role string (`"borrower"`, `"loan_officer"`, `"underwriter"` -- and even this variance is cosmetic since the actual role always comes from the state dict at runtime).

**Impact:** Six copies means six places to update if `UserContext` gains a field (Phase 5 will likely add CEO context), or if `AgentState` changes shape. A bug fix to one copy must be manually replicated to five others.

**Recommendation:** Extract to a single `agents/_context.py` module (or add it to `agents/base.py`) and import everywhere. The default role parameter can be a function argument.

### [AR-03] Severity: Warning
**Component(s):** `agents/*_tools.py` -> `middleware/auth.py`
**Finding:** All 6 agent tool modules import `build_data_scope` from `middleware.auth`. This creates a dependency from the agent layer into the middleware layer, which architecturally belongs to the HTTP request pipeline. The `build_data_scope` function is a pure function that maps `(UserRole, user_id) -> DataScope` and has no dependency on HTTP middleware concepts (no `Request`, no FastAPI dependencies).

**Impact:** The middleware module becomes a coupling point between two otherwise independent subsystems (HTTP routes and LangGraph agents). If middleware refactoring occurs (e.g., splitting auth concerns), it would unnecessarily affect agent tool imports.

**Recommendation:** Move `build_data_scope()` to `schemas/auth.py` (where `DataScope` and `UserContext` are already defined) or to a new `core/auth.py` module. Both the middleware and agent tools would import from this shared location. This also resolves the coupling identified in AR-02 since the extracted `_user_context_from_state` helper would import from the same core module.

### [AR-04] Severity: Warning
**Component(s):** `services/application.py`
**Finding:** The `transition_stage()` function in `services/application.py` (line 187) raises `fastapi.HTTPException` directly. This is the only service function that raises an HTTP-specific exception. All other services return `None` or `{"error": "..."}` dicts for error signaling (condition service, decision service, etc.).

The service layer should be HTTP-framework-agnostic. When tools call `transition_stage()` (via `loan_officer_tools.py` line 390), a FastAPI HTTPException propagates up through LangGraph's tool execution, which does not handle it the same way the FastAPI exception handler would. The exception is caught by the generic `except Exception` in `_chat_handler.py` line 242, producing a vague "temporarily unavailable" message instead of the clear stage transition error.

**Impact:** Underwriter or LO agents that attempt an invalid stage transition get an opaque error message. The user has no idea why the operation failed. This will be more problematic in Phase 5 where the CEO persona may trigger stage queries.

**Recommendation:** Change `transition_stage()` to return `None` or `{"error": "..."}` consistent with the rest of the service layer. The route handler that calls it should raise `HTTPException`; the tool that calls it should format the error string for the agent.

### [AR-05] Severity: Warning
**Component(s):** `services/decision.py`, `agents/decision_tools.py` (outstanding conditions calculation)
**Finding:** The "outstanding conditions" calculation (`open + responded + under_review + escalated`) is duplicated in 3 locations:

1. `services/decision.py` lines 121-126 (in `_resolve_decision`)
2. `agents/decision_tools.py` lines 571-576 (in `uw_generate_cd`)
3. `agents/condition_tools.py` lines 282-287 (in `uw_condition_summary` -- slightly different, this one is the full unresolved count display)

Each location manually sums the same 4 status counts from `get_condition_summary()` output. If a new condition status is added (Phase 5 could introduce an "escalated_to_manager" status), each location must be updated independently.

**Impact:** A missed update would cause inconsistent behavior between the decision service (which gates approvals) and the CD generation tool (which gates closing disclosure). This is a compliance-relevant inconsistency.

**Recommendation:** Add `get_outstanding_count(summary: dict) -> int` as a function on the condition service (or as a property of a proper ConditionSummary dataclass). All 3 locations should call it.

### [AR-06] Severity: Warning
**Component(s):** `agents/decision_tools.py` lines 254-406, 409-546, 548-701
**Finding:** The `uw_draft_adverse_action`, `uw_generate_le`, and `uw_generate_cd` tool functions are 150-170 lines each and contain substantial business logic: fee calculations, payment computations, borrower lookup, document generation, and TRID date tracking. This is not tool-layer work; these are domain operations that happen to be triggered by an agent.

At 701 lines total, `decision_tools.py` is the largest tool module. The business logic embedded in it (mortgage payment formula, closing cost estimation, adverse action notice format) is untestable without standing up the full LangGraph + DB stack because it is locked inside `@tool`-decorated async functions that require `InjectedState`.

**Impact:** These functions cannot be unit tested in isolation. Any change to fee structures, disclosure formatting, or payment calculations requires integration-level testing through the full agent stack. Phase 5 (CEO dashboard) may need to display loan estimates and closing costs without going through an agent.

**Recommendation:** Extract the pure business logic into service functions:
- `services/trid.py` -- `generate_loan_estimate(app, rate_lock, borrower_name) -> dict`, `generate_closing_disclosure(...)` -- pure computation, no DB
- `services/adverse_action.py` -- `draft_adverse_action_notice(decision, borrower_name, denial_reasons) -> str` -- pure formatting
- The tool functions become thin wrappers: gather data from services, call the pure function, format for agent output.

### [AR-07] Severity: Suggestion
**Component(s):** `agents/borrower_tools.py` line 30
**Finding:** `borrower_tools.py` imports `_DOC_TYPE_LABELS` (prefixed with underscore, indicating private/internal) from `services/completeness.py`. This is the only cross-module import of a private name in the codebase.

**Recommendation:** Either make it public by removing the underscore prefix (`DOC_TYPE_LABELS`) since it is used across module boundaries, or provide a public accessor function.

### [AR-08] Severity: Suggestion
**Component(s):** `agents/borrower_tools.py` lines 293, 351, 360
**Finding:** `borrower_tools.py` imports `_DISCLOSURE_BY_ID` (private name) from `services/disclosure.py` in 3 places using inline `from ..services.disclosure import _DISCLOSURE_BY_ID` inside function bodies. This is the same private-name-crossing pattern as AR-07, but compounded by being an inline import repeated 3 times.

**Recommendation:** Make `_DISCLOSURE_BY_ID` public (`DISCLOSURE_BY_ID`), or better, add a `get_disclosure_label(disclosure_id: str) -> str` public function to the disclosure service and use that instead of reaching into the private lookup dict.

### [AR-09] Severity: Warning
**Component(s):** `routes/applications.py` lines 427-448, 458-509
**Finding:** The `add_borrower` and `remove_borrower` route handlers contain raw SQLAlchemy queries (`select(ApplicationBorrower)`, `select(Borrower)`, `session.add()`, `session.delete()`, `session.commit()`) directly in the route layer. They bypass the service layer entirely.

The route layer should delegate to services for all data mutations. Other routes in the codebase correctly delegate to service functions (e.g., `app_service.create_application`, `app_service.transition_stage`).

**Impact:** No audit trail for borrower add/remove operations. Co-borrower management will grow in Phase 5 (CEO viewing application details); having the logic in routes makes it inaccessible to agents or other callers. The `remove_borrower` endpoint performs a `session.delete()` -- the only hard-delete in the codebase -- without an audit event.

**Recommendation:** Extract to `services/application.py` (or a new `services/borrower.py`): `add_borrower_to_application(session, user, application_id, borrower_id, is_primary)` and `remove_borrower_from_application(session, user, application_id, borrower_id)`. Add audit events for both operations.

### [AR-10] Severity: Suggestion
**Component(s):** `services/application.py`
**Finding:** The service module imports `fastapi.HTTPException` (the only service that does so; see AR-04) and also imports `fastapi.status`. This creates a hard dependency from the service layer to FastAPI. If the services were ever reused in a non-FastAPI context (CLI tool, background worker, agent tool), this import would be a problem.

**Recommendation:** Remove the FastAPI import. Return error dicts or raise domain-specific exceptions (e.g., `class InvalidStageTransitionError(ValueError)`) that callers can translate to their appropriate error format.

### [AR-11] Severity: Warning
**Component(s):** `services/decision.py` lines 37-53
**Finding:** The `_get_ai_recommendation()` function retrieves the AI preliminary recommendation by scanning the last 20 audit events for a `tool_call` with `event_data.tool == "uw_preliminary_recommendation"`. This is a fragile coupling: the decision service depends on the exact string name of a tool defined in `agents/underwriter_tools.py`, and on the specific `event_data` schema that tool writes to audit events.

If the tool is renamed, if its audit `event_data` format changes, or if a different tool produces recommendations, this function silently returns `(None, None)` and the AI agreement comparison is lost.

**Impact:** Silent data loss -- the AI vs. human comparison feature (a key compliance/demo feature for Phase 5 CEO dashboard) depends on string matching audit event payloads. No compile-time or test-time check catches a mismatch.

**Recommendation:** Define a constant (e.g., `PRELIMINARY_RECOMMENDATION_TOOL = "uw_preliminary_recommendation"`) shared between the tool module and the decision service, or better, store the recommendation as a first-class record (e.g., a `preliminary_recommendations` table or a dedicated audit event type) rather than mining the general audit trail.

### [AR-12] Severity: Suggestion
**Component(s):** `services/audit.py` lines 60-83
**Finding:** The hash chain audit pattern uses `pg_advisory_xact_lock` to serialize all audit event inserts globally. Under concurrent agent tool calls (which each open independent `SessionLocal()` contexts), this creates a serial bottleneck: every tool's DB session must wait for the advisory lock before writing any audit event.

In the current Phase 4 codebase, a single UW agent turn with 3 tool calls (e.g., `uw_risk_assessment` + `compliance_check` + `uw_preliminary_recommendation`) results in 3 concurrent sessions each acquiring the advisory lock sequentially. With Phase 5 adding the CEO persona and potentially more concurrent users, this serialization could become a latency concern.

**Recommendation:** For MVP this is acceptable -- document it as a known scalability constraint. For Phase 5 preparation, consider: (a) per-application hash chains instead of a global chain (advisory lock key includes application_id), which would parallelize audit writes across different applications; or (b) batching audit writes per tool turn instead of per tool call.

### [AR-13] Severity: Warning
**Component(s):** `routes/borrower_chat.py`, `routes/loan_officer_chat.py`, `routes/underwriter_chat.py`
**Finding:** The 3 authenticated chat endpoints are nearly identical (85%+ code duplication). Each file:
1. Defines a `router = APIRouter()`
2. Defines a WebSocket endpoint that calls `authenticate_websocket(ws, required_role=UserRole.XXX)`
3. Resolves checkpointer
4. Calls `get_agent("xxx-assistant", checkpointer=checkpointer)`
5. Builds thread_id, session_id
6. Calls `run_agent_stream()`
7. Defines a GET `/xxx/conversations/history` endpoint

The only differences are: the role constant, the agent name string, and the URL path.

**Impact:** Phase 5 will need a CEO chat endpoint. Adding it means copying the same ~40 lines a 4th time. Any protocol change (e.g., adding session metadata to the initial WS handshake) must be applied to all files.

**Recommendation:** Create a factory function in `_chat_handler.py`:

```python
def create_authenticated_chat_routes(
    path_prefix: str,
    agent_name: str,
    required_role: UserRole,
) -> APIRouter:
```

Each persona module becomes a 3-line file. This also makes it trivial to add the CEO endpoint in Phase 5.

### [AR-14] Severity: Suggestion
**Component(s):** `services/decision.py`, `services/condition.py`
**Finding:** Both services return untyped `dict` values from most functions. For example, `render_decision()` returns `dict | None` where the dict's keys are implicit (`id`, `application_id`, `decision_type`, `rationale`, etc.). `get_conditions()` returns `list[dict] | None` where each dict has implicit keys (`id`, `description`, `severity`, `status`, etc.).

This means callers (tool functions) access dict keys by string, with no type checking. A typo like `result["descion_type"]` would only fail at runtime.

**Impact:** As the codebase grows in Phase 5 (CEO dashboard aggregations, analytics), the lack of typed return values from services makes it easy to introduce key-name errors. The decision and condition services are the most complex in the system and would benefit most from structured return types.

**Recommendation:** Define Pydantic models or dataclasses for service return values (e.g., `DecisionResult`, `ConditionInfo`, `ConditionSummary`). The tool layer would access `.decision_type` instead of `["decision_type"]`, gaining IDE autocomplete and type checking. This can be done incrementally -- start with the decision service since it has the highest complexity.

### [AR-15] Severity: Warning
**Component(s):** `services/intake.py` -> `middleware/pii.py`
**Finding:** `services/intake.py` imports `mask_ssn` from `middleware.pii`. This is a service-layer dependency on the middleware layer (same pattern as AR-03 but in the service layer instead of agents). `mask_ssn` is a pure string transformation function (`"123-45-6789"` -> `"***-**-6789"`) with no middleware dependencies.

**Recommendation:** Move `mask_ssn()` to a shared utility module (e.g., `core/pii.py` or `core/masking.py`). Both the middleware and the intake service import from there.

### [AR-16] Severity: Warning
**Component(s):** `agents/decision_tools.py` (LE/CD generation), `services/decision.py`
**Finding:** The `uw_generate_le` and `uw_generate_cd` tools directly mutate the Application ORM object (`app.le_delivery_date = datetime.now(UTC)` at line 527, `app.cd_delivery_date = datetime.now(UTC)` at line 683) from within a tool function. This means a domain-significant field update (TRID compliance tracking) happens as a side effect of text generation, not through a dedicated service operation.

If the LE/CD generation fails after setting the date but before commit, the date is rolled back -- but the generated text was already formatted using that date. If the tool is retried (LangGraph retry), the date is set again, potentially creating confusion about "when was the LE actually delivered."

**Impact:** TRID compliance timing is a demo-critical feature. Having the delivery date set as a side effect of document generation rather than as an explicit service operation makes it harder to reason about correctness. Phase 5 CEO dashboard may need to query these dates for compliance reporting.

**Recommendation:** Separate date tracking from document generation:
1. `services/trid.py` -- `record_le_delivery(session, application_id)` and `record_cd_delivery(...)` -- explicit date-setting service functions with their own audit events
2. The LE/CD tool calls the generation function, then explicitly records delivery

### [AR-17] Severity: Suggestion
**Component(s):** `compose.yml`
**Finding:** MinIO is not gated behind any profile -- it runs in the default (no-profile) stack alongside postgres, api, and ui. The comment says `(none) postgres + minio + api + ui`. MinIO was added for LangFuse v3 object storage, but it is also used for document storage by the API.

For developers who only need the minimal stack (no document uploads, no observability), MinIO adds ~200MB of container image weight and a port binding (9090/9091) to the default profile.

**Recommendation:** Consider whether MinIO should be in the `storage` profile for observability-only use cases, with the API gracefully degrading when MinIO is unavailable (document uploads return a clear error). Currently the API's `depends_on: minio` hard-requires it. This is a minor operational concern but worth noting for the 10-minute setup goal.

### [AR-18] Severity: Warning
**Component(s):** Agent graph caching in `agents/registry.py`
**Finding:** The agent registry caches compiled LangGraph graphs as module-level singletons (`_graphs` dict). The cache key is the agent name, and the value is `(graph, mtime)`. However, the `checkpointer` parameter passed to `get_agent()` is not part of the cache key.

If `get_agent("underwriter-assistant", checkpointer=A)` is called, it caches the graph with checkpointer A. A subsequent call `get_agent("underwriter-assistant", checkpointer=B)` returns the cached graph with checkpointer A (because mtime hasn't changed), silently ignoring checkpointer B.

In the current codebase this is not a practical problem because each chat endpoint always passes the same checkpointer instance from the singleton `ConversationService`. But it is a latent bug that would surface if tests or future code paths use different checkpointers.

**Impact:** Low immediate risk, but the API contract of `get_agent(name, checkpointer)` is misleading -- the checkpointer is only used on first build or config change.

**Recommendation:** Either (a) document that checkpointer must be consistent across calls for the same agent, or (b) include checkpointer identity in the cache key, or (c) move checkpointer binding to the chat handler (compile the graph without checkpointer, then bind at invocation time if LangGraph supports this).

---

## Summary

### Critical: 0
### Warning: 11 (AR-01, AR-02, AR-03, AR-04, AR-05, AR-06, AR-09, AR-11, AR-13, AR-15, AR-16)
### Suggestion: 5 (AR-07, AR-08, AR-10, AR-12, AR-14)

### Systemic Themes

1. **Service layer bypass** (AR-01, AR-06, AR-09): Agent tools and routes contain substantial business logic and raw DB queries that should be in the service layer. This is the most impactful structural issue -- it makes business logic untestable, un-reusable, and scattered.

2. **Cross-layer coupling** (AR-03, AR-15): Both agents and services import from `middleware/`, creating dependency arrows that go sideways instead of downward. The fix is straightforward: move pure utility functions (`build_data_scope`, `mask_ssn`) to a shared `core/` or `schemas/` location.

3. **Code duplication** (AR-02, AR-05, AR-13): The `_user_context_from_state` helper (6 copies), outstanding conditions calculation (3 copies), and chat endpoint boilerplate (3 copies) are copy-paste patterns that will each need a 4th copy in Phase 5 (CEO persona).

4. **Untyped service returns** (AR-14): Service functions return raw dicts, forcing string-key access with no type safety. This is manageable at current scale but will become a maintenance burden as Phase 5 adds aggregation and reporting.

### Phase 5 Readiness Assessment

The codebase is structurally sound for the current feature set -- all 739 tests pass, the agent architecture is consistent, compliance subsystems (KB, checks, HMDA) are well-isolated, and the audit trail hash chain is correctly implemented.

However, Phase 5 (Executive/CEO persona) will need:
- **Aggregation queries** across applications -- currently all data access goes through `get_application()` which returns one app at a time. The CEO dashboard will need portfolio-level views.
- **A 4th chat endpoint** -- with the current copy-paste pattern (AR-13), this means another 40-line file identical to the other three.
- **Reuse of LE/CD and decision data** -- the CEO needs to see these without going through an agent. With business logic locked in tool functions (AR-01, AR-06), this data is inaccessible to REST endpoints.

Addressing AR-01 (service layer extraction) and AR-13 (chat endpoint factory) before Phase 5 implementation would significantly reduce Phase 5 complexity and prevent further accumulation of the patterns identified here.
