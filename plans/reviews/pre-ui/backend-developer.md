# Backend Developer Review -- Pre-UI

**Scope:** `packages/api/src/routes/`, `packages/api/src/middleware/`, `packages/api/src/main.py`

**Focus:** Route handler correctness, middleware behavior and ordering, async patterns, session
management, error handling, FastAPI dependency injection, response model consistency.

---

## Critical

### BE-01: `audit_export` writes audit event without user identity

**File:** `packages/api/src/routes/audit.py:187`

`write_audit_event` is called without `user_id` or `user_role`, meaning the "data_access"
audit record for every export has null identity fields. This defeats the audit trail for one
of the most security-sensitive operations in the system (bulk data export).

The endpoint uses `require_roles` in `dependencies=` but does not inject `CurrentUser` into
the function signature, so the user context is not available. This is a structural gap.

**Fix:** Add `user: CurrentUser` to the function signature and pass `user_id=user.user_id`
and `user_role=user.role.value` to `write_audit_event`.

```python
async def audit_export(
    ...,
    session: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(),
) -> Response:
    ...
    await write_audit_event(
        session,
        event_type="data_access",
        user_id=user.user_id,
        user_role=user.role.value,
        event_data={...},
    )
```

---

### BE-02: `audit_export` has no `response_model` -- PII masking bypasses CSV export

**File:** `packages/api/src/routes/audit.py:163`, `packages/api/src/middleware/pii.py:111`

The `audit_export` endpoint returns `Response` with `media_type="text/csv"` for CSV exports.
`PIIMaskingMiddleware` only applies masking when `content_type` contains `"application/json"`.
A CEO requesting CSV export receives raw, unmasked SSN and DOB values in the CSV file, which
contradicts the docstring comment `"PII masking is applied by the PIIMaskingMiddleware for CEO
role"`.

This is a real data leak path: CEO role is explicitly permitted to export, and the docstring
asserts masking is applied, but it is not applied for CSV.

**Fix:** Either (a) apply CSV-specific PII masking in `export_events()` before returning,
or (b) extend `PIIMaskingMiddleware` to handle CSV media type, or (c) restrict export to
JSON only for CEO role and handle CSV masking in the export service.

---

## Warning

### BE-03: `PIIMaskingMiddleware` copies response headers including stale `Content-Length`

**File:** `packages/api/src/middleware/pii.py:130`

When PII masking rewrites the response body, the new body may be a different size than the
original (masked strings like `"***-**-1234"` are longer than raw values). However, the
middleware passes the original response headers verbatim via `dict(response.headers)`. If the
original response included a `Content-Length` header matching the unmasked body length, the
rebuilt `Response` will carry an incorrect `Content-Length`, which can cause client parsing
errors or truncated responses.

**Fix:** Strip or update `Content-Length` in the headers dict after rewriting the body:

```python
headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
return Response(
    content=new_body,
    status_code=response.status_code,
    headers=headers,
    media_type=response.media_type,
)
```

---

### BE-04: `get_decision` re-fetches all decisions then filters in Python

**File:** `packages/api/src/routes/decisions.py:76`

`get_decision` calls `get_decisions(session, user, application_id)` which fetches all
decisions for the application, then linearly scans in Python to find the matching
`decision_id`. For applications with many decisions this is wasteful, but more importantly
the service signature has no single-record fetch path. The route should not be scanning
Python lists to resolve a primary-key lookup.

**Fix:** Add a `get_decision_by_id` service function that fetches the single record directly
by ID, with the RBAC scope check applied at the query level. The existing `get_decisions`
call in `list_decisions` is fine; only the `get_decision` route needs a targeted query.

---

### BE-05: `update_application` can silently return a stale `app` when both stage and fields are updated

**File:** `packages/api/src/routes/applications.py:367`

When a PATCH body contains both `stage` and other fields, `transition_stage` runs first (line
369) and `app` is set to the transitioned result. Then `update_application` runs (line 387)
and overwrites `app` with the field-updated result. However, if only `stage` is in the body
(`updates` is empty after `pop`), `app` remains the `transition_stage` result and the `if
updates:` block is skipped entirely. This is correct.

The real concern is when `transition_stage` fails: `app` is still `None` at the point the
`404` is raised (line 382). But if the outer `try/except` for `InvalidTransitionError` does
not catch a `None` return, and `update_application` is also called, `app` at line 399 would
be built from `update_application`'s return -- which re-fetches the pre-transition state.
Two separate service calls in one transaction create a window for inconsistency.

**Fix:** Validate that both operations share the same session and that the transition commit
happens before the field update, or merge both operations into a single service call.
For MVP, add a comment documenting the ordering dependency.

---

### BE-06: `create_authenticated_chat_router` closes WebSocket but does not `return` after sending error

**File:** `packages/api/src/routes/_chat_handler.py:307`

In the `chat_websocket` closure inside `create_authenticated_chat_router`, when agent loading
fails:

```python
await ws.send_json({"type": "error", "content": "..."})
await ws.close()
return
```

The `return` is present here (line 313), so this is handled. However, in the public chat
endpoint (`chat.py:41`), the same pattern is also present and handled. No bug. This note is
informational only and confirms the pattern is consistent.

---

### BE-07: `run_agent_stream` passes `messages_fallback` list by reference into concurrent scope

**File:** `packages/api/src/routes/_chat_handler.py:159`

When `use_checkpointer=False`, `messages_fallback` is a mutable list that accumulates all
conversation turns. On each loop iteration, `messages_fallback.append(HumanMessage(...))` is
called, then the full list is passed as `input_messages`. If the client sends a second message
before the first agent response completes (not guarded by any lock), both messages will be
appended before the second `astream_events` call, doubling the history sent to the LLM.

The WebSocket's single-consumer model limits concurrent message processing per connection in
practice (because `await ws.receive_text()` blocks), but there is no explicit guard and the
comment on the code does not document the implicit serialization assumption. If the
implementation changes, this breaks silently.

**Fix:** Document the serialization assumption with a comment explaining why concurrent
mutation is not a concern: "The outer `while True` loop awaits `receive_text()` which
serializes reads; the inner `astream_events` blocks until the response is complete before
the next `receive_text()` call."

---

### BE-08: Health endpoint uses fragile conditional `Depends` at function signature level

**File:** `packages/api/src/routes/health.py:25`

```python
async def health_check(
    db_service: DatabaseService | None = Depends(get_db_service) if get_db_service else None,
) -> list[HealthResponse]:
```

The `Depends(get_db_service) if get_db_service else None` expression is evaluated at import
time. If `get_db_service` is falsy (due to the import exception being caught on lines 12-16),
FastAPI receives `None` as the default, not a `Depends()`. This works but is fragile: FastAPI
will not inject anything for that parameter, meaning `db_service` is always `None` if the DB
package import fails -- which is the fallback intention. However, if `get_db_service` is a
truthy callable but the dependency itself raises at injection time, the exception will surface
uncaught.

More importantly, the bare `except Exception` on line 13 that silences all DB import errors
means misconfigured DB dependencies fail silently and health always reports only the API
component. This could mask real startup errors from operators.

**Fix:** Log the specific import exception at WARNING level inside the except block:

```python
except Exception as exc:
    logger.warning("DB package unavailable for health check: %s", exc)
    DatabaseService = None
    get_db_service = None
```

---

## Suggestion

### BE-09: `admin.seed_data` uses `status_code=HTTP_200_OK` for a POST that creates resources

**File:** `packages/api/src/routes/admin.py:19`

The `/admin/seed` POST endpoint returns `200 OK` instead of `201 Created`. While seeding is
idempotent in intent (it is a write operation that creates demo data), the project convention
(per `api-conventions.md`) is that POST endpoints that create resources return `201`. Using
`200` is inconsistent with other create endpoints in the codebase.

**Fix:** Change `status_code=status.HTTP_200_OK` to `status_code=status.HTTP_201_CREATED`
if the intent is resource creation, or rename the endpoint to reflect it as an action verb
(`/admin/seed/run` or keep as-is with a `200` and document the exception).

---

### BE-10: `get_document_content` endpoint name conflicts with its role as a path provider

**File:** `packages/api/src/routes/documents.py:192`

The endpoint is named `get_document_content` and returns `DocumentFilePathResponse` (which
is a file path, not content). The URL is `/documents/{id}/content` but the response is a
path string. This creates a semantic mismatch that will confuse UI developers integrating the
endpoint: they expect binary content or a download URL, but receive a filesystem path string.

**Fix:** Either rename to `get_document_path` with a URL of `/documents/{id}/path`, or
change the response to return a presigned URL / download link to the actual content. At MVP,
documenting the intent clearly in the docstring is the minimum fix.

---

### BE-11: `models_monitoring` sub-endpoints each call `_safe_summary` redundantly

**File:** `packages/api/src/routes/model_monitoring.py:60,76,93,109`

Each of the four sub-endpoints (`/latency`, `/tokens`, `/errors`, `/routing`) calls
`_safe_summary(hours, model)` which fetches the full `ModelMonitoringSummary` from LangFuse,
then returns only one field from it. A client fetching all four metrics makes four separate
LangFuse API calls. This is a read-throughput concern but also means four potential
503 responses for one logical dashboard load.

For MVP this is acceptable. At production, the summary should be fetched once and all
sub-responses derived from it (or sub-endpoints removed in favor of the single summary
endpoint).

**Fix:** Add a comment to `_safe_summary` noting the N-call amplification for sub-endpoints,
or deprecate the sub-endpoints and direct UI consumers to the `/model-monitoring` summary
endpoint.
