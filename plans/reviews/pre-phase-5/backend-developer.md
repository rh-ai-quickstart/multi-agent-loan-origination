# Pre-Phase 5 Backend Review

**Reviewer:** Backend Developer
**Date:** 2026-02-27
**Scope:** `packages/api/src/` (services, routes, agents, middleware, inference)
**Verdict:** REQUEST_CHANGES

---

## 1. Async Correctness

### [BE-01] Critical -- Blocking synchronous PDF operations in async context

**File:** `packages/api/src/services/extraction.py` lines 175-205

`_extract_text_from_pdf` and `_pdf_first_page_to_image` are synchronous methods that call `fitz.open()` (pymupdf) for CPU-intensive PDF parsing and image rendering. These are called from the async `_process_pdf` method (line 159, 169) which runs inside an `async` pipeline triggered by `asyncio.create_task`. This blocks the event loop for the duration of the PDF operation.

The `storage.py` module already demonstrates the correct pattern -- wrapping synchronous boto3 calls in `loop.run_in_executor()`. The extraction methods should follow the same approach.

**Suggested fix:** Wrap both methods with `asyncio.get_running_loop().run_in_executor(None, ...)` or refactor them as standalone functions dispatched to the default executor.

### [BE-02] Warning -- Synchronous `_ensure_bucket()` in StorageService constructor

**File:** `packages/api/src/services/storage.py` lines 55-63

`_ensure_bucket()` calls `self._client.head_bucket()` and potentially `self._client.create_bucket()` -- both synchronous HTTP calls to MinIO. This runs during `__init__`, which is called from `init_storage_service()` during the async app lifespan handler. While the lifespan itself may tolerate brief blocking, this is inconsistent with the async-first pattern used by `upload_file` and `download_file` in the same class.

**Suggested fix:** Make `_ensure_bucket` async and call it explicitly after construction, or wrap the boto3 calls in `run_in_executor`.

### [BE-03] Warning -- Synchronous `response["Body"].read()` after async executor dispatch

**File:** `packages/api/src/services/storage.py` line 92

`download_file` correctly dispatches `get_object` to the executor, but `response["Body"].read()` runs synchronously on the event loop thread after the executor returns. For large files, this blocks the event loop while reading the full response body from the HTTP stream. The entire download (including body read) should happen within the executor.

**Suggested fix:** Move the `.read()` call into the executor by wrapping the full get-and-read sequence:

```python
def _download_sync(self, object_key: str) -> bytes:
    response = self._client.get_object(Bucket=self._bucket, Key=object_key)
    return response["Body"].read()
```

### [BE-04] Warning -- Synchronous file I/O in KB ingestion

**File:** `packages/api/src/services/compliance/knowledge_base/ingestion.py` line 176

`md_file.read_text()` is synchronous filesystem I/O. In practice, KB ingestion is a one-time admin operation (not on the hot path), so the impact is low. However, if multiple files are ingested in sequence, the cumulative blocking time on the event loop could be noticeable.

**Suggested fix:** Low priority. If ingestion is ever exposed as a user-triggered operation, wrap in `run_in_executor`.

### [BE-05] Warning -- `verify_audit_chain` loads entire audit table into memory

**File:** `packages/api/src/services/audit.py` lines 97-99

`verify_audit_chain` executes `select(AuditEvent).order_by(AuditEvent.id.asc())` and materializes every row into a Python list. After 4 phases of development with frequent audit writes per tool invocation, this table will grow unbounded. At scale, this will OOM or time out.

**Suggested fix:** Use windowed/chunked iteration with `yield_per()` or `stream_scalars()` to process rows in batches, keeping only the previous event's hash in memory at any time. Alternatively, use `server_side_cursors=True` with the async session.

---

## 2. Session Handling

### [BE-06] Warning -- `_chat_handler._audit` creates session via `get_db()` generator protocol

**File:** `packages/api/src/routes/_chat_handler.py` lines 119-132

The `_audit` helper iterates over the `get_db()` async generator to obtain a session:

```python
async for db_session in get_db():
    await write_audit_event(...)
    await db_session.commit()
```

This works but is fragile. The `get_db()` generator yields once and then runs cleanup in its `finally` block. Using `async for` with a generator that yields exactly once is non-obvious and will confuse future readers. More importantly, if `write_audit_event` acquires the advisory lock and then the commit fails, the generator's cleanup will close the session, but the advisory lock release depends on transaction completion.

**Suggested fix:** Use `SessionLocal()` context manager directly (the pattern already used in all agent tools):

```python
async with SessionLocal() as db_session:
    await write_audit_event(...)
    await db_session.commit()
```

### [BE-07] Suggestion -- Inconsistent session sourcing across agent tools vs. routes

Agent tools (borrower_tools, loan_officer_tools, underwriter_tools, condition_tools, decision_tools, compliance_check_tool) all use `SessionLocal()` context manager for session-per-tool-call. Routes use `Depends(get_db)` for request-scoped sessions. Services accept `AsyncSession` as a parameter. This is actually correct for the respective contexts (tools run outside HTTP request scope, routes are request-scoped), but it is worth documenting the rationale so future contributors do not accidentally mix patterns.

**Suggested fix:** Add a brief comment in `base.py` or a docstring in the agents module explaining why tools use `SessionLocal()` instead of the FastAPI dependency.

---

## 3. Error Propagation

### [BE-08] Warning -- `HTTPException` raised from service layer in `application.py`

**File:** `packages/api/src/services/application.py` lines 187-193

`transition_stage` raises `HTTPException(status_code=422)` when an invalid stage transition is requested. This couples the service layer to FastAPI's HTTP transport. If this service function is ever called from an agent tool (which uses its own session and has no HTTP context), the exception will be semantically wrong.

The condition and decision services handle the same pattern differently -- they return `{"error": "..."}` dicts. Neither pattern is ideal, but they should at least be consistent.

**Suggested fix:** Raise a domain exception (e.g., `InvalidTransitionError`) and let the route handler convert it to an HTTP 422. This matches the existing pattern where route handlers map None returns to 404.

### [BE-09] Warning -- `_resolve_role` raises `HTTPException` from auth utility

**File:** `packages/api/src/middleware/auth.py` lines 121-124

`_resolve_role` raises `HTTPException(403)` when no recognized role is found. This function is imported and called from `_chat_handler.py` (line 63) in a WebSocket context, where `HTTPException` is not the right exception type (WebSocket connections do not return HTTP responses).

The `_chat_handler.py` works around this with a bare `except Exception:` at line 64, but this masks the actual problem. If `_resolve_role` raised a `ValueError` instead, the caller could handle it appropriately for its context.

**Suggested fix:** Have `_resolve_role` raise `ValueError` (or a custom `NoRoleError`). The HTTP dependency `get_current_user` can catch it and raise `HTTPException`. The WebSocket handler can catch it and close the connection with an appropriate code.

### [BE-10] Warning -- Bare `except Exception` in chat handler swallows all errors

**File:** `packages/api/src/routes/_chat_handler.py` line 252

The outer try/except in `run_agent_stream` catches all exceptions as client disconnection:

```python
except Exception:
    logger.debug("Client disconnected from chat")
```

This catches `WebSocketDisconnect` (correct) but also catches programming errors like `AttributeError`, `TypeError`, `KeyError`, etc. These should propagate or at least be logged at a higher level than `debug`.

**Suggested fix:** Catch `WebSocketDisconnect` (from starlette) explicitly. Log any other exception at `warning` or `error` level before returning.

### [BE-11] Warning -- Silent audit write failures in chat handler

**File:** `packages/api/src/routes/_chat_handler.py` line 131

When `_audit()` fails, the exception is logged at `warning` level and swallowed. The chat continues without the audit record. For an application that demonstrates compliance patterns (HMDA, ECOA, audit trails), silently dropping audit events undermines the integrity guarantee.

**Suggested fix:** At minimum, log at `error` level. Consider sending a non-fatal status message to the client indicating that audit recording failed, so the operator is aware.

### [BE-12] Suggestion -- Inconsistent error return pattern across services

The condition service (`condition.py`) and decision service (`decision.py`) return `{"error": "..."}` dicts for business rule violations, while `application.py` raises `HTTPException`. This inconsistency means callers must check for different error shapes depending on which service they call.

**Files affected:**
- `packages/api/src/services/condition.py` -- returns `{"error": "..."}` (lines 332, 394, 441, 490, 498, 554)
- `packages/api/src/services/decision.py` -- returns `{"error": "..."}` (similar pattern)
- `packages/api/src/services/application.py` -- raises `HTTPException` (line 187)

**Suggested fix:** Standardize on domain exceptions (e.g., `BusinessRuleViolation`) across all services. Route handlers and agent tools can then translate these into their respective error formats (HTTP 422 or error message in tool output).

---

## 4. Service Layer Quality

### [BE-13] Warning -- Business logic in route handler: `add_borrower` and `remove_borrower`

**File:** `packages/api/src/routes/applications.py` lines 404-509

Both `add_borrower` and `remove_borrower` contain significant business logic directly in the route handler:

- Borrower existence check (line 419-424)
- Duplicate junction row check (line 427-437)
- Minimum borrower count enforcement (lines 486-496)
- Primary borrower removal guard (lines 498-503)

These validations and state changes should live in a service function (e.g., `application.add_borrower()`, `application.remove_borrower()`). Route handlers should validate input, call the service, and format the response.

Additionally, `remove_borrower` has an inline import `from sqlalchemy import func` at line 487, which is already imported at the module level in the service files.

**Suggested fix:** Extract both operations into `services/application.py`. The route handler calls the service and maps the result.

### [BE-14] Warning -- `_user_context_from_state` duplicated in 6 agent tool files

**Files:**
- `packages/api/src/agents/borrower_tools.py` line 55
- `packages/api/src/agents/loan_officer_tools.py` line 66
- `packages/api/src/agents/underwriter_tools.py` line 34
- `packages/api/src/agents/condition_tools.py` line 38
- `packages/api/src/agents/decision_tools.py` line 36
- `packages/api/src/agents/compliance_check_tool.py` line 46

The same function is copy-pasted across all 6 tool modules. Any change to the UserContext construction requires updating 6 files.

**Suggested fix:** Extract to a shared utility, e.g., `agents/_utils.py` or add to `agents/base.py`, and import from there.

### [BE-15] Suggestion -- Borrower lookup pattern duplicated 3 times in `decision_tools.py`

**File:** `packages/api/src/agents/decision_tools.py` lines 311-322, 431-442, 586-597

Three tool functions (`uw_propose_decision`, `uw_render_decision`, `uw_get_decision_history`) each contain identical code to query `ApplicationBorrower` and then `Borrower` for the primary borrower. This is a local duplication within a single file.

**Suggested fix:** Extract to a private helper like `_get_primary_borrower(session, application_id)`.

### [BE-16] Suggestion -- Condition service returns raw dicts instead of typed models

**File:** `packages/api/src/services/condition.py`

All condition service functions return `dict | None`. The dict keys are constructed inline (lines 71-86, 138-143, 193-198, etc.) with no schema validation. This makes it easy for typos or missing keys to slip through, and callers cannot use IDE autocompletion.

Other services (e.g., `application.py`) return ORM objects that the route layer converts to Pydantic models. The condition service should follow the same pattern or return Pydantic models directly.

**Suggested fix:** Return `Condition` ORM objects (like `application.py`) or define service-layer Pydantic models. Let the route layer handle serialization.

### [BE-17] Suggestion -- Private name `_DOC_TYPE_LABELS` imported across module boundary

**File:** `packages/api/src/agents/borrower_tools.py` line 30

```python
from ..services.completeness import _DOC_TYPE_LABELS, check_completeness
```

The leading underscore convention signals "module-private, not part of public API." Importing it from another module breaks encapsulation. If `completeness.py` refactors this mapping, borrower_tools will break silently.

**Suggested fix:** Either rename to `DOC_TYPE_LABELS` (no underscore) to signal it is part of the public API, or expose a helper function that performs the label lookup.

---

## 5. WebSocket Handling

### [BE-18] Warning -- No message size limit on WebSocket receive

**File:** `packages/api/src/routes/_chat_handler.py` line 136

`await ws.receive_text()` accepts messages of arbitrary length. A malicious client could send a multi-megabyte message, consuming server memory during JSON parsing and agent invocation. This applies to all 4 chat endpoints (public, borrower, LO, underwriter).

**Suggested fix:** Check `len(raw)` after receive and reject messages exceeding a reasonable limit (e.g., 10KB for chat messages). Send an error JSON and `continue`.

### [BE-19] Warning -- No receive timeout on WebSocket

**File:** `packages/api/src/routes/_chat_handler.py` line 136

`await ws.receive_text()` blocks indefinitely on a stale connection. If a client opens a WebSocket and never sends a message (or becomes unresponsive), the coroutine holds the connection and associated resources forever until TCP keepalive eventually closes it.

**Suggested fix:** Wrap with `asyncio.wait_for(ws.receive_text(), timeout=300)` (5-minute idle timeout). On `asyncio.TimeoutError`, send a timeout message and close the connection.

### [BE-20] Suggestion -- No rate limiting on WebSocket messages

**File:** `packages/api/src/routes/_chat_handler.py` line 135 (the while loop)

A client can send messages as fast as the network allows. Each message triggers an LLM invocation (which may have cost implications) and multiple audit writes. There is no per-connection rate limiting.

**Suggested fix:** Track message timestamps per connection and enforce a minimum interval (e.g., 1 message per second) or a sliding window limit (e.g., 20 messages per minute). This is an MVP-level concern since each LLM call has real cost.

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 1 |
| Warning | 14 |
| Suggestion | 5 |

The most impactful finding is [BE-01] (blocking PDF operations on the event loop), which will degrade throughput for all concurrent requests during document extraction. The service layer consistency issues ([BE-08], [BE-09], [BE-12], [BE-13]) are the next priority -- they create maintenance burden and will become harder to fix as more features build on top of the current patterns. The WebSocket hardening findings ([BE-18], [BE-19]) should be addressed before the system is exposed to untrusted clients.
