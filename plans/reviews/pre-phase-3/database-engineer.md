# Database Engineer Review -- Pre-Phase 3

Reviewer: Database Engineer
Date: 2026-02-26
Scope: All database models, migrations, query patterns, and data integrity constraints

---

## DB-01: Application.financials relationship is uselist=False but schema supports per-borrower financials
**Severity:** Critical
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:91-93`
**Description:** The `Application.financials` relationship is declared with `uselist=False`, meaning SQLAlchemy expects a single `ApplicationFinancials` row per application. However, the schema was explicitly migrated (migration `d5e6f7a8b9c0`) to support per-borrower financials via a composite unique constraint `(application_id, borrower_id)`. With `uselist=False`, accessing `app.financials` will silently return only one arbitrarily-chosen financials row when multiple exist (one per borrower). The `intake.py` service uses `app.financials` (line 288, 397, 406) as if it's a single object, which will break or return incorrect data once co-borrower financials exist.
**Recommendation:** Change the relationship to `uselist=True` (i.e., `relationship("ApplicationFinancials", back_populates="application", cascade="all, delete-orphan")`). Update all call sites (`intake.py:get_remaining_fields`, `intake.py:get_application_progress`) to iterate the list or filter for the primary borrower's financials explicitly. If the intent is truly one-per-app, remove the `borrower_id` column and composite unique constraint.

---

## DB-02: N+1 query pattern in check_condition_documents
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/condition.py:263-271`
**Description:** Inside `check_condition_documents`, after fetching all documents linked to a condition (line 254-260), the code loops over each document and issues a separate query to fetch `DocumentExtraction` rows for each one (lines 265-271). With N documents, this produces N+1 queries. For conditions with many linked documents, this is a performance concern.
**Recommendation:** Use a single query with `selectinload(Document.extractions)` on the initial document query:
```python
doc_stmt = (
    select(Document)
    .options(selectinload(Document.extractions))
    .where(Document.condition_id == condition_id)
    .order_by(Document.created_at.desc())
)
```

---

## DB-03: verify_audit_chain loads entire audit_events table into memory
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/audit.py:97-99`
**Description:** `verify_audit_chain` executes `select(AuditEvent).order_by(AuditEvent.id.asc())` and calls `list(result.scalars().all())`, materializing every audit event row into Python memory. With a production-scale audit trail (thousands to millions of rows), this will exhaust memory and be extremely slow.
**Recommendation:** Use cursor-based iteration or batch processing. For example, fetch rows in batches of 1000 using `.yield_per(1000)` on the result, or paginate with `LIMIT/OFFSET`. The hash chain verification can be done incrementally by tracking the previous event's hash as you iterate.

---

## DB-04: AuditEvent.application_id has no foreign key constraint
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:320`
**Description:** `AuditEvent.application_id` is a plain `Integer` column with no `ForeignKey` reference to `applications.id`. This means the database cannot enforce referential integrity -- audit events can reference non-existent application IDs. The same applies to `AuditEvent.decision_id` (line 321).
**Recommendation:** This may be intentional (audit events should survive application deletion, and the append-only trigger prevents cascading changes). If so, document this design decision. If not, add `ForeignKey("applications.id", ondelete="SET NULL")` to both columns. The append-only constraint means CASCADE wouldn't fire anyway, but SET NULL would be safer if the trigger were ever removed.

---

## DB-05: HmdaDemographic has no foreign keys to public schema tables
**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:365-366`
**Description:** `HmdaDemographic.application_id` and `HmdaDemographic.borrower_id` are plain integers with no FK constraints. Migration `b3c4d5e6f7a8` comments "no FK -- hmda schema cannot reference public.borrowers", which is correct given the schema isolation (lending_app is revoked from hmda schema). However, this means orphaned HMDA records can accumulate if applications or borrowers are deleted from the public schema.
**Recommendation:** Document this as an accepted trade-off of the HMDA isolation architecture. Consider a periodic reconciliation job (Phase 3+) that flags hmda records whose application_id no longer exists in the public schema. The seed cleanup in `seeder.py` already handles this via `clear_hmda_demographics`, but application deletion outside of seed cleanup would leave orphans.

---

## DB-06: Missing index on AuditEvent.session_id
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:323`
**Description:** `AuditEvent.session_id` is queried directly in `get_events_by_session` (`audit.py:137`) with a `WHERE AuditEvent.session_id == session_id` filter. This column has no index, so this query performs a sequential scan on the audit_events table, which grows continuously as an append-only log.
**Recommendation:** Add `index=True` to the `session_id` column definition, or create an index via a migration: `CREATE INDEX ix_audit_events_session_id ON audit_events (session_id)`.

---

## DB-07: Condition.status enum comparison uses string values inconsistently
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/status.py:138`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/completeness.py:246`
**Description:** The `Condition.status` column uses `native_enum=False` (stored as VARCHAR). In `status.py:138`, the code compares against `_RESOLVED_CONDITION_STATUSES` which contains string values like `ConditionStatus.CLEARED.value` ("cleared"). However, `Condition.status.notin_()` is called with the raw strings. Meanwhile in `condition.py:61`, the code uses `Condition.status.in_([ConditionStatus.OPEN, ConditionStatus.RESPONDED])` -- passing enum objects. Similarly, `completeness.py:246` uses `Document.status.notin_([s.value for s in _EXCLUDED_STATUSES])` with `.value`. This inconsistency (sometimes enum objects, sometimes `.value` strings) works because `native_enum=False` with `str` enums stores the string value, but it makes the code fragile -- a future change to native enums would break the `.value` comparisons.
**Recommendation:** Standardize on passing enum objects everywhere (e.g., `ConditionStatus.CLEARED` not `ConditionStatus.CLEARED.value`). SQLAlchemy handles the conversion internally for non-native enums. This makes the code resilient to future changes.

---

## DB-08: Document upload creates S3 object then commits -- no rollback on S3 failure
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/document.py:166-173`
**Description:** In `upload_document`, after `session.flush()` assigns `doc.id`, the code uploads to S3 (line 168), then updates `doc.file_path` and commits (line 173). If the S3 upload succeeds but the subsequent `session.commit()` fails (e.g., DB connection drop), the S3 object becomes orphaned with no DB record pointing to it. Conversely, if S3 upload fails, the flushed Document row is part of the session and could end up committed by a later operation on the same session (depending on how the session is used upstream).
**Recommendation:** Wrap the S3 upload and DB commit in a try/except. On S3 failure, explicitly remove the flushed document from the session or rollback. On commit failure after successful S3 upload, log the orphaned S3 key for cleanup. Consider using savepoints (`session.begin_nested()`) so the document row can be rolled back independently on S3 failure.

---

## DB-09: Extraction pipeline creates its own SessionLocal -- transaction boundary unclear
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/extraction.py:60`
**Description:** `ExtractionService.process_document` creates its own `SessionLocal()` context (line 60). Inside the `except` block (lines 149-155), it tries to set `doc.status = PROCESSING_FAILED` and commit, but `doc` was loaded in the same session earlier. If the original error caused the session to be in a broken state (e.g., connection lost, transaction aborted), the recovery commit will also fail silently (caught by the inner except on line 154). The outer session is never explicitly rolled back before the recovery attempt.
**Recommendation:** Add `await session.rollback()` before the recovery attempt on line 151. This ensures the session is in a clean state before trying the status update. Alternatively, use a fresh session for the recovery update.

---

## DB-10: HMDA route_extraction_demographics writes AuditEvent directly instead of using write_audit_event
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/compliance/hmda.py:195-200`
**Description:** The `route_extraction_demographics` function creates `AuditEvent` objects directly and adds them to the compliance session (lines 195-200). This bypasses the `write_audit_event` function which maintains the hash chain (advisory lock + prev_hash computation). The same pattern appears in `collect_demographics` (lines 277-291). These audit events will have `prev_hash=NULL`, breaking the chain integrity for any events that should follow them.
**Recommendation:** Use `write_audit_event` (from `services.audit`) for all audit event creation. However, this requires the lending session (since `write_audit_event` uses advisory locks on the same DB). The architecture splits compliance and lending sessions, so this needs careful handling -- either pass both sessions to these functions, or accept that HMDA audit events are outside the hash chain and document this as a known limitation.

---

## DB-11: RateLock.locked_rate uses Float instead of Numeric for financial data
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:180`
**Description:** `RateLock.locked_rate` is `Float`, which maps to IEEE 754 double-precision floating point. Interest rates like 6.375% cannot be represented exactly in binary floating point, leading to rounding artifacts (e.g., 6.3750000000000001). The same issue applies to `ApplicationFinancials.dti_ratio` (line 161) and `HmdaLoanData.dti_ratio` (line 394) and `HmdaLoanData.interest_rate` (line 399).
**Recommendation:** Change `locked_rate` and `interest_rate` to `Numeric(5, 4)` (supports rates up to 99.9999%). Change `dti_ratio` to `Numeric(5, 4)` (supports ratios up to 99.9999%). Float is acceptable for `DocumentExtraction.confidence` since exact precision is not critical there.

---

## DB-12: Missing composite index on document_extractions for (document_id, field_name)
**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:293-296`
**Description:** `DocumentExtraction` has an index on `document_id` alone, but queries in `condition.py:266-268` filter by `document_id` and order by `field_name`. A composite index `(document_id, field_name)` would serve as a covering index for this query pattern, avoiding a sort step.
**Recommendation:** Add a composite index `(document_id, field_name)` if extraction queries by document are frequent. The single-column index on `document_id` is sufficient for most queries; this is a minor optimization.

---

## DB-13: quality_flags stored as JSON-serialized Text, parsed inconsistently
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:273`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/condition.py:279`
**Description:** `Document.quality_flags` is stored as `Text` containing JSON-serialized arrays (e.g., `'["unreadable"]'`). The extraction service writes it as `json.dumps(quality_flags)` (extraction.py:90,127), the completeness service reads it with `json.loads(doc.quality_flags)` (completeness.py:270), but `check_condition_documents` reads it with `doc.quality_flags.split(",")` (condition.py:279). The `.split(",")` call will incorrectly parse JSON arrays -- e.g., `'["wrong_period", "document_type_mismatch"]'` would split into `['["wrong_period"', ' "document_type_mismatch"]']` including brackets and quotes.
**Recommendation:** Either change the column type to `JSON` (or `JSONB`) for native JSON storage, or use `json.loads()` consistently everywhere quality_flags is read. The `.split(",")` in condition.py:279 is a bug that produces malformed flag strings.

---

## DB-14: Seed cleanup truncates audit_events but does not reset the hash chain genesis
**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/seed/seeder.py:82`
**Description:** `_clear_demo_data` uses `TRUNCATE TABLE audit_violations, audit_events CASCADE` to clear audit data. After truncation, the next `write_audit_event` call will find no previous event and set `prev_hash = "genesis"`, which is correct. However, the truncation bypasses the append-only trigger (TRUNCATE is not caught by BEFORE DELETE triggers), which means it silently violates the append-only guarantee. This is acceptable for seed cleanup but should be documented.
**Recommendation:** Add a comment documenting that TRUNCATE intentionally bypasses the append-only trigger for seed cleanup purposes, and that this is the only permitted path for clearing audit data.

---

## DB-15: Dual-session seeding is not atomic
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/seed/seeder.py:321-333`
**Description:** The seeder commits the lending session first (line 325), then the compliance session (line 327). If the compliance commit fails, the lending data exists but HMDA demographics are missing. The code logs this (lines 329-331) and suggests re-running with `--force`, but the manifest already recorded "seeded" status. A subsequent non-force run will see the manifest and skip seeding, leaving HMDA data permanently missing until someone manually intervenes.
**Recommendation:** The code already documents this limitation (lines 322-324). To improve: commit the compliance session first (lower-risk data), then the lending session (which writes the manifest). If the lending commit fails, the HMDA data is orphaned but harmless, and the manifest won't exist, so a retry will work. Alternatively, check for HMDA data completeness in `_check_manifest`.

---

## DB-16: Missing index on conditions table for status-based queries
**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:192-218`
**Description:** The `conditions` table has an index on `application_id` but not on `status`. The `status.py` service queries conditions filtered by `application_id` AND `status` (line 137-139), and `condition.py` filters by `application_id` AND `status IN (...)` (line 60-62). A composite index `(application_id, status)` would improve these queries.
**Recommendation:** Create index `(application_id, status)` for the conditions table. The existing `application_id` index handles the equality predicate, but adding `status` would allow index-only scans for the common "count open conditions for app X" query.

---

## DB-17: Borrower tools create standalone sessions that may conflict with request-scoped sessions
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:71`, lines 121, 175, 292, 320, 365, 426, 469, 501, 571, 627, 677
**Description:** Every tool function in `borrower_tools.py` creates its own `SessionLocal()` context manager for database access. These are independent sessions from the request-scoped session provided by `get_db()`. While this works correctly for read-only tools, tools that write and commit (`acknowledge_disclosure`, `start_application`, `update_application_data`, `get_application_summary`) create separate transactions. If the WebSocket handler that invokes these tools also has a session, there's no transaction coordination between them. Additionally, each tool opens and closes a connection, adding connection pool pressure during conversations with multiple tool calls.
**Recommendation:** Consider passing a session through the LangGraph state rather than creating one per tool invocation. This would allow multiple tools in a single agent turn to share a session and transaction boundary. For now, this works but is inefficient.

---

## DB-18: ApplicationBorrower junction table missing constraint to ensure exactly one primary borrower
**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:112-137`
**Description:** The `application_borrowers` table has `is_primary` boolean but no database-level constraint ensuring exactly one primary borrower per application. The application layer (e.g., `add_borrower` route in applications.py:349-354) allows setting `is_primary=True` on a new junction row without unsetting it on the existing primary. This can result in multiple primary borrowers for a single application, which would cause unpredictable behavior in `_get_borrower_for_app` (intake.py:149-159) and other services that assume a single primary borrower.
**Recommendation:** Add a partial unique index: `CREATE UNIQUE INDEX uq_app_one_primary ON application_borrowers (application_id) WHERE is_primary = true`. This enforces at most one primary borrower per application at the database level. The `add_borrower` endpoint should also check and swap primary status atomically.

---

## DB-19: Missing ON DELETE CASCADE on initial migration ForeignKeys
**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/alembic/versions/fe5adcef3769_add_domain_models.py:49`, lines 66, 83, 99, 113, 129, 143
**Description:** The initial migration (`fe5adcef3769`) creates foreign keys without `ondelete` behavior specified (e.g., `applications.borrower_id -> borrowers.id`, `application_financials.application_id -> applications.id`). The ORM model definitions have `ondelete="CASCADE"` specified on ForeignKey declarations, but the actual database constraints created by the initial migration use the default PostgreSQL behavior (`NO ACTION`). Later migrations (e.g., `f6a7b8c9d0e1` for co-borrower support) do specify `ondelete="CASCADE"`. This means tables created in the initial migration may have `NO ACTION` foreign keys that don't match the ORM model's declared `CASCADE` behavior.
**Recommendation:** Verify the actual on-delete behavior in the running database with `\d+ tablename` in psql. If they don't match the ORM declarations, create a migration to alter the FK constraints. For tables where later migrations dropped and recreated FKs (like `applications.borrower_id`), this may already be resolved.

---

## DB-20: timestamp migration uses string formatting for ALTER TABLE statements
**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/db/alembic/versions/b2c3d4e5f6a7_timestamps_with_timezone.py:52-56`
**Description:** The timestamp migration uses f-string formatting to build ALTER TABLE statements: `f'ALTER TABLE {table} ALTER COLUMN "{column}" TYPE TIMESTAMP WITH TIME ZONE ...'`. While the values come from a hardcoded list (not user input), this pattern is fragile -- a table or column name with special characters could produce invalid SQL. The double-quoting of column names is correctly applied, but table names are unquoted.
**Recommendation:** Quote table names as well: `f'ALTER TABLE "{table}" ALTER COLUMN "{column}" ...'`. This is a minor robustness improvement since all current table names are simple identifiers.
