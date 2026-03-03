# Performance Review -- Pre-Phase 3

Reviewer: Performance Engineer
Date: 2026-02-26
Scope: packages/api/src/services/, packages/api/src/routes/, packages/api/src/agents/, packages/db/

---

## PERF-01: Audit chain verification loads entire audit_events table into memory
**Severity:** Critical
**Location:** packages/api/src/services/audit.py:97-99
**Description:** `verify_audit_chain()` executes `select(AuditEvent).order_by(AuditEvent.id.asc())` with no LIMIT, then calls `list(result.scalars().all())`, loading every audit event row into Python memory at once. Every WebSocket message generates at least one audit event (tool_invocation, safety_block, etc.), and the chat handler writes audit events for each streamed response. The table will grow unboundedly.
**Impact:** With 10k+ audit events (easily reachable after a few dozen chat sessions), this query will consume 100+ MB of RAM per invocation and take multiple seconds. At 100k+ rows it becomes a denial-of-service vector against the `/api/admin/audit/verify` endpoint.
**Recommendation:** Implement streaming/batched verification that walks the chain in fixed-size pages (e.g., 1000 rows at a time), carrying only the previous event's hash forward between pages. This reduces peak memory from O(N) to O(batch_size).

---

## PERF-02: N+1 query pattern in condition document checking
**Severity:** Critical
**Location:** packages/api/src/services/condition.py:262-271
**Description:** `check_condition_documents()` fetches documents for a condition, then loops over each document and executes a separate `SELECT` for its `DocumentExtraction` rows. This is a classic N+1 pattern -- one query per document.
**Impact:** If a condition has 5 linked documents, this produces 6 queries (1 for documents + 5 for extractions). Latency scales linearly with document count, adding ~5-10ms per additional document due to round-trip overhead.
**Recommendation:** Use `selectinload(Document.extractions)` on the document query at line 254 to batch-load all extractions in a single query:
```python
doc_stmt = (
    select(Document)
    .options(selectinload(Document.extractions))
    .where(Document.condition_id == condition_id)
    .order_by(Document.created_at.desc())
)
```

---

## PERF-03: Document upload reads entire file into memory
**Severity:** Warning
**Location:** packages/api/src/routes/documents.py:72
**Description:** `file_data = await file.read()` reads the entire uploaded file into a `bytes` object in memory. The file is then validated for size (line 133 of document.py checks `len(file_data) > max_bytes`), uploaded to S3, and later downloaded again for extraction. The entire file lives in the async worker's memory during the upload request.
**Impact:** With the default upload limit (likely 10-25MB per the `UPLOAD_MAX_SIZE_MB` setting), a few concurrent uploads can consume hundreds of MB. Since FastAPI runs on a single event loop, large uploads block other coroutines during the `await file.read()` call.
**Recommendation:** Use `file.read(chunk_size)` in a loop with an accumulating size counter to fail fast on oversized files without reading the full body. For the S3 upload, consider using boto3 multipart upload for files over a threshold (e.g., 5MB).

---

## PERF-04: Extraction pipeline downloads entire file into memory for PDF processing
**Severity:** Warning
**Location:** packages/api/src/services/extraction.py:76
**Description:** `file_data = await storage.download_file(file_path)` downloads the entire document from S3 into a `bytes` object. This is then passed to pymupdf which opens it as an in-memory stream. For scanned PDFs, the file is rendered to PNG images (line 169), creating additional large byte arrays.
**Impact:** A 20MB scanned PDF will use ~20MB for the download, plus ~20-50MB for rendered page images (pymupdf pixmap), plus the base64-encoded version for LLM vision (~27MB for a 20MB image). Peak memory per extraction can reach 100+ MB.
**Recommendation:** For text extraction, pymupdf can open files from a file path. Write the downloaded bytes to a temporary file, then pass the path to pymupdf instead of keeping the full content in memory. For image rendering, process one page at a time and send to LLM immediately rather than collecting all images in a list (currently `_pdf_pages_to_images` returns `list[bytes]` but only `images[0]` is used at line 173).

---

## PERF-05: Repeated application scope verification queries in condition service
**Severity:** Warning
**Location:** packages/api/src/services/condition.py:42-55, 93-106, 161-172, 229-240
**Description:** Every method in the condition service (`get_conditions`, `respond_to_condition`, `link_document_to_condition`, `check_condition_documents`) executes the same full application-with-borrowers query to verify scope. This includes `selectinload(Application.application_borrowers).joinedload(ApplicationBorrower.borrower)` even though only the application's existence and scope are needed.
**Impact:** Each condition operation requires a minimum of 2 queries (scope check + actual work). The scope check eagerly loads borrower data that is never used. For a borrower checking 5 conditions, this is 10 unnecessary borrower loads.
**Recommendation:** Extract a lightweight `verify_application_scope()` helper that does `select(Application.id).where(Application.id == application_id)` with `apply_data_scope()` -- no eager loading of borrowers. The current pattern loads the full application graph just to check if it exists.

---

## PERF-06: Status endpoint triggers cascading redundant queries
**Severity:** Warning
**Location:** packages/api/src/services/status.py:112-117
**Description:** `get_application_status()` first calls `check_completeness()` (which loads the application with borrowers, then queries documents with scope joins), then calls `get_application()` again (which loads the same application with borrowers a second time). The application is fetched twice with identical eager loading.
**Impact:** The `/api/applications/{id}/status` endpoint executes at least 4 queries: (1) completeness loads app+borrowers, (2) completeness queries documents, (3) `get_application` loads app+borrowers again, (4) conditions count query. The second app load is pure waste.
**Recommendation:** Have `check_completeness()` return the loaded application as part of its result, or extract the shared application load so `get_application_status()` can pass the already-loaded app to both functions.

---

## PERF-07: Intake service re-queries application multiple times per field update
**Severity:** Warning
**Location:** packages/api/src/services/intake.py:199-260, 270-304
**Description:** `update_application_fields()` loads the application at line 200, gets the borrower at line 211, gets financials at line 215, does the updates, then calls `get_remaining_fields()` at line 260 which re-executes the same application query, borrower query, and financials lookup all over again.
**Impact:** Every `update_application_data` tool invocation from the borrower chat (which happens per conversational exchange during intake) executes 6+ queries where 3 would suffice. During a typical intake conversation with 10-14 field updates, this adds ~30 unnecessary queries.
**Recommendation:** After applying updates, compute remaining fields from the already-loaded objects (`app`, `borrower`, `financials`) instead of re-querying them.

---

## PERF-08: Advisory lock serializes ALL audit writes across ALL concurrent connections
**Severity:** Warning
**Location:** packages/api/src/services/audit.py:60
**Description:** `pg_advisory_xact_lock(900001)` acquires a transaction-level advisory lock, meaning only one audit event can be written at a time across all database sessions. Every WebSocket message that triggers a tool or safety check calls `write_audit_event()`, which means concurrent chat sessions serialize on this lock.
**Impact:** Under load with N concurrent chat sessions, audit writes become a global bottleneck. If each chat message generates 2-3 audit events and an advisory lock acquisition + query + insert takes ~5ms, 10 concurrent users would see ~50-150ms of lock contention per message.
**Recommendation:** For MVP this is acceptable since hash chain integrity requires serialization. For Phase 3+, consider batching audit writes per WebSocket message (collect all events, write them in one transaction with one lock acquisition) or moving to a sequence-based prev_hash that doesn't require querying the latest row.

---

## PERF-09: Missing index on audit_events.session_id
**Severity:** Warning
**Location:** packages/db/src/db/models.py:323
**Description:** `AuditEvent.session_id` has no index, but `get_events_by_session()` at audit.py:137 queries `WHERE session_id = ?` and the admin route at admin.py:71 exposes this as a user-facing endpoint. The `disclosure.py` service also queries `WHERE event_type = 'disclosure_acknowledged' AND application_id = ?`.
**Impact:** Session-based audit queries will do full table scans. As the audit table grows (it's append-only and never pruned), query time degrades linearly. With 100k audit events, a session lookup could take 50-100ms vs <1ms with an index.
**Recommendation:** Add `index=True` to the `session_id` column definition. Consider a composite index on `(event_type, application_id)` for the disclosure status queries.

---

## PERF-10: Synchronous boto3 S3 client blocks the event loop thread pool
**Severity:** Warning
**Location:** packages/api/src/services/storage.py:71-81
**Description:** The StorageService uses the synchronous boto3 client wrapped in `loop.run_in_executor(None, ...)`, which dispatches to the default ThreadPoolExecutor. The default executor has a small thread pool (typically `min(32, os.cpu_count() + 4)`). S3 operations (upload, download) are network-bound and can take 100ms-1s+.
**Impact:** Under load, the default thread pool becomes saturated with S3 operations, blocking other `run_in_executor` calls (including other S3 ops and potentially other sync libraries). With 5 concurrent document uploads, 5 of the ~8 default threads are consumed.
**Recommendation:** Create a dedicated `ThreadPoolExecutor` for S3 operations so they don't contend with other thread-pool users. Alternatively, switch to `aiobotocore` for native async S3 operations. For MVP, a dedicated executor is the minimal fix.

---

## PERF-11: Per-message audit writes in WebSocket handler create excessive DB round-trips
**Severity:** Warning
**Location:** packages/api/src/routes/_chat_handler.py:117-130
**Description:** The `_audit()` helper creates a new database session (`async for db_session in get_db()`) for every single audit event. During one user message, the handler may write audit events for: tool_invocation (per tool), safety_block, tool_auth_denied. Each event is a separate session with its own connection checkout, advisory lock, query, insert, commit, and connection return.
**Impact:** A single chat message that invokes 2 tools generates 2 `_audit()` calls, each requiring a full DB session lifecycle. At 5 concurrent users sending messages, this is 10+ short-lived sessions per second just for audit writes, each contending on the advisory lock from PERF-08.
**Recommendation:** Collect audit events during the stream processing and write them in a single batch at the end of the message (after the `done` event), using one DB session and one advisory lock acquisition.

---

## PERF-12: LLM classifier adds latency to every chat message
**Severity:** Warning
**Location:** packages/api/src/agents/base.py:123-142
**Description:** Every user message goes through the `classify` node which makes a full LLM round-trip to determine if the query is SIMPLE or COMPLEX. The classify call uses the `fast_small` model, but even fast models have 100-500ms latency. This happens before any actual work begins.
**Impact:** Adds 100-500ms of latency to every single chat message, including trivial follow-ups like "yes" or "ok". The fallback to rule-based classification (line 137) only activates on LLM failure, not as a fast path.
**Recommendation:** Run the rule-based classifier first as a fast path. If the rule-based classifier has high confidence (e.g., message is very short, or contains clear tool-triggering keywords), skip the LLM classification entirely. Only invoke the LLM classifier for ambiguous messages.

---

## PERF-13: Agent graph rebuilds ChatOpenAI instances on every YAML mtime change
**Severity:** Info
**Location:** packages/api/src/agents/registry.py:63-84, borrower_assistant.py:69-76
**Description:** When `get_agent()` detects a YAML config mtime change, it calls `build_graph()` which creates new `ChatOpenAI` instances for every model tier (lines 70-76 of borrower_assistant.py). Each `ChatOpenAI` instance creates new HTTP connection pools internally. The old instances (and their connection pools) are left for garbage collection.
**Impact:** During development with frequent config edits, each reload creates new HTTP connections to the LLM endpoint. In production this is rare (config rarely changes), but during development it can cause connection pool churn. Minor impact.
**Recommendation:** No immediate action needed for MVP. For production, consider reusing LLM clients across graph rebuilds if only the system prompt changes.

---

## PERF-14: SQLAlchemy engines created without connection pool tuning
**Severity:** Info
**Location:** packages/db/src/db/database.py:16-22
**Description:** Both `engine` and `compliance_engine` are created with `create_async_engine(url, echo=...)` using default pool settings. The defaults are: `pool_size=5`, `max_overflow=10`, `pool_timeout=30`, `pool_recycle=-1` (disabled). Two separate engines means two separate pools, consuming up to 30 connections total (2 engines x 15 max).
**Impact:** The default `pool_size=5` may be insufficient under load when multiple concurrent WebSocket sessions each need DB connections for tool invocations, audit writes, and scope checks. Conversely, the `pool_recycle=-1` default means connections are never recycled, which can cause stale connection errors behind connection-killing proxies or PgBouncer.
**Recommendation:** Set `pool_recycle=3600` (1 hour) to prevent stale connections. Monitor whether `pool_size=5` is sufficient during Phase 3 load testing. Consider adding `pool_pre_ping=True` for resilience.

---

## PERF-15: PII masking round-trips through model_dump/model_construct
**Severity:** Info
**Location:** packages/api/src/routes/applications.py:80-87
**Description:** For PII-masked responses, the code serializes each `ApplicationResponse` to a dict via `model_dump(mode="json")`, applies masking, then reconstructs the model via `model_construct()`. For list endpoints, this happens per item in the list.
**Impact:** On a list of 20 applications with 2 borrowers each, this is 20 `model_dump` + 20 `model_construct` calls. With Pydantic v2's fast serialization this is ~1ms total, so the impact is minimal. Only affects CEO-role users.
**Recommendation:** No action needed for MVP. If this shows up in profiling, masking could be applied directly to the ORM objects before serialization.

---

## PERF-16: Extraction pipeline only processes first page of scanned PDFs
**Severity:** Info
**Location:** packages/api/src/services/extraction.py:169-173
**Description:** `_pdf_pages_to_images()` renders ALL pages of a scanned PDF to PNG images, but `_process_pdf()` only sends `images[0]` (the first page) to the LLM. Multi-page scanned documents waste CPU rendering pages 2-N that are never used.
**Impact:** Rendering a 10-page scanned PDF creates 10 PNG images (~2-5MB each), uses ~20-50MB of memory, and spends ~1-2 seconds on rendering -- all for pages that are discarded.
**Recommendation:** Only render the first page: `page = pdf[0]; pix = page.get_pixmap()` instead of iterating all pages. If multi-page extraction is needed later, process pages one at a time with early termination.

---

## PERF-17: Agent tools create independent DB sessions instead of sharing
**Severity:** Info
**Location:** packages/api/src/agents/borrower_tools.py:71, 121, 175, 292, 320, 365, 427, 469, 501, 571, 627, 677
**Description:** Every borrower tool function creates its own `async with SessionLocal() as session:` context. When the LLM invokes multiple tools in sequence (e.g., `start_application` then `update_application_data` then `get_application_summary`), each gets a separate DB session, separate connection checkout, and separate transaction.
**Impact:** A typical intake turn may invoke 2-3 tools, creating 2-3 independent sessions. Each session checkout and return adds ~1-2ms. The sessions also don't share cached ORM objects, so the same application may be loaded multiple times across tool calls.
**Recommendation:** For MVP this is acceptable since LangGraph tools run independently. For Phase 3+, consider a session-per-turn pattern where a single DB session is created at the start of the agent turn and passed through the tool invocations via the graph state.
