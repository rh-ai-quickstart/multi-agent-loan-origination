# Debug Specialist Review -- Pre-UI Reliability

Scope: `packages/api/src/` with emphasis on agents and services.
Methodology: Traced failure paths end-to-end for error recovery, resource leaks,
race conditions, state consistency, and operational debuggability.

---

## Critical

### DS-01: Document upload leaves orphaned DB row on S3 failure

**File:** `packages/api/src/services/document.py:197-217`

`upload_document` inserts the `Document` row and calls `session.flush()` to
get `doc.id`, then calls S3 `upload_file`. If S3 raises, the function
propagates the exception but has already flushed the DB row. The caller in
the route layer has no rollback guard in a `try/finally` block -- the session
context manager will roll back if the exception propagates without a commit,
which is correct. However, the status field was updated to `PROCESSING` before
commit:

```python
doc.status = DocumentStatus.PROCESSING        # mutated in memory
await storage.upload_file(...)                # may raise here
doc.file_path = object_key                    # never reached
await session.commit()                        # never reached
```

Wait -- on closer inspection the sequence is:
1. `session.flush()` -- row inserted with `status=UPLOADED`, no `file_path`
2. `upload_file(...)` -- if this raises, the session context manager (`async with
   SessionLocal()`) rolls back the transaction at exit, so the row is NOT
   persisted.

This is actually correct. However, there is a real problem: the function
**returns `None`** when the application is not found (line 187), but its
declared return type is `Document`. Callers in
`packages/api/src/routes/documents.py` check for `None` to detect "not
found" vs. "upload succeeded", but any caller that calls
`get_extraction_service().process_document(doc.id)` as a background task
(via `BackgroundTasks.add_task`) after this `None` return will be called with
the return value of `upload_document` -- which is `None`, not a `Document`.

More concretely: when `upload_document` returns `None` (app not found), the
route layer in `documents.py` should 404 before the background task is
queued. Let me verify the actual severity is a type annotation lie, not a
functional bug. This is a Warning-level issue (see DS-07), not a Critical.

Re-evaluating: the real Critical in this area is that if the S3 upload
succeeds but the subsequent `session.commit()` fails (DB error), the document
exists in S3 but no DB record tracks it. The object is unreachable and
untrackable. This is the phantom-S3-object problem (partially noted as W-23
for the opposite direction). **This direction (commit failure after successful
S3 upload) is NOT in the deferred list.** The deferred item W-23 says "S3
upload failure leaves phantom Document row" -- the inverse. The missing
coverage is: successful S3 upload + failed commit = orphaned S3 object with
no audit trail and no way to clean it up.

**Suggested fix:** Wrap the commit in a try/except; if commit fails, attempt
S3 object deletion as a compensating action and re-raise.

---

### DS-02: `add_borrower` commits twice, creating inconsistent audit trail on second commit failure

**File:** `packages/api/src/services/application.py:299-314`

`add_borrower` performs two separate `await session.commit()` calls:

```python
session.add(junction)
await session.commit()                         # commit 1: junction row

await audit.write_audit_event(...)
await session.commit()                         # commit 2: audit event
```

If the second commit (audit) fails, the junction row is already persisted --
the borrower is added to the application but the audit trail does not record
it. This is an undetectable silent failure: the operation succeeds from the
caller's perspective (exception swallowed at the route layer) but the audit
chain has a gap.

The same pattern exists in `remove_borrower` at lines 367-379.

**Suggested fix:** Combine both operations into a single transaction: call
`write_audit_event` before the first (and only) commit. Both the junction
write and audit write should be flushed, then committed atomically.

---

## Warning

### DS-03: Agent graph cache has no thread-safety guard for concurrent rebuilds

**File:** `packages/api/src/agents/registry.py:62-106`

`get_agent` is an async function that checks `_graphs` (a module-level dict),
performs a filesystem `stat()`, and then rebuilds the graph. Under asyncio
concurrency -- multiple WebSocket connections triggering the same agent
simultaneously -- two coroutines can both read a stale or absent cache entry,
both decide to rebuild, and both call `_build_graph`. The second write to
`_graphs[agent_name]` wins, but the first graph (and its LangGraph compiled
state) becomes garbage. More importantly, if both builds overlap in time and
one succeeds while the other partially initializes (e.g., import fails midway
through a dynamic `importlib.import_module`), the cache may end up in an
inconsistent state.

This is not a data-corruption risk but is a reliability risk: concurrent
first-load requests for the same agent will each build a graph independently,
creating redundant LLM client connections.

**Suggested fix:** Use `asyncio.Lock` per agent name to serialize concurrent
rebuilds. A simple `_rebuild_locks: dict[str, asyncio.Lock]` alongside
`_graphs` would prevent the race.

---

### DS-04: `StorageService._ensure_bucket` swallows all `ClientError` exceptions, including permission errors

**File:** `packages/api/src/services/storage.py:57-63`

```python
def _ensure_bucket(self) -> None:
    try:
        self._client.head_bucket(Bucket=self._bucket)
    except ClientError:
        logger.info("Creating S3 bucket: %s", self._bucket)
        self._client.create_bucket(Bucket=self._bucket)
```

`ClientError` covers all S3 errors: `AccessDenied`, `NoSuchBucket`,
`InvalidBucketName`, `TooManyRequests`, etc. The code only intends to handle
`NoSuchBucket`. If `head_bucket` fails with `AccessDenied` (wrong credentials)
or any other error, the code proceeds to `create_bucket`, which will also
fail -- but now with a different error that surfaces as a `RuntimeError` at
startup with a confusing message, masking the root cause (bad credentials).

**Suggested fix:** Check the error code before deciding to create:

```python
except ClientError as e:
    if e.response["Error"]["Code"] in ("NoSuchBucket", "404"):
        self._client.create_bucket(Bucket=self._bucket)
    else:
        raise
```

---

### DS-05: `langfuse_client.fetch_observations` pagination loop has no page limit -- can hang indefinitely

**File:** `packages/api/src/services/langfuse_client.py:97-117`

```python
while True:
    ...
    total_pages = meta.get("totalPages", 1)
    if page >= total_pages:
        break
    page += 1
```

If LangFuse returns malformed pagination metadata (e.g., `totalPages: 0` or
the field is absent), the loop will run until the caller's `httpx` timeout
(15s) fires or the process runs out of memory. If LangFuse is pathologically
slow or returns an unbounded page count, the fetch will consume memory
proportional to the total observation count. With large LangFuse deployments
this could cause OOM in the API process.

Additionally, if LangFuse returns `totalPages: null` or any non-integer,
`page >= total_pages` will raise a `TypeError` which surfaces as an unhandled
exception in the monitoring endpoint.

**Suggested fix:** Cap the loop at a reasonable maximum (e.g., 50 pages):

```python
_MAX_PAGES = 50
while page <= _MAX_PAGES:
    ...
    if page >= total_pages:
        break
    page += 1
else:
    logger.warning("LangFuse fetch hit page cap (%d), results may be incomplete", _MAX_PAGES)
```

Also add a type check before comparison: `total_pages = int(meta.get("totalPages", 1))`.

---

### DS-06: `PIIMaskingMiddleware` reads entire streaming response into memory, losing streaming benefits and risking OOM on large responses

**File:** `packages/api/src/middleware/pii.py:115-119`

```python
body_bytes = b""
async for chunk in response.body_iterator:
    ...
    body_bytes += chunk
```

Byte concatenation in a loop is O(n^2) because each `+=` on an immutable
`bytes` object creates a new allocation. For audit export responses with
`limit=10_000` events this can be several MB, triggering quadratic allocation
behavior. More critically, the middleware buffers the full response body in
memory for EVERY CEO-role response -- including large list/export responses.

**Suggested fix:** Use `b"".join([...])` with a list accumulator:

```python
chunks = []
async for chunk in response.body_iterator:
    chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
body_bytes = b"".join(chunks)
```

This is a single-line fix with significant efficiency improvement.

---

### DS-07: `upload_document` return type annotation is `Document` but can return `None`

**File:** `packages/api/src/services/document.py:149-187`

```python
async def upload_document(...) -> Document:
    ...
    if application is None:
        return None      # line 187 -- returns None despite Document return type
```

The function signature declares `-> Document` but silently returns `None` when
the application is not accessible. This is a type-correctness bug that will
cause `AttributeError` crashes for any future caller that doesn't check for
`None`. The route layer currently handles it (it checks for `None`), but the
incorrect return type means mypy/pyright will not flag callers that assume the
return is always a `Document`.

**Suggested fix:** Change the return type to `Document | None` to match the
actual behavior.

---

### DS-08: `lo_application_detail` accesses ORM attributes after session is closed

**File:** `packages/api/src/agents/loan_officer_tools.py:80-123`

```python
async with SessionLocal() as session:
    app = await get_application(session, user, application_id)
    ...

# --- SESSION IS CLOSED HERE ---
stage = app.stage.value if app.stage else "inquiry"
...
for ab in app.application_borrowers or []:   # lazy-loaded relationship access
    if ab.borrower:                           # another lazy-load
```

After the `async with SessionLocal()` block exits, the session is closed and
the ORM objects are detached. Accessing `app.application_borrowers` and
`ab.borrower` outside the session context will raise
`MissingGreenlet`/`DetachedInstanceError` unless these relationships were
eagerly loaded. `get_application` in `application.py` does use `selectinload`
for `application_borrowers` with `joinedload` for `borrower`, so this
currently works. But the access pattern is fragile: if `get_application` is
ever refactored to not eager-load these relationships, this tool silently
breaks at runtime (not at definition time).

Similarly, the `status` variable from `get_application_status` accesses ORM
attributes after session close.

**Suggested fix:** Access and format all ORM attributes inside the `async
with` block, before the session closes. This is the pattern already used
correctly by `ceo_application_lookup` (which formats inside the session block)
and `uw_application_detail` (which calls `_format_application_detail` before
the commit).

---

### DS-09: `ceo_model_latency` / `ceo_model_token_usage` / `ceo_model_errors` / `ceo_model_routing` call `get_model_monitoring_summary` four times per conversational turn

**File:** `packages/api/src/agents/ceo_tools.py:485-657`

Each of the four model monitoring tools independently calls
`get_model_monitoring_summary(hours, model)`, which makes an HTTP request to
LangFuse (or returns from the 60-second cache). If the CEO agent calls all
four tools in a single turn (e.g., "show me a complete monitoring report"),
the first call fetches from LangFuse and populates the cache, but the
remaining three also hit the same cache key and return instantly. This looks
fine due to caching.

However, the 60-second TTL means that if four monitoring queries arrive
staggered across cache expiration boundaries, all four will trigger
independent HTTP fetches to LangFuse concurrently, potentially quadrupling
the load on LangFuse and causing race conditions in the `_cache` dict (two
coroutines may both miss the cache and both call `fetch_observations`, both
receive results, and both write to `_cache` -- last write wins, no data
corruption but wasted work).

More critically: if LangFuse raises an error (which propagates out of
`get_model_monitoring_summary` as `httpx.HTTPStatusError` or
`httpx.RequestError`), the tool returns the error string `f"Error fetching
model monitoring data: {e}"`. This is fine from a UX standpoint. But the
error is logged as a warning in `get_model_monitoring_summary` before
re-raising, then the tool catches it and returns a string -- so the exception
is swallowed with a warning log. This is acceptable but the log message lacks
the request context (which tool, which hours, which model).

**Suggested fix:** Low-priority for MVP. Note that `_cache` is a plain dict
with no lock -- safe under asyncio's cooperative scheduling (no parallel
modification), but worth a comment documenting that assumption.

---

### DS-10: `ingest_kb_content` flushes but does not commit -- KB ingestion relies on caller's commit

**File:** `packages/api/src/services/compliance/knowledge_base/ingestion.py:236`

The function ends with:

```python
await session.flush()
logger.info("KB ingestion complete: %d documents, %d chunks", ...)
return {"documents": total_docs, "chunks": total_chunks}
```

The function never calls `session.commit()`. This design relies entirely on
the caller to commit. If the caller commits correctly this works fine, but if
the caller forgets to commit (or if an exception occurs in caller code after
`ingest_kb_content` returns but before commit), the entire ingestion is
silently rolled back with no error logged in `ingest_kb_content`.

This pattern is intentional for service-layer functions (which let the route
own the transaction boundary), but it is inconsistent with other service
functions that DO commit internally (e.g., `condition.py`, `application.py`).
The inconsistency makes it hard to reason about which service calls are
transactionally complete. At minimum, the docstring should explicitly state
"caller must commit".

**Suggested fix:** Add a note to the function docstring: "Caller is
responsible for committing the session after this function returns."

---

### DS-11: `lo_submit_to_underwriting` partial transition can leave application in PROCESSING stage permanently

**File:** `packages/api/src/agents/loan_officer_tools.py:370-408`

This tool performs a two-step stage transition within a single DB session:

```python
# Step 1: APPLICATION -> PROCESSING
app = await transition_stage(session, user, application_id, ApplicationStage.PROCESSING)
await write_audit_event(...)

# Step 2: PROCESSING -> UNDERWRITING
app = await transition_stage(session, user, application_id, ApplicationStage.UNDERWRITING)
await write_audit_event(...)
await session.commit()
```

`transition_stage` does not commit -- it mutates the ORM object in memory and
returns. The final `session.commit()` (inside the `async with`) commits both
transitions atomically, which is correct.

However, if an exception is raised between Step 1 and Step 2 (e.g., the
second `transition_stage` raises `InvalidTransitionError`), the exception
propagates, the `async with` rolls back, and the application stays in its
original stage -- this is correct behavior.

But: this tool is noted in the deferred list (W-25) as "two-step transition
not atomic". That issue focuses on the audit events. My independent review
confirms that the two-step transition IS atomic at the DB level (single
transaction), but the deferred concern about audit event ordering (two separate
flush calls to `write_audit_event` before the final commit) is valid and could
produce incomplete audit trails if the process crashes between flushes. This
is already deferred (W-25), so flagging it here for awareness only.

The NEW finding not in the deferred list: `transition_stage` calls
`get_application` (which re-queries with selectinload) as its final step
(line 199 in `application.py`). That second `get_application` call after the
stage mutation is the source of additional DB round trips: the tool calls
`transition_stage` twice, each of which issues a `SELECT` + attribute
mutation + another `SELECT` for the refreshed object. Four DB queries for what
could be two. Not critical, but adds latency.

---

### DS-12: `_extract_text_from_pdf_sync` does not close PDF handle on exception

**File:** `packages/api/src/services/extraction.py:190-201`

```python
@staticmethod
def _extract_text_from_pdf_sync(file_data: bytes) -> str | None:
    try:
        pdf = fitz.open(stream=file_data, filetype="pdf")
        text_parts = []
        for page in pdf:
            text_parts.append(page.get_text())
        pdf.close()        # only reached on success
        return " ".join(text_parts).strip()
    except Exception:
        logger.exception("Failed to open PDF with pymupdf")
        return None        # pdf.close() NOT called on exception
```

If `fitz.open` succeeds but `page.get_text()` raises, `pdf.close()` is never
called. pymupdf/fitz holds a file descriptor and native memory for the PDF
object. Under high document volume this could accumulate open handles until
Python's garbage collector finalizes the object, which is non-deterministic.

The same pattern exists in `_pdf_first_page_to_image_sync` (lines 214-227).

**Suggested fix:** Use a try/finally or context manager:

```python
try:
    pdf = fitz.open(stream=file_data, filetype="pdf")
    try:
        text_parts = [page.get_text() for page in pdf]
        return " ".join(text_parts).strip()
    finally:
        pdf.close()
except Exception:
    logger.exception("Failed to open PDF with pymupdf")
    return None
```

---

## Suggestion

### DS-13: `get_completion` in `inference/client.py` has no timeout, retry, or error logging

**File:** `packages/api/src/inference/client.py:38-52`

```python
async def get_completion(messages, tier, **kwargs) -> str:
    client = _get_client(tier)
    model_cfg = get_model_config(tier)
    response = await client.chat.completions.create(
        model=model_cfg["model_name"],
        messages=messages,
        **kwargs,
    )
    return response.choices[0].message.content or ""
```

Any network error, timeout, or model error from the OpenAI-compatible endpoint
propagates directly to the caller with no logging at this layer. When
`ExtractionService._extract_via_llm` catches `json.JSONDecodeError`, it logs
`"LLM returned non-JSON"` -- but if the LLM call itself raises
`openai.APIConnectionError` or `openai.Timeout`, the extraction pipeline logs
`"Extraction failed for document %s"` with the full traceback, which is
acceptable. The improvement here is adding a log line at the `get_completion`
layer itself for operational visibility into which tier/model failed, without
requiring callers to reconstruct that context from the traceback.

**Suggested fix:** Add structured logging on exception before re-raising:

```python
except Exception:
    logger.error("LLM completion failed (tier=%s, model=%s)", tier, model_cfg["model_name"],
                 exc_info=True)
    raise
```

---

### DS-14: `_compute_turn_times` join on audit events does not handle multiple transitions per application

**File:** `packages/api/src/services/analytics.py:121-183`

The query joins `to_events` and `from_events` on `application_id`. An
application that was returned to an earlier stage (e.g., sent back from
underwriting to application for more documents) would have multiple
`stage_transition` audit events for the same application and transition pair.
The join would produce a Cartesian product for that application, inflating the
average turn time. This is a data quality / correctness issue for the CEO
analytics dashboard in edge cases.

For demo/MVP with clean data this won't manifest, but it should be noted for
when real data volumes arrive.

**Suggested fix:** Take the minimum `from_ts` and maximum `to_ts` per
application in the subqueries to handle re-entries:

```sql
SELECT application_id, MIN(timestamp) as from_ts FROM ...
GROUP BY application_id
```

---

### DS-15: `search_events` in `audit.py` has a default limit of 500 with no documented maximum

**File:** `packages/api/src/services/audit.py:231-250`

`search_events` defaults to `limit=500` and the `ceo_audit_search` tool
allows the CEO to request up to the `limit` parameter (default 100) but passes
it through without validation. The audit service accepts whatever integer the
caller provides, including arbitrarily large values. A CEO asking for
`limit=10000` would load 10,000 ORM objects into memory.

This is consistent with `export_events` which has `limit=10_000` (intentional
for export). The difference is `search_events` formats results into strings in
the agent tool, which caps display at 50 -- so from a UX standpoint it's
bounded, but the DB query is unbounded.

**Suggested fix:** Add an upper bound in `search_events` (e.g., `limit =
min(limit, 1000)`) and document it.

---

### DS-16: `ConversationService.get_conversation_history` silently converts tool-call messages to empty strings

**File:** `packages/api/src/services/conversation.py:175-179`

```python
for msg in messages:
    role = "assistant" if getattr(msg, "type", "") == "ai" else "user"
    content = getattr(msg, "content", str(msg))
    if content:
        result.append({"role": role, "content": content})
```

LangGraph checkpoints contain `AIMessage` objects with `tool_calls` and
`ToolMessage` objects. When `AIMessage.content` is empty (which is common when
the model makes a tool call with no accompanying text), `content = ""` and the
message is filtered out (`if content`). When the UI uses history to render
conversation context, tool-invocation turns will be invisible in the history.
This may confuse users who saw "the assistant call a tool" in the original
session but see no trace of it in history.

**Suggested fix:** This is intentional for the UI (tool messages are internal
plumbing), but the behavior should be documented in the function docstring.
Add: "Note: tool call and tool response messages are excluded from history
(content is empty or None)."
