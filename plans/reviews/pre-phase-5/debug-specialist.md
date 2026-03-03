# Debug/Error Handling Review -- Pre-Phase 5

**Reviewer:** debug-specialist
**Date:** 2026-02-27
**Scope:** Full codebase (`packages/api/src/`)

## Findings

### [DS-01] Severity: Critical
**File(s):** `packages/api/src/services/document.py:149-219`
**Finding:** `upload_document` creates a DB row and then calls S3 storage. If the S3 upload fails, the Document row exists with `status=UPLOADED` and no `file_path`, but the exception propagates without rolling back the DB row. The background extraction task will later attempt to download a nonexistent S3 object, fail, and set `PROCESSING_FAILED`. Meanwhile the borrower sees a phantom document with no content.
**Failure Scenario:** MinIO is down or times out during `storage.upload_file()`. The DB now has a Document row with `file_path=None` and `status=UPLOADED`. The extraction background task fires against a None path, hits an exception in `_guess_content_type(None)`, and crashes.
**Recommendation:** Wrap the S3 upload in try/except. On failure, either delete the Document row or set its status to a new `UPLOAD_FAILED` status. At minimum, do not fire the extraction background task if `upload_document` returns None or raises.

### [DS-02] Severity: Critical
**File(s):** `packages/api/src/routes/_chat_handler.py:242-250`
**Finding:** The inner `except Exception` that catches agent invocation failures sends an error message to the WebSocket but does NOT break out of the `while True` loop. The client can keep sending messages after the agent has failed, and each message will re-invoke `graph.astream_events` -- likely failing again in the same way. This creates a tight loop of exceptions + error messages with no backoff or circuit-breaking.
**Failure Scenario:** LLM endpoint goes down. Every subsequent user message triggers a full exception chain (graph construction, HTTP timeout, exception logging, WebSocket error message). The server logs fill with repeated stack traces. The client receives an error message but may keep sending messages, generating unbounded error volume.
**Recommendation:** Add a failure counter. After N consecutive agent invocation failures (e.g., 3), send a final error message explaining the service is unavailable and close the WebSocket. Alternatively, break out of the loop after the first agent failure if the error is a connection/infrastructure error rather than a transient one.

### [DS-03] Severity: Critical
**File(s):** `packages/api/src/services/audit.py:58-83`
**Finding:** The advisory lock `pg_advisory_xact_lock` serializes all audit writes globally. This means every concurrent request that writes an audit event (every tool call, every WebSocket message, every stage transition) is serialized behind a single lock. Under load with multiple concurrent agents, this becomes a severe bottleneck -- all audit writes queue up sequentially.
**Failure Scenario:** Five concurrent WebSocket sessions each invoking tools that write audit events. Each tool call acquires the advisory lock, fetches the latest event, computes the hash, inserts, and commits. With ~100ms per audit write, throughput is capped at ~10 audit events/second regardless of available DB connections or CPU.
**Recommendation:** For MVP, this is acceptable if documented as a known scaling limitation. For production readiness, consider batch audit writes (accumulate within a transaction and flush), or replace the global lock with a per-application lock (`pg_advisory_xact_lock(AUDIT_LOCK_KEY, application_id)`) so different applications can audit concurrently.

### [DS-04] Severity: Critical
**File(s):** `packages/api/src/services/condition.py:89-143`, `packages/api/src/services/condition.py:422-468`
**Finding:** Condition lifecycle operations (respond, clear, waive, return) perform read-then-write without any row-level locking. Two concurrent requests to respond to the same condition will both read `status=OPEN`, both set `status=RESPONDED`, and both succeed without conflict. Similarly, two concurrent `clear_condition` calls could both succeed, writing duplicate audit events.
**Failure Scenario:** Borrower submits a condition response via chat while also responding via the API endpoint simultaneously. Both requests read `status=OPEN`, both transition to `RESPONDED`. No error, but the audit trail shows two `condition_response` events for the same condition, creating an inconsistent record.
**Recommendation:** Add `SELECT ... FOR UPDATE` (via `with_for_update()`) when fetching the condition row before modifying it. This ensures only one writer proceeds at a time for a given condition.

### [DS-05] Severity: Critical
**File(s):** `packages/api/src/services/decision.py:235-348`
**Finding:** `render_decision` modifies the Application stage AND creates a Decision record AND writes audit events in a single transaction, but there is no row-level lock on the Application. Two concurrent decision renders for the same application (e.g., two underwriters with the same application open) could both read the application in `UNDERWRITING` stage, both pass validation, and both create Decision records while racing to set the new stage.
**Failure Scenario:** Two underwriters independently call `uw_render_decision` with `confirmed=true` on the same application within milliseconds. Both read `stage=UNDERWRITING`, both pass `_resolve_decision` validation, both create Decision records, and the last commit wins on the stage update. The audit trail shows two decisions for the same application, one of which may be logically invalid.
**Recommendation:** Add `SELECT ... FOR UPDATE` on the Application row in `_resolve_decision` (or at the start of `render_decision`) to serialize concurrent decisions on the same application.

### [DS-06] Severity: Warning
**File(s):** `packages/api/src/routes/_chat_handler.py:131-132`
**Finding:** Audit event write failures are silently swallowed with only a warning log. The `_audit` helper catches all exceptions and logs them, but the main flow continues. If the database is down, every audit write in the streaming loop fails silently, and the user's entire conversation proceeds with zero audit trail. For a regulated financial application where audit is a compliance requirement, silent audit failure is a significant gap.
**Failure Scenario:** Database connection pool exhausted. All `_audit()` calls fail. The conversation continues normally -- the borrower provides SSN, income, employment data -- with no audit record of any of it. When compliance asks for the audit trail later, there is nothing.
**Recommendation:** At minimum, track consecutive audit failures and log at ERROR level after N consecutive failures. Consider sending a system-level warning to the WebSocket session indicating that audit recording is degraded. For production, consider failing the conversation if audit cannot be maintained (compliance requirement).

### [DS-07] Severity: Warning
**File(s):** `packages/api/src/agents/base.py:178-194`
**Finding:** The `agent_fast` node calls `fast_llm.bind(logprobs=True)` and then `ainvoke(messages)` with no try/except. If the fast LLM endpoint is down or returns an error, the exception propagates through LangGraph and crashes the entire agent turn. The `agent_capable` node has the same issue (line 202-207). Neither node handles LLM invocation failures.
**Failure Scenario:** LLM endpoint returns 503 or times out. The exception propagates from `ainvoke` up through LangGraph's streaming, is caught by the outer `except Exception` in `_chat_handler.py:242`, and the user gets a generic "temporarily unavailable" error. But the error message logged by `logger.exception("Agent invocation failed")` does not include which model tier failed, what the input was, or which agent was involved.
**Recommendation:** Add try/except in `agent_fast` and `agent_capable` that catches LLM invocation errors and returns a structured error message to the graph state. Log the failure with model tier, endpoint, and truncated input for debugging. This also allows the graph to potentially recover (e.g., if fast model fails, escalate to capable model rather than crashing).

### [DS-08] Severity: Warning
**File(s):** `packages/api/src/services/storage.py:57-63`
**Finding:** `_ensure_bucket` catches all `ClientError` exceptions from `head_bucket` and assumes the bucket doesn't exist, then calls `create_bucket`. But `ClientError` can be raised for reasons other than "bucket not found" -- e.g., permission denied, invalid credentials, network error. In those cases, `create_bucket` will also fail, and the StorageService constructor will crash during app startup with an unhelpful error.
**Failure Scenario:** MinIO credentials are wrong. `head_bucket` raises `ClientError(403 Forbidden)`. The code catches it and tries `create_bucket`, which also raises `ClientError(403 Forbidden)`. The app crashes on startup with a boto3 error that doesn't clearly indicate "bad credentials."
**Recommendation:** Check the error code on the `ClientError`. Only attempt `create_bucket` for 404 (NoSuchBucket). For other errors (403, connection refused), let them propagate with a clear log message indicating the root cause.

### [DS-09] Severity: Warning
**File(s):** `packages/api/src/services/extraction.py:149-155`
**Finding:** The outer `except Exception` in `process_document` catches extraction failures and attempts to update the document status to `PROCESSING_FAILED`. But this secondary update is done on the same session that may already be in an invalid state (e.g., if the original exception was a DB error). The secondary `session.commit()` could also fail, and its failure is caught by a nested `except Exception` that only logs.
**Failure Scenario:** A database error occurs during extraction (e.g., unique constraint violation when inserting `DocumentExtraction`). The session is now in a bad state. The outer except tries to set `doc.status = PROCESSING_FAILED` and `session.commit()`, which may raise again because the session hasn't been rolled back. The nested except catches this, logs it, and the document is left in `PROCESSING` status forever -- never retried, never marked failed.
**Recommendation:** Call `await session.rollback()` before attempting the status update in the outer except block. This ensures the session is in a clean state for the status update. Alternatively, open a new session for the error-recovery status update.

### [DS-10] Severity: Warning
**File(s):** `packages/api/src/inference/client.py:38-52`
**Finding:** `get_completion` has no error handling at all. If the LLM endpoint returns a non-200 response, an HTTP error, or the response has no choices, the exception propagates with no context about which tier, model, or endpoint was being called.
**Failure Scenario:** LLM endpoint returns 500. The `openai` SDK raises `InternalServerError`. The caller (e.g., extraction pipeline) catches `json.JSONDecodeError` but not HTTP errors, so the exception propagates up to the `process_document` outer catch. The stack trace shows an openai SDK error but doesn't indicate which model tier or endpoint was involved.
**Recommendation:** Wrap the API call in try/except that catches `openai.APIError` and its subclasses, logs the tier, model name, and endpoint, then re-raises or returns a sentinel. This makes debugging LLM failures significantly easier.

### [DS-11] Severity: Warning
**File(s):** `packages/api/src/services/application.py:167-197`
**Finding:** `transition_stage` reads the application, validates the transition, updates the stage, and commits. But between the read and the write, another request could have already transitioned the application to a different stage. There is no row-level lock (`FOR UPDATE`) to prevent this race.
**Failure Scenario:** LO calls `lo_submit_to_underwriting` which does APPLICATION -> PROCESSING -> UNDERWRITING in sequence. Between the first and second transition, another user PATCHes the application stage. The second `transition_stage` call reads a stage that has changed since validation, potentially allowing an invalid transition.
**Recommendation:** Use `with_for_update()` in `get_application` when called from `transition_stage` to lock the row during the read-validate-write cycle.

### [DS-12] Severity: Warning
**File(s):** `packages/api/src/routes/_chat_handler.py:252-253`
**Finding:** The outer `except Exception` that catches WebSocket disconnections logs at `DEBUG` level with the message "Client disconnected from chat." This catches ALL exceptions -- not just WebSocket disconnections. If the `while True` loop exits due to an unexpected error (e.g., a bug in JSON parsing, a KeyError), it is silently swallowed at DEBUG level.
**Failure Scenario:** A code bug causes a `TypeError` or `AttributeError` inside the streaming loop but outside the inner try/except. The outer except catches it, logs "Client disconnected from chat" at DEBUG level, and the connection closes. The actual error is lost -- no stack trace, no ERROR-level log. The user sees the connection drop with no explanation.
**Recommendation:** Catch `WebSocketDisconnect` explicitly and log at DEBUG. For all other exceptions in the outer handler, log at ERROR with `exc_info=True`.

### [DS-13] Severity: Warning
**File(s):** `packages/api/src/routes/chat.py:37`
**Finding:** `conversation_service.checkpointer` is accessed unconditionally when `use_checkpointer` is True, but `conversation_service.checkpointer` raises `RuntimeError` if not initialized. The `is_initialized` check on line 36 is correct, but if the service becomes uninitialized between the check and the access (e.g., the connection pool closes), the `RuntimeError` from `checkpointer` is not caught, and the WebSocket endpoint crashes without sending an error message to the client.
**Failure Scenario:** The checkpointer's underlying psycopg connection pool fails health checks and auto-closes between the `is_initialized` check and the `checkpointer` property access. The RuntimeError propagates, and the WebSocket is closed without any error message to the client.
**Recommendation:** Wrap the `checkpointer` access in try/except and fall back to `checkpointer=None` (ephemeral mode) on failure, with a warning log. This pattern is already used in borrower_chat.py and other chat endpoints -- the same race exists in all of them (lines 37 in each).

### [DS-14] Severity: Warning
**File(s):** `packages/api/src/services/compliance/knowledge_base/search.py:54-108`
**Finding:** `search_kb` catches embedding failures and returns an empty list, but does not log what the query was. When debugging "why did the KB search return nothing?", the only log message is "Failed to get query embedding, returning empty results" with no indication of what was being searched for.
**Failure Scenario:** Embedding model endpoint is intermittently failing. Multiple KB searches return empty results. The logs show "Failed to get query embedding" repeated, but no indication of which queries failed, making it impossible to determine if the issue is with specific queries or a blanket failure.
**Recommendation:** Include the query text (or a truncated version) in the warning log: `logger.warning("Failed to get query embedding for query='%.100s', returning empty results", query)`.

### [DS-15] Severity: Warning
**File(s):** `packages/api/src/agents/decision_tools.py:50-81`
**Finding:** The `_compliance_gate` function checks for a compliance_check audit event and looks for `event_data.get("status") == "FAIL"`. But the compliance_check tool in `compliance_check_tool.py:177-183` stores the status under `event_data["overall_status"]`, not `event_data["status"]`. The gate is checking a key that is never set, meaning it will never detect a FAIL status. The compliance gate is effectively a no-op for blocking approvals when compliance fails.
**Failure Scenario:** An underwriter runs a compliance check that FAILs (e.g., DTI exceeds 50%). The audit event is written with `{"overall_status": "FAIL", "can_proceed": false}`. The underwriter then calls `uw_render_decision` with `decision="approve"`. The `_compliance_gate` queries the audit event, checks `event_data.get("status")` which is None (the key is `overall_status`), does not match "FAIL", and returns None (gate passes). The approval proceeds despite the failed compliance check.
**Recommendation:** Change `comp_event.event_data.get("status")` to `comp_event.event_data.get("overall_status")` in `_compliance_gate`. Also check `comp_event.event_data.get("can_proceed") is False` as a secondary signal.

### [DS-16] Severity: Warning
**File(s):** `packages/api/src/services/document.py:186-188`
**Finding:** `upload_document` returns `None` when the application is not found, but its return type annotation says `-> Document`. This is a type lie -- callers that rely on the type annotation will not expect None. The route layer (documents.py:98) does check for None, but this mismatch could cause bugs in future callers.
**Failure Scenario:** A new caller of `upload_document` trusts the `-> Document` return type, does not check for None, and crashes with `AttributeError: 'NoneType' object has no attribute 'id'` when the application is not found.
**Recommendation:** Change the return type to `-> Document | None` to match the actual behavior.

### [DS-17] Severity: Warning
**File(s):** `packages/api/src/routes/_chat_handler.py:236-238`
**Finding:** The `messages_fallback.append(AIMessage(content=full_response))` line is inside the `for event in graph.astream_events` loop, at the same indentation level as the loop body. This means it executes after every event, not after the full response is assembled. The `full_response` string grows as events arrive, but the append is inside the streaming loop, adding partial responses to the fallback history.
**Failure Scenario:** Without checkpointer, the `messages_fallback` list accumulates the AI response after the very first streaming event that sets `full_response`. Subsequent events append additional copies of the growing response. The conversation history becomes polluted with partial responses, causing the LLM to see garbled context on subsequent turns.
**Recommendation:** Move the `messages_fallback.append` and `ws.send_json({"type": "done"})` lines OUTSIDE the `async for event` loop (dedent them one level). They should execute after the streaming loop completes, not inside it.

### [DS-18] Severity: Warning
**File(s):** `packages/api/src/main.py:46-48`
**Finding:** The lifespan startup calls `init_storage_service(settings)` which creates a boto3 client and calls `_ensure_bucket`. If MinIO is not running, the constructor raises (from the boto3 `head_bucket`/`create_bucket` call), and the entire FastAPI application fails to start with no graceful degradation. The conversation service (line 46) handles initialization failure gracefully (falls back to ephemeral mode), but storage does not.
**Failure Scenario:** Developer starts the API before starting MinIO. The app crashes immediately with a connection error in `_ensure_bucket`. The developer sees a boto3 error and has to figure out that MinIO needs to be running.
**Recommendation:** Wrap `init_storage_service` in try/except, log a clear error message ("MinIO/S3 unavailable -- document upload will be disabled"), and allow the app to start in a degraded state. Document upload endpoints should check if the storage service is initialized before proceeding.

### [DS-19] Severity: Warning
**File(s):** `packages/api/src/services/audit.py:58-83`
**Finding:** If the `pg_advisory_xact_lock` call itself fails (e.g., DB connection dropped), or if the subsequent query for `prev_event` fails, the exception propagates to the caller. Since `write_audit_event` is called inside many service functions (condition operations, decisions, stage transitions), a transient DB error during audit writing will crash the entire business operation, even though the primary operation may have already succeeded.
**Failure Scenario:** During `render_decision`, the Decision record is added to the session, then `write_audit_event` is called. If the advisory lock acquisition fails (e.g., connection timeout), the entire transaction rolls back -- including the Decision record and the stage transition. The user sees a generic error, and the decision is lost.
**Recommendation:** For business-critical operations (decisions, stage transitions), consider writing the audit event as a secondary step: commit the primary operation first, then write the audit event in a separate try/except block. This prevents audit infrastructure failures from blocking business operations. The audit gap can be detected and repaired by the hash chain verification.

### [DS-20] Severity: Warning
**File(s):** `packages/api/src/agents/loan_officer_tools.py:355-430`
**Finding:** `lo_submit_to_underwriting` performs a two-step stage transition (APPLICATION -> PROCESSING -> UNDERWRITING) without any atomicity guarantee. If the first transition succeeds but the second fails (e.g., DB error, validation error), the application is left in PROCESSING stage with no mechanism to retry or roll back.
**Failure Scenario:** First `transition_stage(PROCESSING)` succeeds and commits. Second `transition_stage(UNDERWRITING)` fails (DB connection lost). The application is now stuck in PROCESSING. The LO cannot retry submission because the readiness check will fail (wrong stage). The LO would need to manually understand the state and figure out recovery.
**Recommendation:** Perform both transitions in a single database session/transaction. Use the session from `SessionLocal()` directly rather than relying on `transition_stage` (which commits internally). Alternatively, make the tool idempotent: if the application is already in PROCESSING, skip step 1 and proceed to step 2.

### [DS-21] Severity: Warning
**File(s):** `packages/api/src/middleware/auth.py:63-64`
**Finding:** In `authenticate_websocket` (`_chat_handler.py:63-64`), the `except Exception` for `_resolve_role` catches ALL exceptions, including potential `HTTPException` from `_resolve_role` (line 121-124 of auth.py). But `HTTPException` in a WebSocket context does not translate to an HTTP response -- it just becomes a generic exception. The error message sent to the WebSocket ("No recognized role") is correct, but the original exception (which may contain useful debug info) is swallowed.
**Failure Scenario:** `_resolve_role` raises `HTTPException(403, "No recognized role assigned")`. The `except Exception` catches it, closes the WebSocket with reason "No recognized role", but the specific detail from the HTTPException is lost in the log (no `exc_info=True`).
**Recommendation:** Add `logger.warning("WebSocket role resolution failed", exc_info=True)` before closing the WebSocket, or catch `HTTPException` specifically and extract its detail.

### [DS-22] Severity: Suggestion
**File(s):** `packages/api/src/services/extraction.py:207-215`, `packages/api/src/services/extraction.py:239-244`
**Finding:** Both `_extract_via_llm` and `_extract_image_via_llm` catch `json.JSONDecodeError` and return None, but they do not catch other exceptions from `get_completion` (e.g., HTTP errors, timeouts, rate limits from the LLM provider). These would propagate to `process_document`'s outer except, which sets `PROCESSING_FAILED` -- the right outcome -- but the error log says "Extraction failed for document X" without distinguishing "LLM returned garbage JSON" from "LLM endpoint is down."
**Failure Scenario:** LLM endpoint returns 429 (rate limited). The `openai` SDK raises `RateLimitError`. The outer except catches it and logs "Extraction failed for document X". The operator sees a stream of extraction failures but can't quickly tell that the root cause is rate limiting versus bad document content.
**Recommendation:** Catch `Exception` broadly in both methods, log the specific exception type and message, then return None. This keeps the extraction pipeline behavior unchanged but improves diagnostic logging.

### [DS-23] Severity: Suggestion
**File(s):** `packages/api/src/agents/borrower_tools.py:611-677`, `packages/api/src/agents/underwriter_tools.py:48-125`
**Finding:** All agent tool functions use `async with SessionLocal() as session:` and perform DB operations, but none of them have try/except for database errors. If the DB is temporarily unavailable during a tool call, the exception propagates through LangGraph's tool node and is handled by the generic "Agent invocation failed" catch in `_chat_handler.py`. The error message to the user is generic ("temporarily unavailable") rather than tool-specific ("I couldn't access application data right now, please try again").
**Failure Scenario:** DB connection pool exhausted during a `uw_risk_assessment` tool call. The tool raises `OperationalError`. LangGraph catches it and the user sees "Our chat assistant is temporarily unavailable" -- a session-level error for what was a single tool failure. The agent could have recovered by informing the user and trying a different tool.
**Recommendation:** Add a decorator or wrapper that catches `SQLAlchemy` operational errors in tool functions and returns a user-friendly string like "I'm having trouble accessing that data right now. Please try again in a moment." This allows the LLM to continue the conversation rather than killing the entire session.

### [DS-24] Severity: Suggestion
**File(s):** `packages/api/src/services/compliance/hmda.py:137-206`
**Finding:** `route_extraction_demographics` creates its own `ComplianceSessionLocal` and catches all exceptions, rolling back on failure. However, the rollback call on line 205 is inside the `except` block but the session context manager (`async with ComplianceSessionLocal()`) should already handle rollback on exception exit. The explicit `rollback()` is redundant but not harmful. The real issue is that the function silently swallows all failures -- if HMDA routing consistently fails (e.g., the compliance schema is missing), there is no alert mechanism beyond log lines.
**Failure Scenario:** The compliance schema was not created during migration. Every document extraction that detects demographic data fails to route it, logging "Failed to route HMDA data for document X" each time. The system appears to work but HMDA data is silently lost for all documents.
**Recommendation:** Consider tracking consecutive HMDA routing failures and raising a system-level alert (e.g., a health check degradation flag) after N consecutive failures. This prevents silent data loss in a compliance-critical path.

### [DS-25] Severity: Suggestion
**File(s):** `packages/api/src/services/application.py:112-155`
**Finding:** `create_application` commits the transaction on line 153, then calls `get_application` to re-query with eager loading. If the commit succeeds but the re-query fails (e.g., connection pool exhausted on the second query), the application was created but the caller gets an exception. The route layer will return a 500, but the application exists in the DB. The borrower would need to know to try again, and the next call would find the existing application.
**Failure Scenario:** Commit succeeds, re-query fails. The borrower sees a 500 error and assumes the application was not created. They retry, and `start_application` finds the existing active application and returns it. No data loss, but a confusing UX.
**Recommendation:** Accept this as a minor edge case for MVP, but consider returning the application ID from the commit result rather than re-querying, and letting the response schema handle the serialization without eager-loaded relationships if needed.

### [DS-26] Severity: Suggestion
**File(s):** `packages/api/src/routes/documents.py:106-111`
**Finding:** The background extraction task is fire-and-forget. While the task reference is retained in `_extraction_tasks` to prevent GC, there is no mechanism to check if extraction tasks are failing systematically. If the extraction service is broken (e.g., LLM endpoint misconfigured), every document upload triggers a failing background task, and no one is alerted.
**Failure Scenario:** LLM base URL is wrong in config. Every extraction task fails with a connection error. Documents pile up in `PROCESSING` status. The borrower and LO see documents stuck in "Processing..." indefinitely with no error signal.
**Recommendation:** Add a health check that reports the extraction task failure rate (e.g., count of documents in `PROCESSING` status for more than N minutes). Alternatively, add a `done_callback` to the task that logs at ERROR level when the task completes with an exception.

### [DS-27] Severity: Suggestion
**File(s):** `packages/api/src/services/condition.py:89-143`
**Finding:** `respond_to_condition` silently accepts responses to conditions in any non-terminal status. If a condition is in `UNDER_REVIEW`, the borrower can still submit a response text, overwriting the previous response. The status remains `UNDER_REVIEW` (the status change only triggers for `OPEN` conditions, line 118). This means the underwriter's in-progress review may be based on stale data.
**Failure Scenario:** Underwriter starts reviewing condition #5 (status: `UNDER_REVIEW`). Borrower submits a new response via chat, overwriting `response_text`. The underwriter finishes their review based on the old response text, but the audit trail shows a newer response. The review outcome is inconsistent with the latest borrower response.
**Recommendation:** Reject responses to conditions that are not in `OPEN` status. Return an error dict explaining that the condition is currently under review and cannot be modified. Alternatively, if overwriting is intended, transition the condition back to `RESPONDED` and add an audit event noting the mid-review update.

### [DS-28] Severity: Suggestion
**File(s):** `packages/api/src/agents/base.py:139-154`
**Finding:** The `input_shield` node calls `checker.check_input(last_msg.content)` but does not handle the case where `last_msg.content` is None or empty. If a malformed message reaches the graph with `content=None`, `check_input(None)` passes None into the Llama Guard prompt template, which substitutes "None" as a string. Llama Guard then evaluates the string "None" (likely safe), and the empty/null message proceeds to the LLM.
**Failure Scenario:** Client sends `{"type": "message", "content": ""}` -- empty string. The chat handler accepts it (line 143 checks `data.get("content")` which is falsy for empty string, so this is actually caught). But if a direct graph invocation passes `HumanMessage(content=None)`, the shield would evaluate "None" as safe text.
**Recommendation:** Add a guard in `input_shield` to return early (or block) if `last_msg.content` is None or empty. This is defense-in-depth since the chat handler already filters empty messages.

### [DS-29] Severity: Suggestion
**File(s):** `packages/api/src/services/intake.py:226-230`
**Finding:** The `converter` functions for intake fields (`_decimal`, `_int`, `_date`, `_loan_type`, `_employment_status`) have no error handling. If `validate_field` passes but the converter raises (e.g., `Decimal("not-a-number")`, `int("abc")`), the exception propagates from `update_application_fields` to the tool, and the tool returns the raw exception as a string. However, `validate_field` is supposed to catch these -- the risk is that a mismatch between validation regex and converter logic allows an invalid value through.
**Failure Scenario:** `validate_field` for `credit_score` accepts "750.5" (passes numeric regex) but `_int("750.5")` raises `ValueError`. The tool crashes rather than returning a user-friendly validation error.
**Recommendation:** Wrap the `converter(normalized)` call on line 229 in try/except ValueError, and add the field to the errors dict if conversion fails. This provides defense-in-depth against validation/conversion mismatches.

### [DS-30] Severity: Suggestion
**File(s):** `packages/api/src/services/audit.py:86-118`
**Finding:** `verify_audit_chain` loads ALL audit events into memory at once (`list(result.scalars().all())`). For a production system with thousands or millions of audit events, this will exhaust memory.
**Failure Scenario:** After months of operation with many concurrent users, the audit_events table has 500K rows. Calling `verify_audit_chain` (e.g., from the admin endpoint) loads all 500K rows into Python memory, consuming gigabytes of RAM and potentially crashing the process.
**Recommendation:** Implement a streaming/batched verification that processes events in chunks (e.g., 1000 at a time), maintaining the running hash across batches. For MVP, add a `LIMIT` parameter to check only the most recent N events, with a warning that full verification may be memory-intensive.
