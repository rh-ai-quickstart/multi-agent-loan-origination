# Database Engineer Review -- Pre-UI

**Scope:** `packages/db/src/db/`, `packages/api/src/services/`, Alembic migrations in `packages/db/alembic/versions/`

---

## Critical

### DB-01: N+1 query pattern in `get_lo_performance` -- one DB roundtrip per LO

**File:** `packages/api/src/services/analytics.py:421-518`

`get_lo_performance` first queries the distinct set of LO IDs (one query), then enters a `for lo_id in lo_ids` loop that executes **6 separate queries per LO**: active count, closed count, initiated count, decided count, denied count, and `_lo_avg_turn_time` (which itself issues 1 query). For a pipeline with 20 LOs this is 121 database roundtrips per dashboard request.

**Suggested fix:** Consolidate into set-based queries using `GROUP BY Application.assigned_to` and a single JOIN to `decisions`. The per-LO counts (active, closed, initiated, decided, denied) can be computed in 2--3 queries total using conditional aggregation (`CASE WHEN ... THEN 1 END`). The turn-time calculation requires audit event correlation and can remain a separate query but should group across all LOs rather than looping.

---

### DB-02: `create_async_engine` called with no pool parameters -- uses asyncpg defaults

**File:** `packages/db/src/db/database.py:16-22`

Both `engine` and `compliance_engine` are created with no `pool_size`, `max_overflow`, `pool_timeout`, or `pool_pre_ping` arguments. asyncpg's default pool size is 5 with no overflow limit. Under concurrent load (multiple agents writing audit events, multiple UI sessions) the pool will saturate silently. There is also no `pool_pre_ping=True`, so stale connections from idle pods cause `InterfaceError` on the first request after inactivity.

**Suggested fix:**
```python
engine = create_async_engine(
    db_settings.DATABASE_URL,
    echo=db_settings.SQL_ECHO,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,
)
```
Expose `POOL_SIZE` and `MAX_OVERFLOW` in `DatabaseSettings` so they can be tuned per environment.

---

## Warning

### DB-03: Initial migration (`fe5adcef3769`) creates `applications` with `borrower_id` FK that is later dropped -- downgrade chain is broken

**File:** `packages/db/alembic/versions/fe5adcef3769_add_domain_models.py:39-53`
**File:** `packages/db/alembic/versions/f6a7b8c9d0e1_add_co_borrower_support.py:70-88`

The base migration (`fe5adcef3769`) creates `applications` with a `borrower_id` FK column referencing `borrowers.id` (line 49). Migration `f6a7b8c9d0e1` drops this column in its `upgrade()`. However, the `downgrade()` of `f6a7b8c9d0e1` re-adds `borrower_id` as nullable with `ondelete="CASCADE"`, which differs from the original `nullable=False` definition. Any existing application rows added after the co-borrower migration would violate the original FK constraint on downgrade. This makes the downgrade chain unreliable for a database with production data.

**Suggested fix:** The downgrade is necessarily lossy given the data model change (one-to-many replaced one-to-one). Document this explicitly in the migration file with a `# DATA LOSS WARNING` comment and add a check in the downgrade that raises if any application has multiple borrowers.

---

### DB-04: `add_borrower` commits twice -- audit event written after first commit risks partial audit trail

**File:** `packages/api/src/services/application.py:294-313`

`add_borrower` calls `await session.commit()` on line 300 after inserting the junction row, then calls `write_audit_event` and `await session.commit()` again on line 311. If the process crashes between the two commits, the co-borrower is added to the application but no audit event is recorded. Given the compliance requirements of this domain, unaudited state changes are a correctness risk.

The same pattern exists in `remove_borrower` (lines 368 and 378).

**Suggested fix:** Write the audit event before the first commit so both the junction row and the audit event are in the same transaction:

```python
junction = ApplicationBorrower(...)
session.add(junction)
await audit.write_audit_event(session, ...)
await session.commit()
```

---

### DB-05: `HmdaLoanData` model has no FK constraint referencing `applications.id` -- cross-schema referential integrity relies entirely on application code

**File:** `packages/db/src/db/models.py:448`
**File:** `packages/db/alembic/versions/e5f6a7b8c9d0_hmda_add_age_and_loan_data.py:32-58`

`HmdaLoanData.application_id` is declared `unique=True, index=True` but has no `ForeignKey` constraint. The comment in `b3c4d5e6f7a8` correctly notes that "hmda schema cannot reference public.borrowers", but `application_id` references `public.applications`, not `borrowers`. PostgreSQL cross-schema foreign keys work when both schemas are in the same database. The absence of this FK means orphaned HMDA loan data rows can accumulate if an application is deleted (no cascade, no error). Similarly, the `hmda.demographics` model omits FKs to `public.applications` and `public.borrowers` for the same stated reason.

**Suggested fix:** Add a FK from `hmda.loan_data.application_id` to `public.applications.id` with `ON DELETE CASCADE`. If the concern is privilege separation (compliance_app cannot reference public schema), use a database trigger on `applications` that cascades deletes to `hmda.loan_data` instead.

---

### DB-06: `upload_document` returns `None` (not `Document`) on missing application but signature declares `Document`

**File:** `packages/api/src/services/document.py:187`

```python
async def upload_document(...) -> Document:
    ...
    if application is None:
        return None  # <-- violates declared return type
```

The function is declared to return `Document` but silently returns `None` when the application is not found. Every call site that treats the result as `Document` without a None check risks an `AttributeError`. The return type should be `Document | None` and callers in the route layer must handle `None`.

---

### DB-07: `_compute_top_denial_reasons` fetches all denial rows to Python for aggregation -- no pushdown to database

**File:** `packages/api/src/services/analytics.py:305-362`

The function pulls every `Decision.denial_reasons` JSONB column value into Python and counts reason strings with a dict. As the number of denial decisions grows this will transfer unbounded data to the application layer. PostgreSQL can aggregate JSONB array elements directly using `jsonb_array_elements_text` and `GROUP BY`.

**Suggested fix:**
```sql
SELECT elem AS reason, COUNT(*) AS cnt
FROM decisions,
     jsonb_array_elements_text(denial_reasons) AS elem
WHERE decision_type = 'denied'
  AND created_at >= :cutoff
GROUP BY elem
ORDER BY cnt DESC
LIMIT 10
```
This pushes the work to the database and transfers only aggregated counts.

---

### DB-08: Missing index on `audit_events.timestamp` -- time-range queries do full table scans

**File:** `packages/db/src/db/models.py:331`
**File:** `packages/api/src/services/audit.py:240-249`

The `audit_events` table has indexes on `event_type`, `application_id`, and `session_id`, but no index on `timestamp`. Several queries filter by `timestamp >= cutoff` (e.g., `search_events`, `_compute_turn_times`, `_lo_avg_turn_time`). Without a timestamp index these are sequential scans. As the audit table grows (every tool call, every chat message) this becomes a meaningful bottleneck.

**Suggested fix:** Add a migration:
```python
op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
```

---

### DB-09: `DocumentExtraction` has no unique constraint on `(document_id, field_name)` -- re-extraction appends duplicates

**File:** `packages/db/src/db/models.py:304-322`

There is no unique constraint preventing multiple extraction rows for the same `(document_id, field_name)` pair. The extraction pipeline can run multiple times on a document (e.g., resubmission flow), producing stale duplicate extractions that co-exist with fresh ones. `check_condition_documents` then returns all extractions, and the agent receives conflicting values for the same field.

**Suggested fix:** Add a unique constraint and handle upsert in the extraction service:
```python
# In migration
op.create_unique_constraint(
    "uq_extraction_doc_field",
    "document_extractions",
    ["document_id", "field_name"],
)
```

---

### DB-10: `KBChunk.embedding` is nullable (`nullable=True`) -- HNSW index silently skips un-embedded chunks and the search WHERE clause filters them

**File:** `packages/db/src/db/models.py:402`
**File:** `packages/api/src/services/compliance/knowledge_base/search.py:65-73`

The model and migration both declare `embedding` as nullable. The search query adds `WHERE c.embedding IS NOT NULL` to exclude un-embedded chunks, but there is no constraint preventing ingestion from leaving chunks without embeddings. An ingestion failure mid-batch leaves partial chunks that are silently excluded from all searches. There is no monitoring or alerting path for this.

**Suggested fix:** Either:
1. Make `embedding NOT NULL` and fail ingestion atomically per document (preferred), or
2. Add a check constraint that fires a notification when un-embedded chunks exist after ingestion.

For MVP, changing the column to `NOT NULL` with a migration is the simpler path. The ingestion pipeline already batches embeddings before insert, so the only gap is failure mid-insert which should roll back the transaction anyway.

---

## Suggestion

### DB-11: Migration `fe5adcef3769` does not include the `AI assistance` comment required by project policy

**File:** `packages/db/alembic/versions/650767a5a0cd_add_condition_response_text_and_.py:1-2`

Migration `650767a5a0cd` (add condition response_text) is missing the `# This project was developed with assistance from AI tools.` comment at the top required by `.claude/rules/ai-compliance.md`. All other migrations have this comment. This is a minor policy consistency issue.

---

### DB-12: `get_lo_performance` uses string literal `"cleared"` instead of `ConditionStatus.CLEARED.value` for status comparison

**File:** `packages/api/src/services/analytics.py:499`

```python
Condition.status == "cleared",
```

All other condition queries in the codebase use `ConditionStatus.CLEARED` or `ConditionStatus.CLEARED.value`. This string literal bypasses the enum and will silently fail to match if the stored value ever changes case or the enum value changes.

**Suggested fix:**
```python
from db.enums import ConditionStatus
Condition.status == ConditionStatus.CLEARED,
```

---

### DB-13: `application.py:add_borrower` does not use `SELECT FOR UPDATE` -- race condition between duplicate check and insert

**File:** `packages/api/src/services/application.py:283-299`

The duplicate-check query (line 284-289) and the subsequent insert (line 293-298) are not atomic. Two concurrent requests to add the same borrower to the same application can both pass the duplicate check before either commits, resulting in a unique constraint violation error rather than a clean business error. The `uq_app_borrower` unique constraint (defined in the model) will catch it at the database level and raise an `IntegrityError`, but this surfaces as an unhandled 500 rather than a 409.

**Suggested fix:** Wrap in a try/except for `IntegrityError` and surface as `ValueError("Borrower already linked to this application")`, or add `FOR UPDATE` on the duplicate-check query.

---

### DB-14: `search_events` in `audit.py` has no index hint and no lower limit on `days` -- can scan the entire audit table

**File:** `packages/api/src/services/audit.py:231-249`

`search_events` accepts `days=None` (no time filter) and `limit=500`. With `days=None` the query scans the full audit table ordered by `timestamp DESC`. Combined with the missing `timestamp` index (DB-08), this is a full table scan. The default `limit=500` partially mitigates row transfer but the scan cost remains.

**Suggested fix:** Make `days` required (or set a sensible default like 30) and add the timestamp index from DB-08.
