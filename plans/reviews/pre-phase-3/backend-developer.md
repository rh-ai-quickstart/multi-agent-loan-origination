# Backend Implementation Review -- Pre-Phase 3

Reviewer: Backend Developer
Date: 2026-02-26
Scope: All Python source in `packages/api/src/` (core, services, routes, agents, middleware, inference)

---

## BE-1: Synchronous blocking call in async auth middleware (`_fetch_jwks`)

**Severity:** Critical
**Location:** packages/api/src/middleware/auth.py:36
**Description:** `_fetch_jwks()` uses `httpx.get()` (synchronous) to call Keycloak's JWKS endpoint. This function is called from `_get_signing_key()`, which is called from `_decode_token()`, which is called from the `async def get_current_user()` FastAPI dependency. A synchronous HTTP call inside an async request handler blocks the entire event loop for the duration of the network round-trip (up to 5 seconds per the timeout). Under concurrent load, this serializes all authenticated requests through JWKS fetches.
**Recommendation:** Replace `httpx.get()` with `await httpx.AsyncClient().get()` (or use a module-level `httpx.AsyncClient` singleton). This requires making `_fetch_jwks`, `_get_jwks`, and `_get_signing_key` async, and `_decode_token` async, and propagating `await` to callers. Alternatively, use `asyncio.to_thread()` as a quick fix, but native async is preferred.

---

## BE-2: Synchronous blocking in `StorageService.__init__` at startup

**Severity:** Warning
**Location:** packages/api/src/services/storage.py:54
**Description:** `StorageService.__init__()` calls `self._ensure_bucket()`, which makes synchronous boto3 calls (`head_bucket`, `create_bucket`). This constructor is called from `init_storage_service()` which runs inside the `async def lifespan()` context manager. Synchronous I/O inside the async lifespan blocks the event loop during startup. While this only runs once at startup, it sets a bad pattern and could cause timeout issues if MinIO is slow to respond.
**Recommendation:** Either defer bucket creation to the first async call, or wrap `_ensure_bucket()` in `asyncio.to_thread()` during initialization. The existing `upload_file`/`download_file` methods already use `run_in_executor` correctly -- apply the same pattern to initialization.

---

## BE-3: `download_file` reads entire file body synchronously in executor callback

**Severity:** Warning
**Location:** packages/api/src/services/storage.py:91
**Description:** `download_file` runs `self._client.get_object(...)` in an executor, but then calls `response["Body"].read()` outside the executor context. The `get_object` API returns a StreamingBody; the `.read()` call happens back on the event loop thread (the `await` returns the response dict, and `.read()` is called synchronously on the result). This blocks the event loop while reading potentially large files.
**Recommendation:** Move the entire download + read sequence into the executor callback:
```python
def _download(key):
    response = self._client.get_object(Bucket=self._bucket, Key=key)
    return response["Body"].read()
await loop.run_in_executor(None, partial(_download, object_key))
```

---

## BE-4: Extraction service uses synchronous pymupdf in async context

**Severity:** Warning
**Location:** packages/api/src/services/extraction.py:175-204
**Description:** `_extract_text_from_pdf()` and `_pdf_pages_to_images()` call pymupdf's `fitz.open()`, `page.get_text()`, and `page.get_pixmap()` synchronously. These are CPU-bound and I/O-bound operations (parsing PDF data). They are called from `_process_pdf()` which is called from the async `process_document()` method. Since `process_document` runs as a background task via `asyncio.create_task()`, these blocking calls tie up the event loop thread during PDF processing.
**Recommendation:** Wrap the pymupdf calls in `asyncio.to_thread()` or `loop.run_in_executor()` to avoid blocking the event loop.

---

## BE-5: `verify_audit_chain` loads all audit events into memory

**Severity:** Warning
**Location:** packages/api/src/services/audit.py:97-99
**Description:** `verify_audit_chain()` fetches all audit events with `list(result.scalars().all())`. Over time, the audit trail will grow unboundedly. Loading the entire chain into memory for verification is an O(n) memory operation that will eventually cause OOM or extreme slowness. The endpoint is admin-only but could still be triggered by authorized users.
**Recommendation:** Process events in batches using windowed queries (e.g., fetch 1000 at a time, carry forward the last event's hash to compute the next batch's expected prev_hash). Alternatively, add a `limit` parameter to the verification endpoint so callers can verify the most recent N events.

---

## BE-6: `condition.py` parses `quality_flags` with `.split(",")` instead of `json.loads()`

**Severity:** Warning
**Location:** packages/api/src/services/condition.py:279
**Description:** In `check_condition_documents()`, quality flags are parsed as `doc.quality_flags.split(",")`. However, throughout the rest of the codebase (e.g., `extraction.py:90-91`, `extraction.py:127`, `completeness.py:270`), quality flags are stored as JSON arrays via `json.dumps(quality_flags)`. A JSON-encoded list like `["blurry", "incomplete"]` split by comma would produce `['["blurry"', ' "incomplete"]']` -- including the JSON brackets and extra quotes. This is an inconsistency that produces garbled quality flag display in condition satisfaction checks.
**Recommendation:** Change line 279 to: `"quality_flags": json.loads(doc.quality_flags) if doc.quality_flags else []`

---

## BE-7: `intake.py` accesses `app.financials` as scalar but model uses a list relationship

**Severity:** Warning
**Location:** packages/api/src/services/intake.py:288, 297, 406
**Description:** `get_remaining_fields()` and `get_application_progress()` access `app.financials` as if it were a scalar (`getattr(financials, column, None)`). However, `ApplicationFinancials` is a separate table joined via `application_id` and the `Application.financials` relationship is loaded with `selectinload(Application.financials)`. If this relationship is defined as a one-to-many (which is the SQLAlchemy default for a simple relationship), `app.financials` would be a list, not a single object. The code accesses it without indexing. If `Application.financials` is actually a `uselist=False` scalar relationship this is fine, but the code pattern (using `selectinload` without `[0]` or scalar access) suggests there may be a mismatch that would cause attribute errors or return None.
**Recommendation:** Verify the relationship definition in the ORM model. If `financials` is a list relationship, use `app.financials[0] if app.financials else None`. If it is intended as scalar (`uselist=False`), confirm this in the model definition.

---

## BE-8: Borrower tools create independent DB sessions, bypassing request-scoped transaction

**Severity:** Warning
**Location:** packages/api/src/agents/borrower_tools.py:71, 121, 175, etc.
**Description:** Every borrower tool creates its own `SessionLocal()` context manager for DB access. This means each tool invocation runs in its own transaction, completely independent of the WebSocket request's transaction context. While this works for read-only tools, it creates several issues: (1) writes from different tools within the same conversation turn are not atomic, (2) a tool writing an audit event and data in separate sessions could leave partial state if one fails, (3) the `update_application_data` tool (line 627) does a data write + audit write in the same session but this session is not the request session.

The current design is pragmatically functional because tools run in background tasks where no request-scoped session exists. However, tools like `start_application` (lines 571-593) create an application and then write an audit event in the same session, committing both -- if the audit write fails (e.g., advisory lock timeout), the application creation is also rolled back. This coupling may be unintentional.
**Recommendation:** Document the per-tool session strategy as an intentional design decision. For tools that do multi-step writes (start_application, update_application_data, acknowledge_disclosure), consider whether a failure in audit logging should roll back the business operation.

---

## BE-9: Agent registry caches graphs with stale checkpointers

**Severity:** Warning
**Location:** packages/api/src/agents/registry.py:63-66
**Description:** `get_agent()` caches compiled graphs keyed by agent name, and only rebuilds when the YAML config file's mtime changes. The `checkpointer` parameter is passed at build time and baked into the compiled graph. If the checkpointer reference changes (e.g., after a reconnection), the cached graph still holds the old checkpointer. The chat routes call `get_agent("public-assistant", checkpointer=checkpointer)` on every WebSocket connection, but if the graph is cached and the YAML hasn't changed, the `checkpointer` parameter is silently ignored and the old checkpointer is used.
**Recommendation:** Either include the checkpointer identity in the cache key, or always pass the checkpointer as runtime config rather than baking it into the compiled graph. Alternatively, invalidate the cache when the checkpointer changes (e.g., after reconnection).

---

## BE-10: WebSocket chat handler `_audit` creates a new DB session per audit event via async generator

**Severity:** Info
**Location:** packages/api/src/routes/_chat_handler.py:117-130
**Description:** The `_audit` helper inside `run_agent_stream` iterates over `get_db()` (an async generator) to obtain a session for each audit event. This creates and closes a new DB session + connection for every audit event (tool invocations, safety blocks, etc.) during a single conversation turn. For a conversation with tool calls, this could mean 3-5 new DB connections per user message.
**Recommendation:** Consider creating a single session at the start of the message processing loop and reusing it for all audit events within that turn. This reduces connection churn.

---

## BE-11: `completeness.py` passes enum values to `notin_()` instead of enum members

**Severity:** Warning
**Location:** packages/api/src/services/completeness.py:246
**Description:** The query filter uses `Document.status.notin_([s.value for s in _EXCLUDED_STATUSES])`. This converts enum members to their string `.value` for the `notin_` clause. Whether this works correctly depends on how SQLAlchemy maps the enum column. If the column stores native Python enum members (which is the case with `sa.Enum(DocumentStatus)`), comparing against string values may fail silently -- the filter wouldn't match and all documents would be returned including failed/rejected ones.
**Recommendation:** Use the enum members directly: `Document.status.notin_(list(_EXCLUDED_STATUSES))`. This matches what SQLAlchemy expects for an enum-typed column. The same pattern appears in `status.py:138` with `_RESOLVED_CONDITION_STATUSES` and `intake.py:48` with `_TERMINAL_STAGES`.

---

## BE-12: `snapshot_loan_data` reads from a session then uses the objects after closing it

**Severity:** Warning
**Location:** packages/api/src/services/compliance/hmda.py:308-323
**Description:** `snapshot_loan_data()` opens a `SessionLocal()` context, reads `app` and `financials`, then exits the `async with` block (closing the session). After that, it accesses `app.loan_type`, `app.property_address`, and `financials.gross_monthly_income` etc. on lines 330-358. Since the session is closed, accessing any lazy-loaded attributes on these ORM objects would raise `MissingGreenlet` / `DetachedInstanceError`. Currently the accessed attributes appear to be simple columns (not relationships), so they should be in the instance's `__dict__` and work. However, if any column uses deferred loading or if the `expire_on_commit` behavior fires, this will break.
**Recommendation:** Either extract the needed scalar values into local variables inside the `async with` block, or use `expire_on_commit=False` on the session. The safer pattern is:
```python
async with SessionLocal() as session:
    ...
    loan_type = app.loan_type
    property_address = app.property_address
    # etc.
```

---

## BE-13: WebSocket `authenticate_websocket` returns `None` for public endpoints without closing

**Severity:** Info
**Location:** packages/api/src/routes/_chat_handler.py:48-53
**Description:** When `required_role is None` and no token is provided, `authenticate_websocket` returns `None` without closing the WebSocket. The caller (borrower_chat) checks `if user is None: return` which would leave the WebSocket in an ambiguous state -- accepted but handler returns. In practice, `borrower_chat_websocket` always passes `required_role=UserRole.BORROWER`, so this path wouldn't trigger there. But the function's contract is misleading: for public chat (chat.py), `authenticate_websocket` isn't called at all.
**Recommendation:** This is a minor clarity issue. Add a docstring note that returning `None` without closing is intentional for unauthenticated-ok endpoints, or refactor so the function always either returns a UserContext or closes the socket.

---

## BE-14: `_chat_handler.py` accesses private functions from auth module

**Severity:** Info
**Location:** packages/api/src/routes/_chat_handler.py:17
**Description:** The chat handler imports `_build_data_scope`, `_decode_token`, and `_resolve_role` from `..middleware.auth`. These are private functions (prefixed with `_`). Similarly, `borrower_tools.py:18` imports `_build_data_scope`. Accessing private APIs creates tight coupling and makes it harder to refactor the auth module.
**Recommendation:** Promote `_build_data_scope` to a public function (remove the underscore prefix) since it's used by multiple modules. For `_decode_token` and `_resolve_role`, consider creating a public `authenticate_token(token: str) -> UserContext` function that wraps the private helpers.

---

## BE-15: Race condition in agent graph cache when checkpointer changes

**Severity:** Info
**Location:** packages/api/src/agents/registry.py:63-84
**Description:** The `_graphs` dict is a module-level mutable global accessed from async handlers with no locking. Multiple concurrent WebSocket connections could trigger simultaneous rebuilds if a YAML config changes while connections are being established. While Python's GIL prevents data corruption, it could result in multiple redundant graph builds, and the last writer wins for the cache entry.
**Recommendation:** For MVP this is acceptable. For production, consider using an `asyncio.Lock` or building graphs lazily with a proper async-safe cache.

---

## BE-16: `intake.py` REQUIRED_FIELDS uses `callable` type hint instead of `Callable`

**Severity:** Info
**Location:** packages/api/src/services/intake.py:117
**Description:** `REQUIRED_FIELDS: dict[str, tuple[str, str, callable]]` uses lowercase `callable` as a type hint. In Python, `callable` is a builtin function, not a type. The correct type hint is `typing.Callable` or `collections.abc.Callable`. Same issue at `intake_validation.py:173`. Ruff and mypy may not flag this because `callable` happens to be a valid expression, but it doesn't actually constrain the type.
**Recommendation:** Change to `Callable` from `collections.abc` or `typing`.

---

## BE-17: `upload_document` service returns `None` for not-found but type hint says `Document`

**Severity:** Info
**Location:** packages/api/src/services/document.py:106, 144
**Description:** The `upload_document` function's return type is `Document`, but it returns `None` on line 144 when the application is not found. The route handler (`documents.py:90`) correctly checks for `None`, but the function signature doesn't reflect this. This is a type safety issue that mypy would catch.
**Recommendation:** Change the return type to `Document | None`.

---

## BE-18: Config `_PROJECT_ROOT` resolution is fragile -- depends on exact directory depth

**Severity:** Info
**Location:** packages/api/src/core/config.py:15
**Description:** `_PROJECT_ROOT = Path(__file__).resolve().parents[4]` hardcodes that config.py is exactly 4 directories deep from the project root. This works today (`packages/api/src/core/config.py` -> `[0]=core, [1]=src, [2]=api, [3]=packages, [4]=root`), but any refactoring that changes the file's location would silently break `.env` loading without a clear error.
**Recommendation:** Consider a more robust approach: walk up until finding a known marker file (like `pyproject.toml` at the monorepo root or `compose.yml`). The current approach works for MVP but is fragile for future refactoring.

---

## BE-19: `_chat_handler.py` merges `build_langfuse_config` output into `config` dict but may overwrite `configurable`

**Severity:** Info
**Location:** packages/api/src/routes/_chat_handler.py:155-158
**Description:** The config dict is built as:
```python
config = {
    **build_langfuse_config(session_id=session_id),
    "configurable": {"thread_id": thread_id},
}
```
If `build_langfuse_config` returns a dict that also contains a `"configurable"` key, the explicit `"configurable"` on the next line would overwrite it. Currently `build_langfuse_config` returns `{"callbacks": [...], "metadata": {...}}` which doesn't include `"configurable"`, so this works. But it's a latent conflict if the observability config changes.
**Recommendation:** Merge more carefully, e.g., use dict union or explicit key assignment to prevent future key collisions.

---

## BE-20: `create_application` in `application.py` parses `user.name` unsafely for mononyms

**Severity:** Info
**Location:** packages/api/src/services/application.py:93-94
**Description:** When creating a borrower from the authenticated user's name:
```python
first_name=user.name.split()[0] if user.name else "Unknown",
last_name=user.name.split()[-1] if user.name and len(user.name.split()) > 1 else "",
```
For a single-word name like "Prince", `split()` returns `["Prince"]`, so `first_name="Prince"` and `last_name=""`. This is handled. But for names with middle components like "Mary Jane Watson", `first_name="Mary"` and `last_name="Watson"`, losing "Jane". This is acceptable for MVP auto-fill since the borrower can correct it via intake, but worth noting.
**Recommendation:** No change needed for MVP. If name parsing becomes important, use a proper name parser or always ask the borrower to confirm.
