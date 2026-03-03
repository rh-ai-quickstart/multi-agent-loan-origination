# Pre-Phase 3 Technical Design Review -- Tech Lead

**Reviewer:** Tech Lead
**Date:** 2026-02-26
**Scope:** Technical patterns, interface contracts, and Phase 3 readiness
**Branch:** chore/pre-audit-cleanup (reviewing current state of main)

---

## TL-01: Agent registry uses hardcoded dispatch -- not extensible for new agents

**Severity:** Warning
**Location:** `packages/api/src/agents/registry.py:34-44`

**Description:**
The `_build_graph()` function uses a hardcoded if/elif chain to map agent names to builder functions:

```python
def _build_graph(agent_name: str, config: dict[str, Any], checkpointer=None):
    if agent_name == "public-assistant":
        from .public_assistant import build_graph
        return build_graph(config, checkpointer=checkpointer)
    if agent_name == "borrower-assistant":
        from .borrower_assistant import build_graph
        return build_graph(config, checkpointer=checkpointer)
    raise ValueError(f"Unknown agent: {agent_name}")
```

Adding the `loan-officer-assistant` (and later `underwriter-assistant`, `ceo-assistant`) requires modifying this function each time.

**Impact on Phase 3:** The loan officer assistant is the primary agent for Phase 3. It must be registered here. Every future agent requires touching this central dispatch function, violating open-closed principle.

**Recommendation:** Switch to a registration-based pattern. Either:
- A decorator-based registry (`@register_agent("loan-officer-assistant")`) on each agent module's `build_graph`, or
- A module-name convention where `_build_graph` imports `agents.{name_with_underscores}` dynamically, or
- A `REGISTRY` dict at module level that each agent module appends to on import.

The YAML config already carries `agent.name` -- the Python-side dispatch should match automatically rather than requiring manual wiring.

---

## TL-02: Borrower tools create their own DB sessions -- bypasses caller session context

**Severity:** Critical
**Location:** `packages/api/src/agents/borrower_tools.py` (lines 71, 121, 175, 293, 320, 365, 427, 469, 501, 571, 627, 677)

**Description:**
Every database-accessing tool in `borrower_tools.py` creates its own session via `async with SessionLocal() as session:`. This means tool invocations run in isolated transactions, disconnected from any outer request session. Example:

```python
@tool
async def document_completeness(application_id: int, state: Annotated[dict, InjectedState]) -> str:
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await check_completeness(session, user, application_id)
```

This pattern has several consequences:
1. **No shared transaction scope** -- if a tool writes an audit event and the graph subsequently fails, the audit event is already committed and cannot be rolled back.
2. **Inconsistent reads** -- two tools called in the same agent turn read from different snapshots (the first tool's commit may not be visible to the second).
3. **The pattern will proliferate** -- the loan officer assistant will need 6+ new tools (`application_detail`, `submit_to_underwriting`, `draft_communication`, etc.), each creating its own session.

**Impact on Phase 3:** The `submit_to_underwriting` tool (S-3-F8-03) needs to atomically: (a) validate readiness, (b) transition application state, (c) write an audit event. With per-tool sessions, a crash between (b) and (c) leaves the state transitioned without an audit record. The `draft_communication` tool also needs to read application + documents + rate locks + conditions in a consistent snapshot.

**Recommendation:** Inject a shared session through the graph state or a contextvar. The `_chat_handler.run_agent_stream` already has access to `get_db()` for audit writes -- extend this pattern so tools receive a session from the graph invocation context rather than creating their own. This also enables the future ability to wrap an entire agent turn in a single transaction.

---

## TL-03: No application state machine enforcement

**Severity:** Critical
**Location:** `packages/api/src/services/application.py:122-150`

**Description:**
The `update_application` service accepts a `stage` field in `_UPDATABLE_FIELDS` and applies it with a simple `setattr` -- no validation of whether the transition is valid:

```python
_UPDATABLE_FIELDS = {"stage", "loan_type", "property_address", "loan_amount", "property_value", "assigned_to"}

async def update_application(session, user, application_id, **updates):
    app = await get_application(session, user, application_id)
    for field, value in updates.items():
        if field not in _UPDATABLE_FIELDS:
            continue
        setattr(app, field, value)
    await session.commit()
```

There is no state machine implementation anywhere in the codebase. The `ApplicationStage` enum defines 10 stages, but valid transitions between them are not enforced.

**Impact on Phase 3:** S-3-F8-03 and S-3-F8-04 explicitly require: (a) `application -> underwriting` transition with validation, (b) rejection of invalid transitions (e.g., re-submitting an application already in underwriting), (c) audit trail for all transitions. Without a state machine, any caller with write access can set any stage to any value, breaking the lending lifecycle invariants. The requirements (S-3-F8-04) specifically list the valid transitions:
- `application -> underwriting` or `application -> withdrawn`
- `underwriting -> conditional_approval` or `underwriting -> denied` or `underwriting -> application`

**Recommendation:** Implement a transition table and a `transition_stage(app, from_stage, to_stage, user)` service function that:
1. Validates the transition against the allowed transition map
2. Rejects invalid transitions with a clear error
3. Writes an audit event with `from_state`, `to_state`, and the triggering user
4. Returns the updated application

Remove `stage` from `_UPDATABLE_FIELDS` so it cannot be set via the generic `update_application` path. All stage changes must go through the state machine function.

---

## TL-04: WebSocket chat handler locked to single-role auth -- no multi-role agents

**Severity:** Warning
**Location:** `packages/api/src/routes/_chat_handler.py:25-85`, `packages/api/src/routes/borrower_chat.py:30`

**Description:**
The `authenticate_websocket()` function takes a single `required_role` parameter and rejects any user whose role does not exactly match:

```python
if required_role is not None and role != required_role:
    await ws.close(code=4003, reason="Insufficient permissions")
    return None
```

The borrower chat endpoint hardcodes `required_role=UserRole.BORROWER`.

**Impact on Phase 3:** The loan officer assistant needs a WebSocket endpoint that accepts users with the `loan_officer` role. This means creating a third chat route file (`lo_chat.py`), which is fine. But the pattern needs to also support `admin` role accessing any chat endpoint for testing/debugging. Currently, an admin cannot use the borrower chat endpoint.

**Recommendation:** Change `required_role` to `allowed_roles: list[UserRole] | None` to support multi-role matching:

```python
if allowed_roles is not None and role not in allowed_roles:
    await ws.close(code=4003, reason="Insufficient permissions")
```

This is a simple change but should be done before Phase 3 to avoid duplicating the single-role pattern in the LO chat endpoint.

---

## TL-05: `_user_context_from_state` fabricates email and name

**Severity:** Warning
**Location:** `packages/api/src/agents/borrower_tools.py:46-57`

**Description:**
The helper that constructs a `UserContext` from graph state fabricates the email and name fields:

```python
def _user_context_from_state(state: dict) -> UserContext:
    user_id = state.get("user_id", "anonymous")
    role_str = state.get("user_role", "borrower")
    role = UserRole(role_str)
    return UserContext(
        user_id=user_id,
        role=role,
        email=f"{user_id}@summit-cap.local",
        name=user_id,
        data_scope=_build_data_scope(role, user_id),
    )
```

The actual user's email and name (from the JWT) are not propagated through the graph state. Only `user_id` and `user_role` are passed.

**Impact on Phase 3:** The loan officer assistant's `draft_communication` tool (S-3-F24-01) needs the LO's real name for the signature block: "If you have any questions, feel free to reach out. - [LO name]". With fabricated names, the draft would say "james.torres" instead of "James Torres". Similarly, audit events written by tools record fabricated user metadata.

**Recommendation:** Propagate `user_email` and `user_name` through the `AgentState` graph state (they are already available in the WebSocket auth step). Update `_user_context_from_state` to read these from state rather than fabricating them.

---

## TL-06: DataScope contract diverges from interface contracts spec

**Severity:** Warning
**Location:** `packages/api/src/schemas/auth.py:8-16` vs `plans/interface-contracts-phase-1.md:43-48`

**Description:**
The interface contracts define `DataScope` as:

```python
class DataScope(BaseModel):
    assigned_to: str | None = None
    pii_mask: bool = False
    own_data_only: bool = False
    user_id: str | None = None
    full_pipeline: bool = False
```

The actual implementation adds an undocumented field:

```python
class DataScope(BaseModel):
    assigned_to: str | None = None
    pii_mask: bool = False
    document_metadata_only: bool = False  # NOT in the interface contract
    own_data_only: bool = False
    user_id: str | None = None
    full_pipeline: bool = False
```

The `document_metadata_only` field is set for the CEO role in `_build_data_scope()` (auth.py:143) but is never checked by any service or route handler. It appears to be a placeholder that was added but never wired up.

**Impact on Phase 3:** The CEO persona is Phase 5, but if `document_metadata_only` is intended to limit CEO document access (e.g., CEO can see document metadata but not download content), it should be documented in the contract. If it is dead code, it should be removed to avoid confusion during Phase 3 when LO document access patterns are being built.

**Recommendation:** Either implement the `document_metadata_only` check in the document service/routes (if it is needed), or remove the field and the CEO assignment. Update the interface contracts document to match either way. Do not leave undocumented fields in the contract.

---

## TL-07: No scope validation when tools access applications by ID

**Severity:** Warning
**Location:** `packages/api/src/agents/borrower_tools.py` (multiple tools)

**Description:**
Several tools accept an `application_id` parameter directly from the LLM without verifying that the authenticated user should have access to that application before querying. While the service layer does apply `apply_data_scope()`, the tool layer trusts whatever `application_id` the LLM passes. In the normal flow, the LLM infers the application_id from conversation context, but prompt injection could cause it to pass a different ID.

The defense-in-depth works here because `apply_data_scope` filters at the DB level, so an out-of-scope ID returns `None` (which the tool reports as "not found"). But the tools do not distinguish between "not found" and "not authorized" -- they return the same message.

**Impact on Phase 3:** S-3-F7-02 explicitly requires defense-in-depth with distinct handling: "RBAC enforcement at service layer -- the service re-applies the data scope filter" and "Attempt to access another LO's application directly -- API returns 403 Forbidden." The current pattern returns "not found" for unauthorized access, which does not meet the 403 requirement for direct API access via REST routes. The REST routes (applications.py) also return 404 for out-of-scope resources (by design, to avoid leaking existence), but the requirements explicitly want 403 for direct access attempts by LOs.

**Recommendation:** For the REST API pipeline endpoint (Phase 3), implement 403 for LO-to-LO application access: check scope before querying, and return 403 when `assigned_to != current_user`. The "return 404 to avoid leaking existence" pattern is appropriate for borrowers but not for LOs, who know the application exists because it was previously in their view. For tool-level access, the current pattern (scope filtering returns None) is acceptable since tool calls are agent-mediated.

---

## TL-08: PII masking is applied ad-hoc in route handlers, not as middleware

**Severity:** Warning
**Location:** `packages/api/src/routes/applications.py:81-87, 119-122`

**Description:**
PII masking for the CEO role is applied inline in each route handler:

```python
if user.data_scope.pii_mask:
    items = [
        ApplicationResponse.model_construct(
            **mask_application_pii(item.model_dump(mode="json"))
        )
        for item in items
    ]
```

This pattern must be replicated in every route that returns borrower PII. The interface contracts (Section 5) describe PII masking as "Applied as response middleware" but it is not implemented as middleware -- it is per-route logic.

**Impact on Phase 3:** The loan officer pipeline endpoint, application detail endpoint, and any new routes returning borrower data must each remember to apply PII masking. Missing it in one route creates a PII leak for the CEO role. Phase 5 (CEO features) will add aggregate endpoints that also need masking.

**Recommendation:** Implement PII masking as FastAPI response middleware (or a response model hook) that checks `request.state.user_context.data_scope.pii_mask` and transforms the response body automatically. This ensures masking cannot be accidentally omitted from new routes. The middleware approach matches what the interface contracts describe.

---

## TL-09: No pipeline-specific query with urgency computation

**Severity:** Warning
**Location:** `packages/api/src/services/application.py:24-51`

**Description:**
The existing `list_applications` service provides basic pagination and data scope filtering but has no support for:
- Urgency indicator computation (rate lock expiration, stage timing, document staleness)
- Pipeline-specific sorting (by urgency, closing date, loan amount, last activity)
- Pipeline-specific filtering (by stage, by closing date range, by stalled status)

Phase 3 (S-3-F7-01) requires all of these.

**Impact on Phase 3:** The loan officer pipeline view is the central feature of Phase 3. Building it requires either extending `list_applications` significantly or creating a dedicated `get_pipeline` service function. The urgency computation logic (S-3-F7-03) requires joining across `rate_locks`, `conditions`, `documents`, and computing derived fields -- this is a fundamentally different query pattern than the current simple list.

**Recommendation:** Create a dedicated `services/pipeline.py` with a `get_pipeline()` function that:
1. Queries applications with eager-loaded rate locks, conditions, and document metadata
2. Computes urgency indicators per the requirements thresholds
3. Supports sorting by urgency, closing date, loan amount, last activity
4. Supports filtering by stage, closing date range, stalled status
5. Returns pipeline-specific response schemas (not reusing the generic `ApplicationResponse`)

Keep `list_applications` for the generic CRUD use case. The pipeline is a distinct view model with different data requirements.

---

## TL-10: Agent tools return plain strings -- no structured tool output

**Severity:** Warning
**Location:** `packages/api/src/agents/borrower_tools.py` (all tools), `packages/api/src/agents/tools.py`

**Description:**
All agent tools return formatted plain strings:

```python
@tool
async def rate_lock_status(application_id: int, state: ...) -> str:
    ...
    lines = [f"Rate lock status for application {application_id}:"]
    lines.append("Status: Active")
    ...
    return "\n".join(lines)
```

The LLM receives text and must parse it to extract structured data (e.g., days remaining for urgency computation).

**Impact on Phase 3:** The loan officer assistant needs to compose information from multiple tools to make recommendations (e.g., "Is this application ready for underwriting?" requires checking document completeness + quality flags + financial data extraction). When tools return formatted strings, the LLM must parse text to reason about the data, which is error-prone.

More critically, the `draft_communication` tool (F24) needs structured access to borrower name, loan details, missing documents, conditions, and rate lock data to compose drafts. Feeding pre-formatted strings to the LLM for re-formatting into a communication draft is wasteful and may introduce formatting artifacts.

**Recommendation:** This is not blocking for Phase 3 (LLMs can parse formatted strings adequately for MVP), but for the loan officer tools, consider returning structured JSON strings or using LangChain's structured output capabilities. At minimum, ensure LO tools are designed with richer data than the borrower tools (the LO needs more data to make decisions; the borrower just needs status summaries).

---

## TL-11: No application-scoped conversation threading

**Severity:** Warning
**Location:** `packages/api/src/services/conversation.py:100-113`

**Description:**
The conversation thread ID format is `user:{user_id}:agent:{agent_name}`. This means each user has exactly one conversation thread per agent type. There is no application-level threading.

```python
@staticmethod
def get_thread_id(user_id: str, agent_name: str = "public-assistant") -> str:
    return f"user:{user_id}:agent:{agent_name}"
```

**Impact on Phase 3:** A loan officer manages multiple applications. The Phase 3 requirements (S-3-F7-04, S-3-F8-01) describe the LO clicking an application from the pipeline to open a chat interface *for that application*. With the current threading model, the LO would have a single conversation across all applications. Switching from application A001 to A002 would carry conversation context from A001, confusing the agent.

The requirements also state (S-3-F7-04): "Application detail loads conversation history -- If I have previously chatted with the borrower about application A001, when I open the application detail, the chat interface displays the conversation history."

**Recommendation:** Extend the thread ID to include an optional application context: `user:{user_id}:agent:{agent_name}:app:{application_id}`. The LO chat endpoint should accept an `application_id` parameter (via query string or initial message) and use it to scope the conversation thread. This allows:
- Multiple parallel conversations per LO (one per application)
- Resuming the conversation for a specific application
- Clean context separation between applications

---

## TL-12: Condition respond endpoint restricted to BORROWER -- LO cannot respond

**Severity:** Warning
**Location:** `packages/api/src/routes/applications.py:216-218`

**Description:**
The condition response REST endpoint is restricted to borrowers:

```python
@router.post(
    "/{application_id}/conditions/{condition_id}/respond",
    dependencies=[Depends(require_roles(UserRole.BORROWER, UserRole.ADMIN))],
)
```

**Impact on Phase 3:** S-3-F8-01 describes the LO reviewing conditions and potentially responding or acting on them. While the LO does not "respond" to conditions in the same way a borrower does, the LO needs to clear conditions (S-3-F8-04 leads into F11 underwriting workflow). The current `ConditionStatus` enum includes `CLEARED` and `WAIVED` states, but there is no REST endpoint or tool for the LO or underwriter to clear/waive conditions.

**Recommendation:** Add a separate endpoint or extend the existing one for condition management by LOs and underwriters:
- `POST /api/applications/{id}/conditions/{cid}/clear` -- LO/underwriter clears a condition
- `POST /api/applications/{id}/conditions/{cid}/waive` -- underwriter waives a condition
- Include `cleared_by` tracking in the condition model (the column exists but is never populated)

This is Phase 3/4 implementation work, but the gap should be acknowledged in the technical design.

---

## TL-13: Duplicate application scope verification pattern across services

**Severity:** Warning
**Location:** `packages/api/src/services/condition.py`, `packages/api/src/services/rate_lock.py`, `packages/api/src/services/status.py`, `packages/api/src/services/completeness.py`

**Description:**
Every service that operates on a child entity (conditions, rate locks, documents) first verifies application scope by executing a separate application query with `selectinload` for borrowers:

```python
# This exact pattern appears in condition.py, rate_lock.py, completeness.py, status.py
app_stmt = (
    select(Application)
    .options(
        selectinload(Application.application_borrowers).joinedload(ApplicationBorrower.borrower)
    )
    .where(Application.id == application_id)
)
app_stmt = apply_data_scope(app_stmt, user.data_scope, user)
app_result = await session.execute(app_stmt)
app = app_result.unique().scalar_one_or_none()
if app is None:
    return None
```

This 8-line block is copy-pasted across at least 8 service functions.

**Impact on Phase 3:** The loan officer assistant will need 4-6 new service functions, each of which will need this same scope verification. The pattern already appears ~8 times; Phase 3 will push it to 12-14 copies. Any change to scope verification logic (e.g., adding LO-specific 403 vs 404 behavior per TL-07) must be applied to all copies.

**Recommendation:** Extract a shared `verify_application_access(session, user, application_id) -> Application | None` function in `services/scope.py` (or a new `services/access.py`) that encapsulates this pattern. Service functions call it instead of duplicating the query.

---

## TL-14: WebSocket protocol has no application context message type

**Severity:** Warning
**Location:** `packages/api/src/routes/_chat_handler.py:140-141`

**Description:**
The WebSocket protocol currently supports only one client message type:

```python
if data.get("type") != "message" or not data.get("content"):
    await ws.send_json(
        {"type": "error", "content": "Expected {type: message, content: ...}"}
    )
```

There is no way for the client to send contextual information (like which application the LO is currently viewing) without embedding it in the message text.

**Impact on Phase 3:** The LO chat interface (S-3-F8-01) is application-scoped. When the LO opens the chat for application A001, the frontend needs to tell the backend which application the conversation is about. Options:
1. Embed `application_id` in the WebSocket URL: `/api/lo/chat?application_id=1`
2. Send a `{"type": "context", "application_id": 1}` message before starting
3. Have the LO always start with "Show me application 1"

Option 1 is simplest but means reconnecting when switching applications. Option 2 is the cleanest protocol extension.

**Recommendation:** Add a `context` message type to the WebSocket protocol that allows the client to set application-level context:

```json
{"type": "context", "application_id": 123}
```

The handler would inject this into the graph state, making it available to tools without the LLM needing to extract it from conversation text. This also supports the thread ID extension recommended in TL-11.

---

## TL-15: `apply_data_scope` does not handle `full_pipeline` flag

**Severity:** Warning
**Location:** `packages/api/src/services/scope.py:15-49`

**Description:**
The `apply_data_scope` function handles `own_data_only` (borrower) and `assigned_to` (loan officer) but has no explicit handling for `full_pipeline` (underwriter, admin, CEO):

```python
def apply_data_scope(stmt, scope: DataScope, user: UserContext, *, join_to_application=None):
    if scope.own_data_only and scope.user_id:
        # ... borrower filter
    elif scope.assigned_to:
        # ... LO filter
    return stmt  # No filter for full_pipeline -- returns unfiltered
```

This works correctly (underwriter/admin/CEO see everything because no filter is applied), but it relies on fall-through behavior rather than explicit intent. There is no assertion that at least one scope flag is set.

**Impact on Phase 3:** If a new role is added or scope logic is modified, the implicit fall-through could accidentally grant unfiltered access to a role that should be restricted. The underwriter scope (per interface contracts Section 5) should only see "applications in underwriting+" but the current implementation applies no filter, meaning underwriters see all applications in all stages.

**Recommendation:** Make the underwriter scope explicit: add a `stage_filter` field to `DataScope` and set it for the underwriter role to `[underwriting, conditional_approval, clear_to_close]`. Or at minimum, add a comment documenting that the fall-through is intentional and listing which roles use it.

---

## TL-16: `ApplicationFinancials` relationship is `uselist=False` but schema supports co-borrowers

**Severity:** Warning
**Location:** `packages/db/src/db/models.py:91-93` vs `packages/db/src/db/models.py:144-146`

**Description:**
The `Application.financials` relationship is defined as `uselist=False`:

```python
financials = relationship(
    "ApplicationFinancials", back_populates="application",
    uselist=False, cascade="all, delete-orphan",
)
```

But `ApplicationFinancials` has a unique constraint on `(application_id, borrower_id)`, meaning there can be one financials record per borrower per application. With co-borrowers, an application has multiple borrowers and thus multiple financials records.

The `uselist=False` means `app.financials` returns only one record (the first one found), silently dropping the co-borrower's financial data.

**Impact on Phase 3:** The loan officer needs to see financial data for both borrowers when reviewing an application (S-3-F8-01: "What is the borrower's monthly income?"). With `uselist=False`, the LO would only see one borrower's financials. The DTI calculation in the intake service also only computes for the primary borrower.

**Recommendation:** Change `uselist=False` to `uselist=True` (or use `relationship("ApplicationFinancials", ...)` which defaults to a list). Update all code that accesses `app.financials` to handle a list. For backward compatibility in the intake service, the primary borrower's financials can be accessed by filtering the list.

---

## TL-17: No document content access endpoint for loan officers

**Severity:** Warning
**Location:** `packages/api/src/routes/documents.py`

**Description:**
The requirements (S-3-F8-02 Notes) specify: "The LO can view raw documents via a document viewer endpoint (`GET /api/documents/{id}/content`), subject to RBAC (CEO cannot access content, LO can access documents in their pipeline)."

I was not able to verify whether this endpoint exists in the current `documents.py` route file without reading it, but the interface contracts Phase 1 spec does not include a document content endpoint, and the Phase 2 document implementation focused on upload and extraction. The `document_metadata_only` DataScope field (TL-06) suggests awareness of this need but no implementation.

**Impact on Phase 3:** S-3-F8-02 explicitly requires the LO to view raw documents. Without a content download endpoint, the LO cannot review actual document images for quality assessment.

**Recommendation:** Add `GET /api/documents/{id}/content` that serves the document file from MinIO storage, with RBAC checks:
- LO: can access documents for applications assigned to them
- Underwriter: can access documents for applications in their queue
- CEO: blocked (`document_metadata_only`)
- Borrower: can access their own documents

---

## TL-18: Agent graph state does not carry `application_id` for tool invocations

**Severity:** Warning
**Location:** `packages/api/src/agents/base.py:62-70`, `packages/api/src/agents/borrower_tools.py`

**Description:**
The `AgentState` includes `user_role` and `user_id` but not `application_id`:

```python
class AgentState(MessagesState):
    model_tier: str
    safety_blocked: bool
    escalated: bool
    user_role: str
    user_id: str
    tool_allowed_roles: dict[str, list[str]]
```

Every tool that needs an application ID requires the LLM to pass it as a parameter. The LLM must infer the correct `application_id` from conversation context.

**Impact on Phase 3:** The LO assistant operates in the context of a specific application (per TL-11 and TL-14). Tools like `application_detail`, `completeness_check`, `submit_to_underwriting`, and `draft_communication` all need the application ID. If the application context is set once (via the context message in TL-14), it should be available to all tools without the LLM needing to pass it each time. This reduces hallucination risk (LLM passing wrong application ID) and simplifies tool signatures.

**Recommendation:** Add `application_id: int | None` to `AgentState`. Set it when the LO selects an application from the pipeline. Tools can read it from state (via `InjectedState`) as a default, falling back to an explicit parameter for tools that operate across applications.

---

## TL-19: Condition schema `created_at` is a string, not a datetime

**Severity:** Info
**Location:** `packages/api/src/schemas/condition.py:16`

**Description:**
The `ConditionItem` schema defines `created_at` as `str | None`:

```python
class ConditionItem(BaseModel):
    id: int
    description: str
    severity: str | None = None
    status: str | None = None
    response_text: str | None = None
    issued_by: str | None = None
    created_at: str | None = None
```

This is because the condition service manually converts to `.isoformat()` strings before returning. The schema also uses `str` for `severity` and `status` instead of the enum types.

**Impact on Phase 3:** The LO pipeline urgency computation (S-3-F7-03) needs to compute time-based urgency from condition creation dates. Working with string dates requires parsing them back. The LO's tools will need typed data for sorting and filtering.

**Recommendation:** Use proper types in the schema: `datetime | None` for `created_at`, `ConditionSeverity | None` for `severity`, `ConditionStatus | None` for `status`. Let Pydantic's JSON serialization handle the conversion. This is a minor consistency fix but prevents the pattern from spreading to new schemas.

---

## TL-20: Service functions return raw dicts instead of typed models

**Severity:** Warning
**Location:** `packages/api/src/services/condition.py`, `packages/api/src/services/rate_lock.py`, `packages/api/src/services/intake.py`

**Description:**
Multiple service functions return untyped dicts:

- `get_conditions()` returns `list[dict] | None`
- `respond_to_condition()` returns `dict | None`
- `get_rate_lock_status()` returns `dict | None`
- `start_application()` returns `dict`
- `update_application_fields()` returns `dict`

The dict shapes are implicit and documented only by reading the implementation.

**Impact on Phase 3:** As the number of services grows (pipeline service, urgency computation, communication drafting), using untyped dicts makes it hard to know what fields are available without reading each function's implementation. This is especially problematic for the loan officer assistant's tools, which will compose data from multiple services.

**Recommendation:** Define Pydantic response models (or at minimum, TypedDict) for service return types. This provides IDE autocompletion, type checking, and self-documenting interfaces. For example:

```python
class ConditionResult(BaseModel):
    id: int
    description: str
    severity: ConditionSeverity | None
    status: ConditionStatus | None
    response_text: str | None
    issued_by: str | None
    created_at: datetime | None
```

This can be shared between the service layer and the schema layer (the schema may be a subset or transformation of the service model).

---

## Summary

| ID | Severity | Title |
|----|----------|-------|
| TL-01 | Warning | Agent registry uses hardcoded dispatch |
| TL-02 | Critical | Borrower tools create own DB sessions |
| TL-03 | Critical | No application state machine enforcement |
| TL-04 | Warning | WebSocket chat handler locked to single-role auth |
| TL-05 | Warning | `_user_context_from_state` fabricates email and name |
| TL-06 | Warning | DataScope contract diverges from interface contracts |
| TL-07 | Warning | No scope validation distinguishing 403 vs 404 |
| TL-08 | Warning | PII masking is ad-hoc, not middleware |
| TL-09 | Warning | No pipeline-specific query with urgency computation |
| TL-10 | Warning | Agent tools return plain strings, no structured output |
| TL-11 | Warning | No application-scoped conversation threading |
| TL-12 | Warning | Condition respond endpoint restricted to BORROWER |
| TL-13 | Warning | Duplicate application scope verification pattern |
| TL-14 | Warning | WebSocket protocol has no application context type |
| TL-15 | Warning | `apply_data_scope` does not handle `full_pipeline` |
| TL-16 | Warning | `ApplicationFinancials` uselist=False with co-borrowers |
| TL-17 | Warning | No document content access endpoint for LOs |
| TL-18 | Warning | Agent graph state does not carry application_id |
| TL-19 | Info | Condition schema uses strings instead of typed fields |
| TL-20 | Warning | Service functions return raw dicts instead of typed models |

**Critical items (TL-02, TL-03)** should be addressed before Phase 3 implementation begins. They affect data integrity (state machine) and transaction safety (tool sessions).

**Warning items** can be addressed as part of Phase 3 implementation, but should be tracked in the technical design to avoid rediscovery during implementation.
