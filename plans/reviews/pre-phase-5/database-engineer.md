# Database Review -- Pre-Phase 5

**Reviewer:** database-engineer
**Date:** 2026-02-27
**Scope:** Models, migrations, query patterns, data integrity, session management

---

## Findings

### [DB-01] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/condition.py:238-246`
**Finding:** N+1 query pattern in `check_condition_documents`. The function queries documents linked to a condition, then loops over each document and issues a separate `SELECT` for `DocumentExtraction` rows inside the loop body. For an application with 5 conditions and 3 documents each, this produces 15 extra round trips.
**Recommendation:** Replace the per-document extraction query with a single batch query outside the loop:
```python
doc_ids = [doc.id for doc in documents]
ext_stmt = (
    select(DocumentExtraction)
    .where(DocumentExtraction.document_id.in_(doc_ids))
    .order_by(DocumentExtraction.document_id, DocumentExtraction.field_name)
)
ext_result = await session.execute(ext_stmt)
all_extractions = ext_result.scalars().all()
ext_by_doc = {}
for e in all_extractions:
    ext_by_doc.setdefault(e.document_id, []).append(e)
```
Then reference `ext_by_doc.get(doc.id, [])` in the loop. Alternatively, use `selectinload(Document.extractions)` on the document query.

---

### [DB-02] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/audit.py:86-118`
**Finding:** `verify_audit_chain` loads the entire `audit_events` table into memory (`list(result.scalars().all())`). After Phase 4 there are hundreds of audit events; by production this will be tens of thousands. This is an unbounded memory allocation with no pagination.
**Recommendation:** Stream the verification using `result.scalars()` as an iterator and keep only the previous event in memory:
```python
prev_event = None
count = 0
async for event in result.scalars():
    count += 1
    if prev_event is None:
        if event.prev_hash != "genesis":
            return {"status": "TAMPERED", "first_break_id": event.id, "events_checked": count}
    else:
        expected = _compute_hash(prev_event.id, str(prev_event.timestamp), prev_event.event_data)
        if event.prev_hash != expected:
            return {"status": "TAMPERED", "first_break_id": event.id, "events_checked": count}
    prev_event = event
return {"status": "OK", "events_checked": count}
```
Use `execution_options(yield_per=500)` on the statement to enable server-side cursor batching.

---

### [DB-03] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/status.py:134`
**Finding:** Inconsistent enum value extraction in `notin_` filter. This line passes raw enum objects:
```python
Condition.status.notin_([s for s in _RESOLVED_CONDITION_STATUSES])
```
Every other service passes `.value` strings:
```python
Condition.status.notin_([s.value for s in _RESOLVED_STATUSES])
```
Because `ConditionStatus` inherits from `str`, SQLAlchemy resolves both forms to the same SQL. However, the inconsistency invites bugs if a future refactor changes the enum base class or if someone copies this pattern for a non-str enum.
**Recommendation:** Change line 134 of `status.py` to use `.value` consistently:
```python
Condition.status.notin_([s.value for s in _RESOLVED_CONDITION_STATUSES]),
```

---

### [DB-04] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:323-340` (AuditEvent)
**Finding:** `AuditEvent.application_id` and `AuditEvent.decision_id` have no foreign key constraints. While the audit table is append-only and intentionally avoids `ON DELETE CASCADE` (to preserve the trail even if an application is deleted), the lack of any FK means orphan references are invisible. There is also no index on `decision_id`, though it is queried in `_get_ai_recommendation` via `event_data->>'tool'` (not directly by `decision_id`).
**Recommendation:** This is acceptable for an MVP audit table where immutability is the priority. For Phase 5 or pre-production, consider adding a non-enforced comment or a partial index on `(application_id, event_type)` to accelerate the `_get_ai_recommendation` query which filters by both `application_id` and `event_type='tool_call'`.

---

### [DB-05] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:232-259` (Decision)
**Finding:** `Decision.denial_reasons` is stored as `Text` containing JSON-serialized data. The service layer (`decision.py:283`) calls `json.dumps(denial_reasons)` on write and `json.loads(d.denial_reasons)` on read. This loses the benefit of PostgreSQL JSONB indexing and GIN operators, and forces application-layer parsing. The `audit_events.event_data` column was already migrated from `Text` to `JSON` (migration `c4d5e6f7a8b9`), so there is precedent.
**Recommendation:** Change `denial_reasons` column type from `Text` to `JSON` (JSONB) in a future migration. This eliminates the manual `json.dumps`/`json.loads` round-trip and enables queries like `denial_reasons ? 'credit_history'` if needed for reporting.

---

### [DB-06] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:253` (Decision.contributing_factors)
**Finding:** `contributing_factors` is a `Text` column with no structure defined. The decision service sets it from a string parameter, but it is unclear whether this should be free-text, a JSON array, or a delimited list. This same ambiguity already caused issues with `Document.quality_flags` (which required a `_parse_quality_flags` helper in `condition.py` to handle both JSON arrays and CSV strings).
**Recommendation:** Define `contributing_factors` as `JSON` (JSONB) and standardize on a list-of-strings format, consistent with `denial_reasons`. Apply the same recommendation to both columns together.

---

### [DB-07] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:176-194` (RateLock)
**Finding:** The `RateLock` model has no `updated_at` column. Every other mutable domain model (Application, Borrower, ApplicationFinancials, Condition, Document, HmdaDemographic) includes `updated_at` with `onupdate=func.now()`. When a rate lock is deactivated (`is_active = False`), there is no timestamp recording when that change happened.
**Recommendation:** Add `updated_at` to `RateLock` with `server_default=func.now(), onupdate=func.now()` in a future migration.

---

### [DB-08] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:302-320` (DocumentExtraction)
**Finding:** `DocumentExtraction.confidence` uses `Float` type. Financial precision matters for confidence scores used to determine extraction quality (e.g., `freshness.py` threshold checks). While confidence is not a financial amount, the codebase has already migrated other `Float` columns to `Numeric` (migration `a1b2c3d4e5f7`) for consistency. The `Float` here is acceptable for MVP but inconsistent with the established pattern.
**Recommendation:** Low priority. If a future migration touches this table, convert `confidence` to `Numeric(3, 2)` for consistency.

---

### [DB-09] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:409-437` (HmdaDemographic)
**Finding:** The `HmdaDemographic` model has no foreign key constraints on `application_id` or `borrower_id`, by design (the HMDA schema is intentionally isolated from the public schema to enforce ECOA compliance). However, there is no `CHECK` constraint or partial index enforcing that `tier` on `KBDocument` is in the set `{1, 2, 3}`.
**Recommendation:** Add a check constraint on `kb_documents.tier`:
```sql
ALTER TABLE kb_documents ADD CONSTRAINT ck_kb_documents_tier CHECK (tier IN (1, 2, 3));
```
This prevents invalid tier values from being inserted without requiring application-layer validation.

---

### [DB-10] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:165-166` (ApplicationFinancials.dti_ratio)
**Finding:** `dti_ratio` is `Numeric(5, 4)` which allows values up to `9.9999` (999.99%). A DTI ratio above 1.0 (100%) is already nonsensical in mortgage lending. There is no `CHECK` constraint to prevent impossible values.
**Recommendation:** Add a check constraint:
```sql
ALTER TABLE application_financials ADD CONSTRAINT ck_dti_ratio_range
    CHECK (dti_ratio IS NULL OR (dti_ratio >= 0 AND dti_ratio <= 1));
```
Similarly for `credit_score`, a `CHECK (credit_score IS NULL OR (credit_score >= 300 AND credit_score <= 850))` would catch data entry errors.

---

### [DB-11] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/decision.py:37-53` (`_get_ai_recommendation`)
**Finding:** The function queries audit events by `application_id` and `event_type='tool_call'`, then iterates through up to 20 results in Python to find the one where `event_data->>'tool' == 'uw_preliminary_recommendation'`. This could be done entirely in SQL using JSONB operators:
```python
stmt = (
    select(AuditEvent.event_data)
    .where(
        AuditEvent.application_id == application_id,
        AuditEvent.event_type == "tool_call",
        AuditEvent.event_data["tool"].astext == "uw_preliminary_recommendation",
    )
    .order_by(AuditEvent.timestamp.desc())
    .limit(1)
)
```
This pushes the filtering to PostgreSQL and avoids transferring unneeded rows.
**Recommendation:** Refactor to use JSONB operators in the query. This also benefits from a future `(application_id, event_type)` composite index on `audit_events`.

---

### [DB-12] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/_chat_handler.py:119-132`
**Finding:** The `_audit` helper inside `run_agent_stream` creates a new database session (via `get_db()` generator) for every single audit event write during WebSocket streaming. Each tool invocation, safety block, and message triggers a separate session creation, advisory lock acquisition, commit, and session close. In a typical chat turn with 2-3 tool calls, this is 3-4 session lifecycles.
**Recommendation:** For MVP this is acceptable since chat audit events are infrequent relative to DB capacity. For Phase 5 or production, consider batching audit events per chat turn (accumulate events in a list, then write them all in a single session after the streaming loop completes for that turn).

---

### [DB-13] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/alembic/versions/f7a8b9c0d1e2_add_compliance_kb_tables.py:86-91`
**Finding:** The downgrade function for the compliance KB migration drops the HNSW index and tables but does not drop the `vector` extension that the upgrade creates with `CREATE EXTENSION IF NOT EXISTS vector`. This is intentional (extensions are shared across the database and other things may depend on them), but it means the downgrade is not fully reversible to a pre-pgvector state.
**Recommendation:** Acceptable as-is. Document in a comment that the extension is intentionally retained on downgrade.

---

### [DB-14] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/alembic/versions/a1b2c3d4e5f6_add_hmda_schema_and_roles.py:86-89`
**Finding:** The downgrade function for the HMDA schema migration drops the schema and table but leaves role grants in place (commented as "Role grants are left in place"). This is correct behavior (roles are cluster-level objects, not database-scoped), but the downgrade for `c3d4e5f6a7b8` (restrict audit access) does restore grants. The inconsistency in downgrade completeness is minor but could cause confusion.
**Recommendation:** Acceptable. The comment documents the decision. No action needed.

---

### [DB-15] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:68-114` (Application), `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/enums.py:30-48`
**Finding:** Application stage transitions are enforced only in the service layer (`application.py:transition_stage`), not at the database level. The `valid_transitions()` method on `ApplicationStage` defines the allowed transitions, but there is no database trigger or constraint preventing direct SQL updates that violate the state machine (e.g., jumping from `INQUIRY` directly to `CLOSED`). The audit trigger prevents mutation of `audit_events`, demonstrating the pattern is feasible.
**Recommendation:** For MVP, service-layer enforcement is sufficient since all mutations go through the API. For pre-production, consider a `BEFORE UPDATE` trigger on `applications` that validates stage transitions against the allowed map, similar to the existing `audit_events_prevent_mutation` trigger pattern.

---

### [DB-16] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/application.py:152-155`
**Finding:** In `create_application`, the function calls `session.commit()` and then immediately calls `get_application()` to re-query the newly created application with eager loading. The commit expires the ORM objects, requiring the re-query. However, if the commit succeeds but the re-query fails (e.g., a transient error), the application is created but the response is lost. The caller would not know the application ID.
**Recommendation:** Capture `application.id` before commit (already done on line 152) and return a minimal response on re-query failure rather than propagating the exception. Alternatively, use `session.flush()` + deferred commit so the eager-loaded re-query runs in the same transaction.

---

### [DB-17] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/completeness.py:222-226`
**Finding:** The `check_completeness` function accesses `ab.borrower` inside a loop over `app.application_borrowers`. The `get_application` call in `application.py` does use `selectinload(Application.application_borrowers).joinedload(ApplicationBorrower.borrower)`, so this is safe when called through that path. However, `check_completeness` depends on this eager loading having been performed by the upstream call. If `check_completeness` is ever called with an `Application` loaded without the eager load (e.g., from a different query path), it would trigger a `MissingGreenlet` error in async context.
**Recommendation:** Add a defensive `selectinload` to the application query within `check_completeness` itself (via `get_application` which already does this), or document the contract that the application must be loaded with borrower relationships. The current code path is safe, but the implicit dependency is fragile.

---

### [DB-18] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py` (general)
**Finding:** The `Condition` model has a composite index opportunity. The `get_conditions` query in `condition.py` filters by `application_id` and optionally by `status IN (OPEN, RESPONDED)`, then orders by `created_at`. The `get_condition_summary` query groups by `status` after filtering by `application_id`. A composite index on `(application_id, status, created_at)` would serve both query patterns as a covering index for the filter + sort.
**Recommendation:** Add a composite index:
```python
Index("ix_conditions_app_status_created", "application_id", "status", "created_at")
```
This would replace the existing single-column `ix_conditions_application_id` index.

---

### [DB-19] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/compliance/hmda.py:299-399` (snapshot_loan_data)
**Finding:** The `snapshot_loan_data` function opens a `SessionLocal()` context to read from the lending schema, closes it, then opens a `ComplianceSessionLocal()` context to write to the HMDA schema. Between these two sessions, there is no transaction isolation guarantee. If the application data changes between the read and the write (e.g., a concurrent financial update), the snapshot could contain stale or inconsistent data.
**Recommendation:** For MVP this is acceptable because snapshots are triggered during stage transitions which are serialized per-application. Document the assumption: "Snapshot must be called during a serialized stage transition to guarantee consistency." For production, consider using a single `SERIALIZABLE` transaction or adding a version/timestamp check.

---

### [DB-20] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/models.py:439-459` (HmdaLoanData)
**Finding:** `HmdaLoanData.snapshot_at` has `onupdate=func.now()` which causes the snapshot timestamp to change every time the row is updated. This is semantically wrong for a "snapshot" timestamp -- the timestamp should record when the snapshot was first taken. Subsequent updates (e.g., correcting a field) should update `updated_at`, not `snapshot_at`. However, `HmdaLoanData` has no `updated_at` column.
**Recommendation:** Remove `onupdate=func.now()` from `snapshot_at` and add a separate `updated_at` column. The `snapshot_at` should be immutable after initial insert. This requires a migration.

---

### [DB-21] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/database.py:86-101` (get_db, get_compliance_db)
**Finding:** Both `get_db()` and `get_compliance_db()` session generators do not call `await session.commit()` before closing. This means services must explicitly commit or the changes are lost (rolled back on close). This is the correct pattern for services that manage their own commit boundaries, but it relies on every service remembering to commit. Several services (e.g., `condition.py`, `decision.py`, `disclosure.py`) do explicit `session.commit()`, which is correct. However, the session generator could provide a safety net with a rollback-only close pattern documented in a comment.
**Recommendation:** No code change needed -- the pattern is correct. Consider adding a docstring note:
```python
"""Dependency to get database session.

The caller is responsible for calling session.commit() to persist changes.
If the session is closed without commit, all changes are rolled back.
"""
```
