# Performance Review -- Pre-Phase 5

**Reviewer:** performance-engineer
**Date:** 2026-02-27
**Scope:** Full codebase (`packages/api/src/`)

## Findings

### [PE-01] Severity: Warning
**File(s):** `packages/api/src/services/audit.py:60-65`
**Finding:** The `write_audit_event` function acquires a PostgreSQL advisory lock (`pg_advisory_xact_lock`) and queries the latest audit event on every single write. This serializes all audit event inserts globally. During a typical WebSocket agent turn, `_chat_handler.py` writes audit events for every `on_tool_end` event (line 212-221), plus safety block events, tool auth events, etc. Each of those events acquires the lock, queries the latest row, computes a hash, inserts, and flushes -- all within the same transaction boundary of the caller. In a multi-user scenario, all concurrent audit writes across all sessions are serialized behind this single advisory lock, creating a global bottleneck.
**Impact:** Under concurrent load (e.g., 10+ simultaneous WebSocket chat sessions with active tool use), audit writes become the serialization point for the entire system. Every tool invocation blocks on the lock held by the previous audit write. Throughput degrades linearly with concurrent audit writers.
**Recommendation:** Batch audit events within a single request/turn: collect audit payloads in a list during the stream, then write them all in a single transaction at the end (one lock acquisition, one chain computation covering the batch). Alternatively, consider a two-phase approach: insert events without hashes immediately, then have a background task compute and backfill the hash chain periodically.

### [PE-02] Severity: Warning
**File(s):** `packages/api/src/services/audit.py:97-99`
**Finding:** `verify_audit_chain` loads the entire `audit_events` table into memory with `list(result.scalars().all())`. The audit table is append-only and grows unboundedly -- every tool invocation, safety check, stage transition, disclosure acknowledgment, and communication generates audit rows. After moderate usage, this table can have thousands to tens of thousands of rows.
**Impact:** Verifying the chain loads all rows plus their JSON `event_data` into Python memory. With 10,000 events each carrying ~500 bytes of JSON, that is ~5MB of data plus SQLAlchemy ORM overhead (~2-3x). The hash recomputation loop also runs `json.dumps(sort_keys=True)` on every row's event_data. This endpoint will become unusably slow and memory-intensive as the audit trail grows.
**Recommendation:** Implement paginated verification: walk the chain in batches of 500-1000, keeping only the last row from the previous batch for hash linkage. This bounds memory to O(batch_size) instead of O(total_events).

### [PE-03] Severity: Warning
**File(s):** `packages/api/src/services/condition.py:237-246` (`check_condition_documents`)
**Finding:** N+1 query pattern: for each document linked to a condition, a separate query fetches `DocumentExtraction` rows (lines 240-246 inside a `for doc in documents` loop). If a condition has 5 linked documents, this fires 5 additional queries beyond the initial document query.
**Impact:** Each additional linked document adds one more round-trip to the database. While the typical case may be 1-3 documents per condition, this pattern degrades linearly and is avoidable.
**Recommendation:** Replace the per-document extraction query with an eager-load on the initial document query, or query all extractions for the document IDs in a single batch:
```python
doc_ids = [doc.id for doc in documents]
ext_stmt = (
    select(DocumentExtraction)
    .where(DocumentExtraction.document_id.in_(doc_ids))
    .order_by(DocumentExtraction.document_id, DocumentExtraction.field_name)
)
```
Then group by `document_id` in Python.

### [PE-04] Severity: Warning
**File(s):** `packages/api/src/services/extraction.py:175-187` (`_extract_text_from_pdf`)
**Finding:** The `_extract_text_from_pdf` and `_pdf_first_page_to_image` methods are synchronous CPU-bound operations (pymupdf PDF parsing, text extraction, and page rendering). They run directly in the async `process_document` method without `run_in_executor`. While the extraction pipeline runs as a background task (not blocking the request), it still runs on the event loop thread, blocking all other async I/O (WebSocket messages, DB queries, HTTP requests) for the duration of PDF parsing.
**Impact:** A large multi-page PDF could block the event loop for 100ms-1s during text extraction. If multiple documents are uploaded simultaneously, the effect compounds. This is somewhat mitigated by the background task running after the upload response, but it still blocks the single-threaded event loop.
**Recommendation:** Wrap the synchronous pymupdf calls in `asyncio.get_running_loop().run_in_executor(None, ...)` to offload them to the thread pool, consistent with how `StorageService` already handles synchronous boto3 calls (see `storage.py:72-82`).

### [PE-05] Severity: Warning
**File(s):** `packages/api/src/services/compliance/checks.py:52-68` (`_business_days_between`)
**Finding:** The business days calculation uses a day-by-day loop (`while current < end: current += one_day`). For TRID checks comparing application creation to loan estimate delivery or closing disclosure to closing date, the date range is typically small (3-30 days), so this is not a bottleneck today. However, if dates are far apart (e.g., a missing `le_delivery_date` set to a far-future default, or stale test data with years-old applications), this loop iterates once per day.
**Impact:** Low for normal usage. Could become noticeable if called on applications with corrupt or distant date values (e.g., 365+ day spread = 365 iterations per call). Since compliance checks run three times per `compliance_check` tool call, degenerate inputs could cause 1000+ iterations.
**Recommendation:** Replace with an arithmetic business-day formula: `full_weeks * 5 + remainder_weekdays`. This computes in O(1) regardless of date spread:
```python
def _business_days_between(start: datetime, end: datetime) -> int:
    if end <= start:
        return 0
    d1, d2 = start.date(), end.date()
    total_days = (d2 - d1).days
    full_weeks, remainder = divmod(total_days, 7)
    start_dow = d1.weekday()
    weekend_days = sum(1 for i in range(remainder) if (start_dow + 1 + i) % 7 >= 5)
    return full_weeks * 5 + (remainder - weekend_days)
```

### [PE-06] Severity: Warning
**File(s):** `packages/api/src/services/status.py:107-113`, `packages/api/src/routes/applications.py:208-212`
**Finding:** `get_application_status` calls `check_completeness` (which internally calls `get_application` to verify scope), then separately calls `get_application` again at line 113. That is two `get_application` calls (each with a join through `ApplicationBorrower` -> `Borrower` via `selectinload`) for the same application in the same request. The route `get_status` at `routes/applications.py:208-212` then calls `get_application` a third time and `compute_urgency` (which triggers 3 more batch queries) for LO/admin roles. Total: 3 calls to `get_application` + completeness queries + urgency queries = at least 7 database round-trips for a single `/applications/{id}/status` request.
**Impact:** Each `get_application` fires a SELECT with two JOINs (ApplicationBorrower, Borrower). Three redundant calls waste ~3-6ms of DB time per request. Combined with the condition count query and urgency queries, a single status request triggers 7+ queries.
**Recommendation:** Pass the already-loaded `Application` object from `check_completeness` through the call chain rather than re-querying. `get_application_status` could accept an optional pre-loaded `app` parameter:
```python
async def get_application_status(session, user, application_id, *, app=None):
    if app is None:
        app = await get_application(session, user, application_id)
```

### [PE-07] Severity: Warning
**File(s):** `packages/api/src/agents/underwriter_tools.py:128-280` (`uw_application_detail`)
**Finding:** The `uw_application_detail` tool makes 4 sequential service calls within a single `SessionLocal()` context: `get_application` (line 143), `list_documents` (line 157), `get_conditions` (line 158), `get_rate_lock_status` (line 159). Each of these service calls internally calls `get_application` again for scope verification (see `get_conditions` line 57, `get_rate_lock_status` line 33). So `get_application` is called 4 times total for the same `application_id`. The same pattern appears in `lo_draft_communication` at `loan_officer_tools.py:455-462` (3 additional `get_application` calls from completeness, conditions, and rate_lock).
**Impact:** 4 redundant `get_application` calls per `uw_application_detail` invocation. Each call runs a SELECT with eager-loaded borrower data. This adds ~4-8ms of pure DB overhead per tool call, and these tools are called frequently during underwriter chat sessions.
**Recommendation:** Have service functions accept an optional pre-loaded `app` parameter to avoid re-querying when the caller has already verified scope. The tool would call `get_application` once, then pass the result downstream:
```python
app = await get_application(session, user, application_id)
conditions = await get_conditions(session, user, application_id, app=app)
rate_lock = await get_rate_lock_status(session, user, application_id, app=app)
```

### [PE-08] Severity: Warning
**File(s):** `packages/api/src/agents/underwriter_tools.py:592-757` (`uw_preliminary_recommendation`)
**Finding:** `uw_preliminary_recommendation` duplicates nearly all the data gathering of `uw_risk_assessment`: it calls `get_application`, queries `ApplicationFinancials`, calls `list_documents`, extracts borrower info, and runs `_compute_risk_factors`. In a typical underwriter workflow, the agent calls `uw_risk_assessment` first, then `uw_preliminary_recommendation` -- resulting in identical DB queries being executed twice. The same `_compute_risk_factors` pure function runs on the same data both times.
**Impact:** Double the DB round-trips (2x `get_application`, 2x `ApplicationFinancials` query, 2x `list_documents`) for what is effectively the same data. Adds ~10-20ms of redundant DB overhead per underwriting review workflow.
**Recommendation:** This is an architectural concern better solved at the agent level (e.g., caching tool results within a turn). At minimum, the recommendation tool could accept pre-computed risk factors from a prior assessment. Alternatively, merge both tools into a single `uw_risk_assessment` that always includes the recommendation section, since they are typically called together.

### [PE-09] Severity: Warning
**File(s):** `packages/api/src/routes/_chat_handler.py:119-131` (`_audit` inner function)
**Finding:** The `_audit` helper opens a new DB session via `async for db_session in get_db()` for every audit write during the streaming loop. This means each `on_tool_end` event, each safety block, and each tool auth denial creates a new session, acquires the advisory lock (PE-01), and commits. During a single agent turn that invokes 3-4 tools, this creates 3-4 separate DB sessions and transactions just for audit logging.
**Impact:** Each audit event during streaming is a full round-trip: open session -> acquire lock -> query latest -> insert -> commit -> close. With 3 tools per turn and the advisory lock serialization, this adds ~15-30ms of latency to each agent turn purely for audit overhead.
**Recommendation:** Accumulate audit events in a list during the stream, then flush them all in a single session/transaction after the agent turn completes (before sending the `done` message). This reduces N sessions to 1 and N lock acquisitions to 1.

### [PE-10] Severity: Suggestion
**File(s):** `packages/api/src/services/application.py:197`, `packages/api/src/services/application.py:222`, `packages/api/src/services/application.py:155`
**Finding:** `update_application`, `transition_stage`, and `create_application` all call `get_application` (with full eager loading of borrowers) as their final step to return the updated object. This is necessary to avoid lazy-load errors in async context, but `create_application` calls it twice: once after the initial commit (line 155 calls `get_application`) and the create itself already did a `session.flush()`. The `transition_stage` and `update_application` methods each call `get_application` twice total: once to load the app for modification, once to reload after commit.
**Impact:** Each write operation on applications triggers 2 full SELECT queries with borrower joins. For `create_application`, the second `get_application` call at line 155 is the third query in the function (after the borrower lookup and the flush).
**Recommendation:** After `session.commit()`, use `session.refresh(application, attribute_names=[...])` with explicit attributes, or re-add the `selectinload` options to a single targeted query, instead of calling the full `get_application` which also re-applies data scope filtering (unnecessary since we just wrote the record).

### [PE-11] Severity: Suggestion
**File(s):** `packages/api/src/services/decision.py:37-53` (`_get_ai_recommendation`)
**Finding:** To find the AI recommendation, this function queries the 20 most recent `tool_call` audit events for the application and scans them in Python looking for `uw_preliminary_recommendation` in the `event_data` JSON. The query is `ORDER BY timestamp DESC LIMIT 20` with a filter on `event_type = 'tool_call'`. This is a sequential scan through audit events, and the Python loop does a JSON dict lookup on each row.
**Impact:** Low for current usage (audit events per application are typically <100). However, the query lacks a composite index on `(application_id, event_type)`, relying on separate single-column indexes. As audit volume grows, this query performance may degrade. The bigger concern is the semantic fragility: if the recommendation was made more than 20 tool calls ago, it will not be found.
**Recommendation:** Add a composite index `(application_id, event_type, timestamp DESC)` on `audit_events` to optimize this pattern. Consider also filtering in SQL by checking `event_data->>'tool' = 'uw_preliminary_recommendation'` using PostgreSQL JSON operators, reducing the number of rows transferred to Python.

### [PE-12] Severity: Suggestion
**File(s):** `packages/api/src/services/document.py:149-218` (`upload_document`)
**Finding:** The `upload_document` function reads the entire file into memory as `bytes` (line 80 in the route, `file_data = await file.read()`), validates the size in Python (line 176), then passes the full byte array to `storage.upload_file`. For the configured max upload size, the entire file must fit in server memory. With concurrent uploads, memory usage scales linearly with the number of simultaneous uploads multiplied by the max file size.
**Impact:** At MVP scale this is fine. With a 10MB max upload size and 10 concurrent uploads, that is 100MB of memory just for file buffers. For a demo application this is acceptable, but the pattern does not scale.
**Recommendation:** Defer to Phase 5+ or production hardening. For future reference: use `SpooledTemporaryFile` with a threshold to spill large uploads to disk, and use streaming upload to S3 via multipart upload.

### [PE-13] Severity: Suggestion
**File(s):** `packages/api/src/services/completeness.py:296-344` (`check_underwriting_readiness`)
**Finding:** `check_underwriting_readiness` calls `get_application` (line 308) and then calls `check_completeness` (line 323), which internally calls `get_application` again (line 216). This is 2 calls to `get_application` for the same resource in the same function. The `lo_submit_to_underwriting` tool in `loan_officer_tools.py:377-430` calls `check_underwriting_readiness` (triggering 2 `get_application` calls), then on success calls `transition_stage` twice (each calling `get_application` again), for a total of 6 `get_application` calls during a single "submit to underwriting" operation.
**Impact:** 6 redundant queries with eager-loaded borrower data during the critical "submit to underwriting" flow. This is the same pattern as PE-07 but amplified by the two stage transitions.
**Recommendation:** Same as PE-07: accept optional pre-loaded `app` parameter in service functions to avoid re-querying.

### [PE-14] Severity: Suggestion
**File(s):** `packages/api/src/routes/applications.py:123-125`
**Finding:** When listing applications for LO/admin roles, the route first queries applications (with pagination), then calls `compute_urgency` which fires 3 additional batch queries (rate locks, conditions, pending docs). These batch queries operate on the already-paginated result set (typically 20 applications), which is a reasonable batch size. However, urgency sort (`sort_by=urgency`) happens in Python after pagination (line 130-136), meaning it only sorts within the current page -- not globally. An application with CRITICAL urgency on page 2 will never appear on page 1 when sorted by urgency.
**Impact:** Functional correctness issue that manifests as a performance concern: to get a correctly urgency-sorted list, the system would need to load all applications and compute urgency for all of them before paginating. With the current design, urgency sort is approximate (within-page only).
**Recommendation:** Document this limitation clearly in the API docs as "urgency sort is within-page only." For correct urgency sort, consider denormalizing urgency level into the Application table (computed on a schedule or on stage/condition changes) so it can be sorted in SQL.

### [PE-15] Severity: Suggestion
**File(s):** `packages/api/src/services/compliance/knowledge_base/search.py:62-78`
**Finding:** The KB search fetches `top_k * 3` candidates from pgvector (line 63), applies tier boosting and minimum similarity filtering in Python, then re-sorts and truncates. With `top_k=5`, this fetches 15 rows. The HNSW index (confirmed in migration `f7a8b9c0d1e2`) handles the vector search efficiently. However, the query passes the embedding vector as a string (`str(query_vec)`) in line 79, requiring PostgreSQL to parse a text representation of a 768-dimension float array on every query.
**Impact:** Parsing a 768-element float array from string adds unnecessary overhead to each KB search. The overhead is small (~1-2ms) but avoidable.
**Recommendation:** Pass the embedding as a proper list/array parameter rather than stringifying it. SQLAlchemy with pgvector supports passing Python lists directly as vector parameters. If using raw SQL via `text()`, use a parameterized cast: `:query_vec::vector`.

### [PE-16] Severity: Suggestion
**File(s):** `packages/api/src/services/compliance/knowledge_base/ingestion.py:169-238` (`ingest_kb_content`)
**Finding:** During KB ingestion, each markdown file is processed sequentially: parse, chunk, embed, and store. The embedding call (`get_embeddings(chunk_texts)`) batches all chunks for a single document, which is good. However, documents are processed one at a time in a loop (line 175-234), and each document triggers a `session.flush()` (line 199) plus individual `session.add()` for each chunk. Additionally, `md_file.read_text()` at line 176 is a synchronous file I/O operation in an async context.
**Impact:** Ingestion is a one-time/infrequent operation (idempotent re-ingestion), so this is not a hot path. The synchronous file reads are on small markdown files (<50KB each) and the number of files is small (8 currently). Low practical impact.
**Recommendation:** Low priority. For future KB growth: batch embedding calls across documents, use `session.add_all()` for chunk insertion, and wrap `md_file.read_text()` in `run_in_executor` if KB grows to hundreds of files.

### [PE-17] Severity: Suggestion
**File(s):** `packages/api/src/services/disclosure.py:72-81` (`get_disclosure_status`)
**Finding:** `get_disclosure_status` loads all `disclosure_acknowledged` audit events for an application into memory to determine which 4 disclosures have been acknowledged. This queries potentially many rows (if the same disclosure is acknowledged multiple times or if audit events accumulate) when only the existence of 4 specific `disclosure_id` values matters.
**Impact:** Low. The number of disclosure_acknowledged events per application is bounded by user interactions (typically 4-8 acknowledgments). The entire result set is small.
**Recommendation:** Optimize with a DISTINCT query on the JSON field:
```python
stmt = (
    select(func.distinct(AuditEvent.event_data['disclosure_id'].astext))
    .where(
        AuditEvent.event_type == "disclosure_acknowledged",
        AuditEvent.application_id == application_id,
    )
)
```
This returns at most 4 scalar values instead of full event rows.

### [PE-18] Severity: Warning
**File(s):** `packages/api/src/routes/_chat_handler.py:252-255`
**Finding:** The WebSocket chat handler has no explicit cleanup of agent/graph state when a client disconnects. The `finally` block at line 254 only calls `flush_langfuse()`. There is no mechanism to cancel in-flight LLM requests or tool executions when the WebSocket closes. If a user disconnects mid-stream, the `graph.astream_events` generator continues running until the current LLM response or tool call completes, consuming compute and DB resources for an abandoned session.
**Impact:** Under normal usage, LLM responses complete within 5-30 seconds, so abandoned work is bounded. However, if many users disconnect during active tool execution (e.g., during slow KB searches or compliance checks), the server accumulates orphaned async tasks consuming DB connections and LLM inference slots.
**Recommendation:** Wrap the `graph.astream_events` call in an `asyncio.shield`/cancellation pattern. When the WebSocket `receive_text()` raises a disconnect exception, cancel the running astream task. Alternatively, set a timeout on agent turns (e.g., 60 seconds) using `asyncio.wait_for`.

### [PE-19] Severity: Suggestion
**File(s):** `packages/db/src/db/models.py:197-230` (Condition model), `packages/api/src/services/urgency.py:225-242`
**Finding:** The `Condition` model has an index on `application_id` but no composite index on `(application_id, status)`. The `_batch_open_condition_counts` query in urgency.py filters by both `application_id IN (...)` and `status NOT IN (...)`, and the `get_conditions` service also filters by `application_id` + `status`. The condition count query in `status.py:129-137` also filters by both columns.
**Impact:** Without a composite index, PostgreSQL must scan all conditions for the given application IDs and then filter by status in memory. For applications with many conditions (e.g., 20+ conditions after several review iterations), this adds unnecessary work.
**Recommendation:** Add a composite index `(application_id, status)` on the `conditions` table. This benefits all the query patterns that filter by both columns.

### [PE-20] Severity: Warning
**File(s):** `packages/api/src/services/audit.py:60-82` (`write_audit_event`), `packages/api/src/routes/_chat_handler.py:119-131`
**Finding:** Every `write_audit_event` call acquires a transaction-scoped advisory lock (line 60) and queries `SELECT * FROM audit_events ORDER BY id DESC LIMIT 1` (line 63). This query scans the index on `id` descending. However, there is no covering index that includes the fields needed for hash computation (`id`, `timestamp`, `event_data`), so each call requires an index lookup plus a heap fetch for the most recent row. More critically, the `_chat_handler.py` audit pattern opens a NEW session for each audit write (line 121: `async for db_session in get_db()`), which means each audit write is its own transaction. The advisory lock is transaction-scoped, so it is released immediately after each commit -- defeating the purpose of serialization if two concurrent audit writes interleave between the lock release and the next acquisition.
**Impact:** The advisory lock provides serialization only within a single transaction. Since each audit event in the chat handler runs in its own transaction, two concurrent chat sessions could both read the same "latest" event between their respective lock acquisitions, compute the same `prev_hash`, and break the chain integrity. This is both a correctness issue and a performance concern (the lock overhead provides no benefit in this usage pattern).
**Recommendation:** For the chat handler path, batch audit events and write them in a single transaction (as recommended in PE-09). This ensures the advisory lock actually serializes correctly. For non-chat paths where `write_audit_event` is called within an existing transaction (e.g., decision rendering), the current pattern works correctly.
