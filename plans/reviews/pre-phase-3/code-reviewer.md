# Code Quality Review -- Pre-Phase 3

**Reviewer:** Code Reviewer (Opus)
**Date:** 2026-02-26
**Scope:** All Python source in `packages/api/src/` and `packages/db/src/`, all TypeScript in `packages/ui/src/`
**Branch:** `chore/pre-audit-cleanup` (clean, mirrors main)

---

## CR-01: quality_flags stored as JSON but parsed as CSV in condition service

**Severity:** Critical
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/condition.py:279`

**Description:** The extraction service writes `quality_flags` to the database as JSON (`json.dumps(["unreadable"])` in `extraction.py:90,101,127`), and the completeness service correctly deserializes it with `json.loads()` (`completeness.py:270`). However, `check_condition_documents()` in `condition.py:279` splits it as a comma-separated string:

```python
"quality_flags": doc.quality_flags.split(",") if doc.quality_flags else [],
```

For a JSON value like `'["blurry", "wrong_period"]'`, `.split(",")` produces `['["blurry"', ' "wrong_period"]']` -- malformed strings with stray brackets and quotes. This means the condition satisfaction check will always misrepresent quality issues, and the borrower-facing `check_condition_satisfaction` tool will display garbled flag names.

**Recommendation:** Replace `.split(",")` with `json.loads()` to match the serialization format used by `extraction.py`:

```python
import json
# ...
"quality_flags": json.loads(doc.quality_flags) if doc.quality_flags else [],
```

---

## CR-02: Duplicate content-type validation -- route and service both validate

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/documents.py:64-70` and `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/document.py:125-129`

**Description:** Content-type validation is performed twice for document uploads: once in the route handler (`documents.py:64-70`) and once in the service (`document.py:125-129`). Both check against the same `ALLOWED_CONTENT_TYPES` set. The route returns HTTP 422, the service raises `DocumentUploadError`. But the route check runs first, so the service's `DocumentUploadError` for content type is dead code -- it can never be reached through the normal HTTP path.

Additionally, `ALLOWED_CONTENT_TYPES` is defined in both `services/document.py:24` and `services/storage.py:21` as identical sets. Three definitions of the same constant is two too many.

**Recommendation:** Define `ALLOWED_CONTENT_TYPES` once (in `document.py` or a shared constants module) and validate only in the service layer. The route should delegate validation entirely to the service and map exceptions to HTTP responses. Remove the duplicate in `storage.py`.

---

## CR-03: Duplicate SSN masking implementations

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/middleware/pii.py:12-20` and `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/intake.py:338-345`

**Description:** Two independent SSN masking functions exist:

- `mask_ssn()` in `pii.py` uses `re.sub(r"\D", "", value)` to extract digits
- `_mask_ssn()` in `intake.py` uses `value.replace("-", "").replace(" ", "")` to strip separators

They produce the same result for well-formed SSNs but differ on edge cases with other non-digit characters. This divergence is an invitation for inconsistent masking behavior -- a bug in one won't be caught by tests for the other.

**Recommendation:** Delete `_mask_ssn` from `intake.py` and import `mask_ssn` from `middleware.pii`.

---

## CR-04: `_build_data_scope` is a private function used across module boundaries

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/middleware/auth.py:136`

**Description:** `_build_data_scope`, `_decode_token`, and `_resolve_role` are prefixed with underscore (private by convention), but they are imported and used by both `routes/_chat_handler.py:17` and `agents/borrower_tools.py:18`. This breaks the encapsulation convention -- callers depend on implementation details of the auth middleware, and a refactor of auth internals would silently break two other modules.

**Recommendation:** Either make these functions public (remove the underscore prefix) since they are part of the module's de facto API, or extract them into a separate public utility (e.g., `middleware/auth_utils.py`).

---

## CR-05: `_chat_handler.py` uses `async for db_session in get_db()` instead of `async with`

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/_chat_handler.py:119`

**Description:** The audit helper in `_chat_handler.py` creates DB sessions by iterating the `get_db()` async generator:

```python
async for db_session in get_db():
    await write_audit_event(db_session, ...)
    await db_session.commit()
```

This is different from every other module, which uses either `Depends(get_db)` (routes) or `async with SessionLocal()` (tools/services). The `async for` pattern works but bypasses the generator's `finally` block cleanup semantics in edge cases (if the loop body raises after commit but before the generator is exhausted, cleanup timing differs from `async with`).

More importantly, a new DB session is created for every single audit event. In a busy chat, this opens a new connection, writes one row, and closes it -- repeated for every streamed token event that triggers audit. This is inefficient.

**Recommendation:** Use `async with SessionLocal() as session:` directly, matching the pattern used by `borrower_tools.py`. Or batch audit writes at the end of each message exchange rather than per-event.

---

## CR-06: `callable` used as type annotation instead of `Callable`

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/intake.py:117` and `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/intake_validation.py:173`

**Description:** Both files use lowercase `callable` as a type annotation in dict type hints:

```python
REQUIRED_FIELDS: dict[str, tuple[str, str, callable]] = { ... }
_VALIDATORS: dict[str, callable] = { ... }
```

`callable` is a built-in function, not a type. While it works at runtime (Python doesn't enforce annotations), static type checkers like mypy and pyright will flag this. The correct type annotation is `Callable` from `collections.abc` or `typing`.

**Recommendation:** Replace `callable` with `Callable` from `collections.abc`:

```python
from collections.abc import Callable

REQUIRED_FIELDS: dict[str, tuple[str, str, Callable]] = { ... }
```

---

## CR-07: `build_graph` is fully duplicated between public and borrower assistants

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/public_assistant.py:19-50` and `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_assistant.py:38-85`

**Description:** The `build_graph()` functions in `public_assistant.py` and `borrower_assistant.py` are structurally identical -- they differ only in the tools list. Both:

1. Extract `system_prompt` from config
2. Build `tool_descriptions` the same way
3. Extract `tool_allowed_roles` from YAML identically
4. Create `llms` dict identically (same loop, same call signature)
5. Call `build_routed_graph()` with the same structure

This is 30+ lines of boilerplate duplicated verbatim. With Phase 3 adding a loan-officer assistant, this will become three copies. With Phase 4 adding an underwriter assistant, four.

**Recommendation:** Extract a generic `build_agent_graph(config, tools, checkpointer)` helper that handles steps 1-5. Each agent module then becomes a one-liner defining its tools list.

---

## CR-08: Repeated application scope-check boilerplate in condition service

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/condition.py:43-55`, `94-104`, `161-171`, `230-240`

**Description:** The condition service has four functions (`get_conditions`, `respond_to_condition`, `link_document_to_condition`, `check_condition_documents`), and each one starts with the exact same 12-line block:

```python
app_stmt = (
    select(Application)
    .options(selectinload(Application.application_borrowers).joinedload(...))
    .where(Application.id == application_id)
)
app_stmt = apply_data_scope(app_stmt, user.data_scope, user)
app_result = await session.execute(app_stmt)
app = app_result.unique().scalar_one_or_none()
if app is None:
    return None
```

This is copy-pasted four times. The same pattern appears in `completeness.py`, `rate_lock.py`, and `status.py`. It is the most repeated code block in the codebase.

**Recommendation:** Extract a `verify_application_access(session, user, application_id) -> Application | None` helper into `scope.py` or a new `services/access.py`. All services call this one function.

---

## CR-09: `_DISCLOSURE_BY_ID` imported inside loop body (repeated imports)

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:337,346`

**Description:** In the `disclosure_status` tool, `_DISCLOSURE_BY_ID` is imported from `services.disclosure` inside two separate loop bodies:

```python
for d_id in result["acknowledged"]:
    from ..services.disclosure import _DISCLOSURE_BY_ID    # imported per iteration
    label = _DISCLOSURE_BY_ID.get(d_id, {}).get("label", d_id)

# ... then again:
for d_id in result["pending"]:
    from ..services.disclosure import _DISCLOSURE_BY_ID    # imported per iteration again
```

While Python caches module imports so this doesn't cause a performance issue, placing an import statement inside a loop body is confusing to readers and suggests the author thought a fresh import was needed each iteration. The import is also already done at the top of `acknowledge_disclosure` (line 284), showing inconsistency within the same file.

**Recommendation:** Move the import to the top of the file alongside the other `disclosure` imports, or at minimum to the function's top level.

---

## CR-10: `from sqlalchemy import func` imported inline inside route handler

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/applications.py:397`

**Description:** The `remove_borrower` route handler has an inline `from sqlalchemy import func` import on line 397, despite `func` being available at the module level via `from sqlalchemy import select` (which is already imported). The `func` import should be at the top of the file.

This is a sign the function was added later and the import was placed lazily rather than at the module level.

**Recommendation:** Move `from sqlalchemy import func` to the module-level imports alongside `select`.

---

## CR-11: `_resolve_role` inefficient set construction

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/middleware/auth.py:116-117`

**Description:** `_resolve_role` builds a set of known role values on every invocation:

```python
known = set(UserRole.__members__.values())
user_roles = [r for r in roles if r in {role.value for role in known}]
```

This creates two temporary sets per request: `set(UserRole.__members__.values())` (which is a set of enum members) and then `{role.value for role in known}` (a set comprehension extracting the string values). The first set `known` is unused except to iterate it immediately in the inner comprehension. This could be simplified to a single module-level constant:

```python
_KNOWN_ROLE_VALUES = {role.value for role in UserRole}
```

**Recommendation:** Define `_KNOWN_ROLE_VALUES` as a module-level constant and reference it in `_resolve_role`.

---

## CR-12: Incomplete return type annotations on route handlers

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/applications.py:226` and `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/documents.py:177` and `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/borrower_chat.py:71`

**Description:** Several route handlers return `dict` without a more specific type or response_model:

- `respond_condition` (applications.py:226) returns `{"data": result}` with no return type annotation and no `response_model`
- `get_document_content` (documents.py:173-192) returns `dict` with return annotation `-> dict`
- `get_conversation_history` (borrower_chat.py:71) returns `-> dict`

These are untyped response shapes that bypass FastAPI's serialization validation. The OpenAPI docs will show `object` with no schema, making API consumers guess at the response format.

**Recommendation:** Define Pydantic response models for these endpoints, or at minimum use `response_model` with inline models. This matters more as Phase 3 adds loan-officer facing endpoints that will consume these.

---

## CR-13: `financials` relationship ambiguity on Application model

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:91-93`

**Description:** The Application model has `financials = relationship(..., uselist=False)`, treating it as a one-to-one relationship. But `ApplicationFinancials` is keyed on `(application_id, borrower_id)` via a unique constraint, meaning there can be multiple financials rows per application (one per borrower). With `uselist=False`, SQLAlchemy will silently return only one row (and warn on duplicates).

This works today because the intake service only creates financials for the primary borrower, but Phase 3 (Loan Officer) will likely need to manage co-borrower financials, at which point this relationship will silently drop data.

**Recommendation:** Either change to `uselist=True` (and update all callers that treat `app.financials` as a single object) or add a comment documenting the intentional constraint and plan for Phase 3.

---

## CR-14: Admin auth secret key regenerated on every application restart

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/admin.py:215`

**Description:** `setup_admin` generates a new session secret key on every call:

```python
auth_backend = AdminAuth(secret_key=secrets.token_urlsafe(32))
```

This means every server restart invalidates all admin sessions. In development with `--reload`, this happens on every file save. While not a bug (sessions should be ephemeral in dev), it creates unnecessary friction during development and would be a problem if admin sessions needed to survive deployments.

**Recommendation:** Source the secret key from settings (e.g., a `SQLADMIN_SECRET_KEY` env var) with a fallback to random generation for dev.

---

## CR-15: `verify_audit_chain` loads entire audit table into memory

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/audit.py:97-99`

**Description:** `verify_audit_chain()` fetches all audit events into memory at once:

```python
stmt = select(AuditEvent).order_by(AuditEvent.id.asc())
result = await session.execute(stmt)
events = list(result.scalars().all())
```

This is fine at 564 tests / small demo data, but the audit table grows with every chat message, tool invocation, and disclosure acknowledgment. A demo session with 100 messages could add 500+ audit events. After a few days of demo usage, this query could return thousands of rows, consuming significant memory.

**Recommendation:** Implement streaming/chunked verification that processes rows in batches (e.g., 1000 at a time), carrying the `prev_hash` between batches.

---

## CR-16: Inconsistent response envelope patterns across endpoints

**Severity:** Warning
**Location:** Multiple routes

**Description:** The API has three different response envelope patterns:

1. **Wrapped with data+count** -- `ApplicationListResponse`, `DocumentListResponse`, `ConditionListResponse` use `{"data": [...], "count": N}`
2. **Wrapped with data only** -- `respond_condition` (applications.py:240) returns `{"data": result}`, `get_conversation_history` returns `{"data": messages}`
3. **Raw object/dict** -- `get_document_content` returns `{"file_path": ...}`, admin endpoints return model instances directly, `get_rate_lock` returns `RateLockResponse(**result)`

Per `api-conventions.md`, the project's own convention says: "Single resource: `{ "data": { ... } }`; Collection: `{ "data": [...], "pagination": { ... } }`". Several endpoints don't follow this convention.

**Recommendation:** Standardize on the documented envelope pattern. At minimum, catalog which endpoints deviate so Phase 3 endpoints can be consistent from the start.

---

## CR-17: `_DOC_TYPE_LABELS` exported from completeness service to agent tools

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:22`

**Description:** `borrower_tools.py` imports `_DOC_TYPE_LABELS` (underscore-prefixed, i.e., private) from `services.completeness`. This is the same pattern as CR-04 -- private symbols used across module boundaries.

**Recommendation:** Either make it public (`DOC_TYPE_LABELS`) since it's part of the cross-module API, or re-export it from the service's `__init__`.

---

## CR-18: `asyncio.create_task` without task reference creates fire-and-forget with no error visibility

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/documents.py:98`

**Description:** The document upload handler fires off the extraction pipeline as a background task:

```python
asyncio.create_task(extraction_svc.process_document(doc.id))
```

The task reference is discarded. If the extraction fails with an unhandled exception after the try/except in `ExtractionService.process_document`, the exception is logged but the task object is garbage-collected. In Python 3.11+, this triggers a "Task exception was never retrieved" warning.

More importantly, if the event loop shuts down while extraction is in progress, the task is cancelled without cleanup. The document stays in `PROCESSING` status permanently (zombie state).

**Recommendation:** Store the task reference and add a `done_callback` for error logging, or use a proper background task queue (even a simple `asyncio.TaskGroup` managed via lifespan).

---

## CR-19: `_user_context_from_state` fabricates email and name from user_id

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:46-57`

**Description:** The helper constructs a `UserContext` with fabricated fields:

```python
email=f"{user_id}@summit-cap.local",
name=user_id,
```

While this works because the downstream services only use `user_id` and `data_scope` for authorization, it creates a `UserContext` with fake PII. If any future code logs the `UserContext` or includes the email in audit events, it will contain misleading data.

**Recommendation:** Document that this `UserContext` is for authorization only, or pass the real email/name through the agent state.

---

## CR-20: `get_remaining_fields` re-queries Application that caller already loaded

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/intake.py:260,270-304`

**Description:** In `update_application_fields`, the function loads the application at the top (line 200-207), then at the end calls `get_remaining_fields` (line 260) which loads the same application again with the same scope check. This is two round-trips for the same data within one service call.

**Recommendation:** Refactor `get_remaining_fields` to accept the already-loaded `app`, `borrower`, and `financials` objects, or compute remaining fields inline.

---

## CR-21: `Application.financials` eager-loaded inconsistently

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/intake.py:202-203,276-279`

**Description:** `update_application_fields` loads `Application` with `.options(selectinload(Application.financials))` (line 203), but then separately queries for financials via `_get_or_create_financials` (line 215) which does its own `select(ApplicationFinancials)` query. The eager-loaded relationship is never used, wasting a query.

Similarly, `get_remaining_fields` (line 279) eager-loads `Application.financials` but then accesses it as `app.financials` (line 288) without checking if the eager load actually populated it.

**Recommendation:** Either use the eager-loaded relationship consistently or drop the `selectinload` option and always query separately.

---

## CR-22: `db_service` in `database.py` uses `globals()['engine']` for default

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/database.py:40`

**Description:** The `DatabaseService.__init__` uses `globals()['engine']` as a default:

```python
def __init__(self, engine=None):
    self.engine = engine or globals()['engine']
```

Using `globals()` for default argument resolution is unusual and fragile. If the module is restructured or `engine` is renamed, this breaks at runtime with a `KeyError` rather than at import time with a `NameError`.

**Recommendation:** Use `engine` directly:

```python
def __init__(self, engine=None):
    self.engine = engine or _default_engine
```

Or reference the module-level `engine` variable directly without `globals()`.

---

## CR-23: No validation that `fields` argument is a JSON string in `update_application_data` tool

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:598-622`

**Description:** The `update_application_data` tool accepts `fields` as a `str` parameter that the LLM is expected to produce as a JSON string. The docstring says to pass JSON, but the tool's type annotation is just `str`. If the LLM passes a non-JSON string (which happens with weaker models), `json.loads` fails and returns a generic error.

More concerning: the `fields` parameter is a raw string that gets `json.loads`'d inside the tool. This is an unusual pattern -- LangChain tools normally accept structured parameters (dicts, individual args) rather than asking the LLM to produce JSON-within-JSON.

**Recommendation:** Consider restructuring the tool to accept individual parameters, or at minimum accept `dict` as the type annotation if the LLM framework supports it. This reduces the chance of malformed JSON from the LLM.

---

## CR-24: `_TERMINAL_STAGES` defined twice with different types

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/intake.py:27-31` and `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/status.py:90-94`

**Description:** Terminal stages are defined in two places with different value types:

In `intake.py`:
```python
_TERMINAL_STAGES = {ApplicationStage.WITHDRAWN, ApplicationStage.DENIED, ApplicationStage.CLOSED}
```
(Set of enum members)

In `status.py`:
```python
_TERMINAL_STAGES = {ApplicationStage.CLOSED.value, ApplicationStage.DENIED.value, ApplicationStage.WITHDRAWN.value}
```
(Set of string values)

If a new terminal stage is added (e.g., `CANCELLED`), it must be added to both sets. If only one is updated, behavior diverges silently.

**Recommendation:** Define `TERMINAL_STAGES` once as a module-level constant in `db/enums.py` (since it's a domain concept) and import it in both services.

---

## CR-25: `_RESOLVED_CONDITION_STATUSES` compared with `.value` inconsistently

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/status.py:96-99,138`

**Description:** `_RESOLVED_CONDITION_STATUSES` is defined as a set of `.value` strings:

```python
_RESOLVED_CONDITION_STATUSES = {ConditionStatus.CLEARED.value, ConditionStatus.WAIVED.value}
```

But the query uses `Condition.status.notin_([s for s in _RESOLVED_CONDITION_STATUSES])`. This works because `ConditionStatus` is a `str` enum, so `.value` returns the raw string, and SQLAlchemy can compare against strings. But it's inconsistent with how other services use enum members directly (e.g., `condition.py:61` uses `ConditionStatus.OPEN` directly in `.in_()`). This inconsistency will trip up developers who expect enums to be used as enums throughout.

**Recommendation:** Use enum members consistently. Either always use `.value` for SQL comparisons or rely on SQLAlchemy's enum handling throughout.

---

## CR-26: Multiple `build_graph` functions have identical LLM initialization

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/public_assistant.py:34-41` and `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_assistant.py:69-75`

**Description:** Both `build_graph` functions create their `llms` dict with identical code:

```python
llms: dict[str, ChatOpenAI] = {}
for tier in get_model_tiers():
    model_cfg = get_model_config(tier)
    llms[tier] = ChatOpenAI(
        model=model_cfg["model_name"],
        base_url=model_cfg["endpoint"],
        api_key=model_cfg.get("api_key", "not-needed"),
    )
```

This is a subset of the duplication noted in CR-07, but worth calling out specifically because the LLM initialization should be centralized -- if a new parameter is needed (e.g., `timeout`, `max_retries`), it needs to be updated in every agent module.

**Recommendation:** Extract `build_llms() -> dict[str, ChatOpenAI]` into `inference/config.py` alongside the existing tier configuration functions.

---

## CR-27: `seed.py` exists at module root but is not referenced

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/seed.py`

**Description:** `seed.py` exists alongside `main.py` at the package root, but the actual seeding logic is in `services/seed/seeder.py` and exposed via the admin route. Let me verify whether `seed.py` is still used.

**Recommendation:** If `seed.py` is superseded by `services/seed/seeder.py`, remove it to avoid confusion about which is the canonical seeding entry point.

---

## CR-28: `disclosure_status` tool does not enforce data scope

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:310-351`

**Description:** The `disclosure_status` tool calls `get_disclosure_status(session, application_id)` without passing the user context. Looking at `services/disclosure.py:55-97`, the function only takes `session` and `application_id` -- it does not verify that the calling user has access to the application. It queries `audit_events` by `application_id` without any scope check.

Compare this with every other borrower tool, which calls `_user_context_from_state(state)` and passes the user through scope-checked service functions. `disclosure_status` is the only tool that skips the access check.

In practice, the borrower assistant agent only knows about application IDs the borrower owns (from `start_application`), so exploitation requires the LLM to hallucinate an arbitrary application ID. But this is still a gap in the defense-in-depth pattern.

**Recommendation:** Add data scope verification to `get_disclosure_status` by requiring a `UserContext` parameter and verifying application access before querying audit events.

---

## CR-29: Inconsistent import style for `SessionLocal` in borrower tools

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:13`

**Description:** `borrower_tools.py` imports `SessionLocal` from `db.database` (the internal module):

```python
from db.database import SessionLocal
```

Every other module in the codebase imports from the `db` package's public API (`from db import get_db`, etc.). The `db/__init__.py` does not export `SessionLocal` (only `get_db`), which means `borrower_tools.py` is reaching past the public interface to access an internal.

This works, but it couples the tools module to the db package's internal structure rather than its public API.

**Recommendation:** Either export `SessionLocal` from `db/__init__.py` (since it's clearly needed as a public API for non-FastAPI contexts) or add a public function like `get_session_factory()` to the db package.

---

## CR-30: Response envelope for `respond_condition` is ad-hoc

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/applications.py:240`

**Description:** The `respond_condition` endpoint returns `{"data": result}` where `result` is an untyped dict from the service layer. This endpoint has no `response_model` parameter, so FastAPI doesn't validate the response shape and OpenAPI docs show an untyped response.

**Recommendation:** Define a `ConditionRespondResponse` Pydantic model and add it as `response_model`.

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 1 |
| Warning | 11 |
| Info | 18 |

The codebase is well-structured overall with clean separation between routes, services, and agents. The most impactful finding is CR-01 (quality_flags JSON/CSV mismatch) which is a data integrity bug. The warning-level findings cluster around three themes: **code duplication** (CR-02, CR-03, CR-07, CR-08, CR-24, CR-26), **inconsistent patterns** (CR-04, CR-05, CR-16, CR-25), and **missing validation/scope checks** (CR-06, CR-15, CR-18, CR-23, CR-28). These should be addressed before Phase 3 implementation to prevent the patterns from proliferating further.
