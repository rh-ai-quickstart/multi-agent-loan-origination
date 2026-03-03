# Debug Specialist -- Pre-Phase 3 Bug Review

Systematic review of latent bugs in the mortgage-ai codebase. Focus areas:
agents, chat handler, services, middleware, inference.

---

## BUG-1: quality_flags parsed as comma-split in condition service but stored as JSON

**Severity:** Critical
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/condition.py:279`
**Description:** The `check_condition_documents` function splits `quality_flags` on commas (`doc.quality_flags.split(",")`) to produce a list. However, the extraction pipeline stores `quality_flags` as a JSON-serialized list via `json.dumps(quality_flags)` (see `extraction.py:90,101,127`). The JSON format is `'["unreadable"]'` or `'["document_type_mismatch", "wrong_period"]'`. Splitting this on commas produces garbage like `['["unreadable"]']` or `['["document_type_mismatch"', ' "wrong_period"]']` -- strings with brackets and quotes embedded.

Meanwhile, the `completeness.py:270` service correctly uses `json.loads(doc.quality_flags)`. The seeder fixture at `fixtures.py:203` sets quality_flags to a plain string (`"Document partially illegible, please resubmit"`), which is neither valid JSON nor comma-delimited in a useful way.

**Reproduction:** Upload a document that triggers extraction with quality flags (e.g., a stale pay stub). Then call `check_condition_documents` on a condition linked to that document. The `quality_flags` field in the response will contain malformed strings with JSON brackets.

**Recommendation:** Change `condition.py:279` to use `json.loads()` with a fallback:
```python
import json
try:
    flags = json.loads(doc.quality_flags) if doc.quality_flags else []
except (json.JSONDecodeError, TypeError):
    flags = [doc.quality_flags] if doc.quality_flags else []
```
Also fix the seeder fixture to store quality_flags as valid JSON: `json.dumps(["partially_illegible"])`.

---

## BUG-2: Synchronous httpx.get blocks the async event loop during JWKS fetch

**Severity:** Critical
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/middleware/auth.py:36`
**Description:** `_fetch_jwks()` uses synchronous `httpx.get()` to call Keycloak's JWKS endpoint. This function is called from `_get_signing_key()`, which is called from `_decode_token()`, which is called from the async `get_current_user()` dependency. The synchronous HTTP call blocks the entire asyncio event loop for up to 5 seconds (the timeout), preventing all other request processing.

Under load, if Keycloak is slow to respond, every concurrent request that needs auth will pile up behind the blocked event loop. With multiple concurrent WebSocket connections and REST requests, this could freeze the entire server.

**Reproduction:** Start the app with Keycloak configured. Add artificial latency to Keycloak (e.g., `tc netem delay 2000ms`). Send multiple concurrent authenticated requests. Observe that all requests stall until the JWKS fetch completes.

**Recommendation:** Switch to `httpx.AsyncClient` for JWKS fetching:
```python
async def _fetch_jwks() -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
```
This requires making `_get_jwks` and `_get_signing_key` async as well. Alternatively, run the sync call via `asyncio.to_thread()` as a minimal fix.

---

## BUG-3: Agent graph cache is not thread-safe under concurrent requests

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/registry.py:72`
**Description:** The `_graphs` module-level dict is mutated without any locking. When multiple WebSocket connections open simultaneously (e.g., two users opening chat at the same time), both may see `agent_name not in _graphs`, both will call `_build_graph()`, and both will write to `_graphs[agent_name]`. In CPython, dict mutations are GIL-protected at the bytecode level, so this won't corrupt the dict structure. However, the mtime-check-then-build sequence at lines 63-72 is a classic TOCTOU race: two coroutines can both see a stale mtime, both build graphs, and the second write wins silently.

More concerning: if one coroutine is mid-build when a config change triggers another coroutine to also rebuild, the build itself (which imports modules and creates LLM clients) could produce undefined behavior.

**Reproduction:** Send two simultaneous WebSocket connection requests when the agent cache is cold. Both will trigger `_build_graph()` concurrently.

**Recommendation:** Add an `asyncio.Lock` around the build section:
```python
import asyncio
_build_lock = asyncio.Lock()

async def get_agent(agent_name: str, checkpointer=None):
    async with _build_lock:
        # existing cache-check + build logic
```
Since `get_agent` is not currently async, it would need to become async, or use `threading.Lock` if it must remain sync.

---

## BUG-4: Shared mutable _DISABLED_USER object returned for all AUTH_DISABLED requests

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/middleware/auth.py:156-162`
**Description:** When `AUTH_DISABLED=true`, `get_current_user()` returns the same `_DISABLED_USER` singleton for every request. The `UserContext` is frozen (`ConfigDict(frozen=True)`), so direct attribute mutation will raise an error. However, if any code path mutates the nested `DataScope` object (which is a mutable Pydantic model, not frozen), that mutation would affect all concurrent requests. Currently `DataScope` is not frozen, so `_DISABLED_USER.data_scope.pii_mask = True` would silently corrupt the singleton for all subsequent requests.

**Reproduction:** In AUTH_DISABLED mode, if any middleware or service ever mutates `user.data_scope`, all subsequent requests inherit the mutation. Currently no code appears to do this, but it's a latent footgun.

**Recommendation:** Either freeze `DataScope` as well (`model_config = ConfigDict(frozen=True)`) or return a fresh `UserContext` instance from `get_current_user()` each time.

---

## BUG-5: WebSocket audit writes iterate get_db generator without proper cleanup on error

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/_chat_handler.py:117-130`
**Description:** The `_audit()` inner function uses `async for db_session in get_db()` to get a database session. `get_db()` is an async generator that yields one session and then closes it in its `finally` block. The `async for` loop correctly exhausts the generator after getting one session. However, if `write_audit_event` or `db_session.commit()` raises an exception, the generator's `finally` still runs (closing the session), but the exception is caught by the broad `except Exception` on line 129.

The real issue is that `get_db()` is designed as a FastAPI dependency (used with `Depends()`), not for manual iteration. Using it as `async for db_session in get_db()` works but is fragile -- if the generator implementation changes (e.g., adds rollback logic), the manual iteration won't benefit from it.

**Reproduction:** If the database is temporarily unavailable, audit writes will silently fail. This is logged at line 130, but the session from `get_db()` may not be properly cleaned up if `SessionLocal()` itself raises.

**Recommendation:** Use `SessionLocal()` directly as a context manager (matching the pattern used in `borrower_tools.py`):
```python
async with SessionLocal() as db_session:
    await write_audit_event(db_session, ...)
    await db_session.commit()
```

---

## BUG-6: Document upload does not roll back S3 object on DB commit failure

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/document.py:166-176`
**Description:** In `upload_document()`, the flow is: create Document row -> flush -> upload to S3 -> update file_path and status -> commit. If the `session.commit()` at line 173 fails (e.g., DB connection drops), the file has already been uploaded to S3 but the Document row is rolled back. This leaves an orphaned object in S3 with no corresponding database record. Over time, this could accumulate orphaned storage objects that consume space but are unreachable.

**Reproduction:** Introduce a transient DB failure (e.g., kill PostgreSQL) between the S3 upload (line 168) and the commit (line 173). The S3 object will exist but the Document row will not.

**Recommendation:** Wrap the commit in a try/except that cleans up the S3 object on failure:
```python
try:
    await session.commit()
except Exception:
    await storage.delete_file(object_key)  # compensating action
    raise
```
Or restructure to commit first (with placeholder status), then upload S3, then update status.

---

## BUG-7: Extraction pipeline exception handler may fail to update document status

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/extraction.py:149-155`
**Description:** In the outer `except Exception` block of `process_document()`, the code tries to set `doc.status = DocumentStatus.PROCESSING_FAILED` and commit. However, the `doc` variable is loaded inside the `try` block at line 64. If the exception occurs before line 64 (e.g., during `SessionLocal()` creation or the initial query), `doc` will be unbound and the error handler at line 152 will raise a `NameError`, masking the original exception.

Even if `doc` is bound, the session may be in a broken state after the original exception (e.g., a database disconnect). The inner `await session.commit()` at line 154 may itself fail, and the inner `except` logs it, but the document is left in PROCESSING status permanently (a zombie).

**Reproduction:** Kill the database while extraction is running. The document will be stuck in PROCESSING status indefinitely, with no way to retry.

**Recommendation:** Restructure the error handler to use a fresh session:
```python
except Exception:
    logger.exception("Extraction failed for document %s", document_id)
    try:
        async with SessionLocal() as err_session:
            stmt = select(Document).where(Document.id == document_id)
            result = await err_session.execute(stmt)
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = DocumentStatus.PROCESSING_FAILED
                await err_session.commit()
    except Exception:
        logger.exception("Failed to update status for document %s", document_id)
```

---

## BUG-8: background extraction task not exception-safe in documents route

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/documents.py:98`
**Description:** `asyncio.create_task(extraction_svc.process_document(doc.id))` creates a fire-and-forget background task. If this task raises an unhandled exception, Python 3.11+ will log it but not propagate it. The task reference is not stored, so there's no way to check its result or handle its failure. If the extraction service itself fails to initialize (raises RuntimeError), the exception happens synchronously and the 201 response will already have been sent.

More critically: the task holds no reference to the DB session, which is correct (it creates its own), but the `doc.id` passed to it could theoretically be affected by session rollback if FastAPI's dependency cleanup happens before the task reads the ID. In practice, `doc.id` is an integer value already captured, so this is safe -- but it's a subtle point.

**Reproduction:** The extraction task failing is invisible to the caller. If the extraction service raises, the document remains in PROCESSING status forever.

**Recommendation:** Store the task reference and add error logging:
```python
task = asyncio.create_task(extraction_svc.process_document(doc.id))
task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
```
This ensures exceptions are consumed (preventing "Task exception was never retrieved" warnings).

---

## BUG-9: Storage service build_object_key allows path traversal via filename

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/storage.py:108-110`
**Description:** `build_object_key` constructs an S3 key as `{application_id}/{document_id}/{filename}`. The `filename` comes from `file.filename` in the upload route (which comes from the HTTP multipart form data -- user-controlled). A malicious user could set the filename to `../../other-app/1/secret.pdf`, causing the S3 object to be written at a path outside the expected prefix. While S3 treats keys as flat strings (no directory traversal), a `../` in the key is still confusing and could cause issues with any prefix-based access policies or listing operations.

**Reproduction:** Upload a file with `filename=../../../admin/1/backdoor.pdf`. The S3 object key will be `{app_id}/{doc_id}/../../../admin/1/backdoor.pdf`.

**Recommendation:** Sanitize the filename to strip path components:
```python
import os
safe_name = os.path.basename(filename)
return f"{application_id}/{document_id}/{safe_name}"
```

---

## BUG-10: Affordability calculator produces negative max_loan_amount for zero interest rate edge case

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/calculator.py:29-33`
**Description:** When `interest_rate=0`, the code takes the `else` branch at line 33: `payment_per_dollar = 1 / n_payments`. This is correct for a 0% interest loan. However, if `loan_term_years=0` is somehow passed, `n_payments` would be 0 and this would cause a `ZeroDivisionError`. The Pydantic schema likely validates `loan_term_years > 0`, but if the tool is called directly with `loan_term_years=0`, it crashes.

Additionally, if `gross_annual_income=0` and `monthly_debts=0`, then `gross_monthly_income=0` and `max_housing_payment=0`, which returns early (line 15-24), but the DTI calculation at line 21 has a guard for `gross_monthly_income > 0`. If both are exactly 0, DTI is correctly set to 0. This path is safe.

**Reproduction:** Call `affordability_calc` with `loan_term_years=0` (if the schema allows it).

**Recommendation:** Add a guard: `if n_payments <= 0: return AffordabilityResponse(...)`. Also verify the Pydantic schema enforces `loan_term_years >= 1`.

---

## BUG-11: TRID deadline calculation uses calendar days instead of business days

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:249`
**Description:** The TRID Loan Estimate deadline requires delivery within 3 **business days** of receiving a completed application. The code uses `timedelta(days=3)`, which counts calendar days. For an application submitted on Thursday, the code would show the deadline as Sunday, but the actual regulatory deadline would be Tuesday (skipping Saturday and Sunday).

The code comment at line 247 says "3 business days" but the implementation uses calendar days.

**Reproduction:** Submit an application on a Friday. The deadline shows as Monday (3 calendar days) instead of Wednesday (3 business days).

**Recommendation:** Since this is a simulated/demo system with the disclaimer "simulated for demonstration purposes", this may be acceptable. But for accuracy, implement a business-day calculator or use `numpy.busday_offset` / a simple weekend-skip loop.

---

## BUG-12: Disclosure status query has no data scope filtering

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/disclosure.py:55-97`
**Description:** `get_disclosure_status()` accepts an `application_id` and queries audit events directly without any data scope check. It does not verify that the calling user has access to the given application. The `disclosure_status` tool in `borrower_tools.py:320` calls this without passing user context for scope filtering (unlike other tools which check application access first).

This means any authenticated user who knows or guesses an application_id can check which disclosures have been acknowledged for that application, potentially leaking information about other users' applications.

**Reproduction:** As borrower A, call `disclosure_status` with borrower B's application_id. The tool returns disclosure status for B's application.

**Recommendation:** Add a data scope check at the beginning of `get_disclosure_status()`, similar to the pattern in other services:
```python
async def get_disclosure_status(session, user, application_id):
    # Verify application is in scope
    app_stmt = select(Application).where(Application.id == application_id)
    app_stmt = apply_data_scope(app_stmt, user.data_scope, user)
    result = await session.execute(app_stmt)
    if result.scalar_one_or_none() is None:
        return None
    # ... rest of function
```

---

## BUG-13: acknowledge_disclosure tool creates its own session but borrows audit hash chain lock contention

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:292-305`
**Description:** The `acknowledge_disclosure` tool creates its own `SessionLocal()` session and calls `write_audit_event()` followed by `session.commit()`. The audit service acquires a PostgreSQL advisory lock (`pg_advisory_xact_lock`) for hash chain integrity. Since this tool creates its own session (transaction), the advisory lock blocks any other concurrent audit writes until this transaction commits.

This is correct behavior for hash chain integrity, but it means that if the LLM is slow and the tool execution takes a while to complete its surrounding context, the advisory lock is held for the duration of the entire transaction scope (until `session.commit()` at line 305). During that time, all other audit writes across the entire application are serialized.

In practice, the lock is released quickly because `session.commit()` happens right after `write_audit_event()`. But if network latency to the DB is high, or if the session is open longer than expected, it could become a bottleneck.

**Reproduction:** Under high concurrency (many borrowers acknowledging disclosures simultaneously), audit writes from other WebSocket sessions could experience latency spikes.

**Recommendation:** This is acceptable for MVP. For production, consider batching audit writes or using an async queue.

---

## BUG-14: Chat handler does not gracefully close WebSocket on agent load failure

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/chat.py:37`
**Description:** In `chat_websocket()`, if `conversation_service.is_initialized` is True but `conversation_service.checkpointer` raises (due to a race condition where the service was shut down between the check and the property access), the `try/except` at line 39 catches it and sends an error message. However, it then calls `await ws.close()` which may fail if the WebSocket is already in a closing state. The `close()` call is not wrapped in a try/except.

**Reproduction:** Trigger a server shutdown while a client is connecting. The `checkpointer` property could raise between the `is_initialized` check (line 36) and the property access (line 37).

**Recommendation:** Wrap the `ws.close()` in a try/except or use a pattern like:
```python
try:
    await ws.close()
except Exception:
    pass
```

---

## BUG-15: Intake service get_remaining_fields accesses app.financials without selectinload for co-borrowers

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/intake.py:288`
**Description:** In `get_remaining_fields()`, `app.financials` is accessed at line 288 after loading the application with `selectinload(Application.financials)` -- this is correct. However, `app.financials` is a `uselist=False` relationship that returns a single `ApplicationFinancials` or None. The financials record is per-application with an optional borrower_id.

The real issue: when there are multiple borrowers (co-borrower scenario from Phase 2), `app.financials` only returns one financials record (because `uselist=False`). If borrower A's financials are stored but borrower B's are the ones the user is asking about, the function checks the wrong financials.

In `update_application_fields()` at line 215, the code correctly fetches financials by `(application_id, borrower_id)`. But `get_remaining_fields()` at line 288 just uses `app.financials` which may point to a different borrower's record.

**Reproduction:** Create an application with a co-borrower. Fill in primary borrower's financials. Check remaining fields -- it may show financials as complete even though the co-borrower's financials are empty, or vice versa.

**Recommendation:** Fetch financials by `(application_id, borrower.id)` consistently:
```python
financials = await _get_or_create_financials(session, application_id, borrower.id) if borrower else None
```
Same fix needed in `get_application_progress()` at line 406.

---

## BUG-16: Model config mtime cache race with hot-reload

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/inference/config.py:106-123`
**Description:** The `get_config()` function caches config by mtime. If two concurrent requests see the same stale mtime, both will attempt to reload. The first one succeeds and updates `_cached_config` and `_cached_mtime`. The second one also reloads, creating a second set of clients (since `clear_client_cache()` is called at line 115). This is wasteful but not incorrect -- the second reload simply replaces the first's result.

However, between the `clear_client_cache()` at line 115 and the `_cached_config = load_config(...)` at line 109, there's a window where client cache is cleared but config is not yet updated. Any concurrent request hitting `_get_client()` during this window will recreate a client from the old config (since `_cached_config` still holds the old value until line 109 completes).

**Reproduction:** Edit `models.yaml` while the server is handling requests. There's a brief window of inconsistency.

**Recommendation:** Swap the order: update `_cached_config` before clearing client cache, or use a lock. For MVP this is acceptable since config changes are infrequent.

---

## BUG-17: LangGraph tool_auth node does not strip blocked tool calls from the message

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/base.py:190-232`
**Description:** When `tool_auth` detects unauthorized tool calls, it returns an AIMessage with a denial string. The `after_tool_auth` function checks if the last message is an AIMessage without tool calls and routes to `output_shield`. However, the original AIMessage with tool calls (from `agent_capable`) is still in the message history. The denial AIMessage is appended after it.

The problem: the `should_continue` function at line 183 routes based on the last message. After tool_auth, the last message is the denial AIMessage (no tool calls), so it routes to `output_shield`. But the original tool-calling AIMessage remains in the message history. If the graph loops or the LLM sees this history in subsequent turns, it may try the same tool calls again (infinite loop if the user keeps chatting).

Additionally, if only some tool calls are blocked (line 206-217 checks each call), the current code either blocks all or blocks none -- there's no partial execution. The `blocked` list is populated for each unauthorized call, but the response either blocks everything (if any are blocked) or lets everything through. If the LLM requests 2 tools and only 1 is unauthorized, both are blocked.

**Reproduction:** Configure a tool with role restrictions. Have the LLM call both a restricted and an unrestricted tool in the same turn. Both will be blocked.

**Recommendation:** For partial blocking, split the tool calls: execute allowed ones via ToolNode and return denial messages for blocked ones. For MVP, the all-or-nothing approach is acceptable, but document it.

---

## BUG-18: WebSocket messages_fallback grows unbounded for long conversations without checkpointer

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/_chat_handler.py:152-153`
**Description:** When the checkpointer is unavailable, `messages_fallback` is a plain list that accumulates every user message and AI response for the duration of the WebSocket connection. For long conversations, this list grows without bound, consuming increasing memory. Each message includes the full text content. A user who keeps chatting for hours could accumulate megabytes of message history in memory.

Additionally, on every turn, the entire `messages_fallback` list is passed as `input_messages` to the graph (line 153). This means the LLM receives the full conversation history on every turn, which will eventually exceed the model's context window and cause errors.

**Reproduction:** Open a chat without the checkpointer. Send 100+ messages. Memory usage grows linearly, and eventually the LLM call will fail due to context window overflow.

**Recommendation:** Add a sliding window over `messages_fallback` to limit the number of messages sent to the LLM:
```python
MAX_HISTORY = 20  # last N messages
input_messages = messages_fallback[-MAX_HISTORY:]
```
And consider periodically trimming the list to prevent unbounded memory growth.

---

## BUG-19: Seeder fixture quality_flags is a plain string, not JSON

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/seed/fixtures.py:203`
**Description:** The seeder sets `quality_flags` to a plain string: `"Document partially illegible, please resubmit"`. The completeness service at `completeness.py:270` tries to `json.loads(doc.quality_flags)`, which will throw `json.JSONDecodeError` for this plain string. The error is caught and `flags` defaults to `[]`, silently hiding the quality issue for seeded data.

**Reproduction:** Run the seeder. Check completeness for the application with the flagged document. The quality flag will not appear.

**Recommendation:** Change the seeder to store JSON: `json.dumps(["partially_illegible"])`. This is related to BUG-1.

---

## BUG-20: Regulatory deadline tool treats "0 days remaining" as non-urgent for Reg B

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:236-245`
**Description:** For the Reg B deadline, when `reg_b_remaining` is exactly 0, the code enters the `if reg_b_remaining > 0` branch's else clause, displaying "0 days ago." It should say "due today" or similar, since 0 remaining days means the deadline is today, not overdue.

**Reproduction:** Check regulatory deadlines on exactly the 30th day after application.

**Recommendation:** Add a `reg_b_remaining == 0` case similar to the TRID handling at line 256.

---

## BUG-21: S3 download_file response Body is not properly closed

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/storage.py:84-91`
**Description:** `download_file()` calls `response["Body"].read()` to get the file bytes but never closes the `Body` stream. The boto3 `get_object` response Body is a `StreamingBody` that holds an HTTP connection. Not closing it can lead to connection pool exhaustion under high document processing load.

**Reproduction:** Process many documents in rapid succession. Connection pool may become exhausted.

**Recommendation:** Use a context manager or explicit close:
```python
body = response["Body"]
try:
    return body.read()
finally:
    body.close()
```

---

## BUG-22: Tool auth bypass when tool_allowed_roles is empty dict vs None

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/base.py:293-310`
**Description:** The graph construction uses `if tool_allowed_roles:` to decide whether to include the `tool_auth` node. An empty dict `{}` is falsy in Python, so if a YAML config defines `tools: []` (no tool configs), `tool_allowed_roles` will be `{}`, and the tool_auth node will be skipped entirely. This is correct behavior (no restrictions configured = no restrictions applied).

However, this means there's no way to have a configuration that says "these tools exist but none of them have role restrictions" vs "role restrictions are not configured at all." Both result in the same behavior. This is a design issue, not a runtime bug, but worth documenting.

**Reproduction:** N/A -- design observation.

**Recommendation:** Document the behavior: empty `tool_allowed_roles` disables the auth node entirely.
