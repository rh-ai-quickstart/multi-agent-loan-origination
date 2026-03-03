# Performance Engineer Review -- Pre-UI

**Scope:** `packages/api/src/`
**Reviewer:** Performance Engineer
**Date:** 2026-03-02

---

## Performance Analysis

### Baseline

No profiling data is available (no load tests have been run). This review identifies bottlenecks
through static analysis. Metrics below describe the structural worst-case for each finding.

---

## Critical

### PE-01: N+1 Queries in `get_lo_performance` -- Sequential Per-LO DB Round Trips

**File:** `packages/api/src/services/analytics.py:422-518`

**Description:**
`get_lo_performance` first fetches all distinct LO IDs (one query), then loops over each LO and
executes **six separate database queries per LO**: active count, closed count, initiated count,
decided count, denied count, and avg condition time, plus one more call to `_lo_avg_turn_time`
which itself issues a seventh query. With N loan officers, this endpoint makes `1 + 7N` queries.
At 10 LOs that is 71 round trips; at 50 LOs it is 351.

This is the hot path for the CEO dashboard, called on every LO performance page load and every
invocation of the `ceo_lo_performance` agent tool.

**Root cause:** Each metric was implemented as an independent scalar count rather than aggregated
via SQL GROUP BY in a single pass.

**Suggested fix:** Consolidate the six per-LO count queries into a single grouped aggregate query
using SQL `CASE WHEN` expressions (the same pattern already used in `_compute_denial_trend`).
The `_lo_avg_turn_time` audit event join can be folded in as a lateral subquery or computed via
a window function. The result set can then be constructed from one pass over the result rows
instead of one pass per LO.

```python
# Example sketch -- replace the per-LO loop with a single grouped query
stmt = (
    select(
        Application.assigned_to,
        func.count(case((Application.stage.in_(_ACTIVE_STAGES), Application.id))).label("active"),
        func.count(case((
            (Application.stage == ApplicationStage.CLOSED) &
            (Application.updated_at >= cutoff), Application.id
        ))).label("closed"),
        ...
    )
    .where(Application.assigned_to.isnot(None), *product_clause)
    .group_by(Application.assigned_to)
)
```

---

### PE-02: `_compute_turn_times` Runs Four Sequential Queries in a Loop

**File:** `packages/api/src/services/analytics.py:107-183`

**Description:**
`_compute_turn_times` iterates over `_TURN_TIME_TRANSITIONS` (4 pairs) and for each pair
executes one database query. These four queries are issued **sequentially** even though they are
fully independent and could be parallelized or merged.

This function is called on every pipeline summary page load and every `ceo_pipeline_summary` tool
invocation. On a large `audit_events` table the JSONB operator `event_data["to_stage"].as_string()`
used in all four queries performs a JSON extraction per row with no index support -- see PE-03.

**Suggested fix:** Either union all four pair queries into a single SQL `UNION ALL` so one round
trip returns all rows, or issue them with `asyncio.gather` to run concurrently. Combined with
PE-03 (adding an index), this reduces both round trips and per-query scan cost.

---

## Warning

### PE-03: Unindexed JSONB Lookups on `audit_events.event_data` in Hot Query Paths

**File:** `packages/api/src/services/analytics.py:136-151, 554-563`

**Description:**
Both `_compute_turn_times` and `_lo_avg_turn_time` filter on:
```python
AuditEvent.event_data["to_stage"].as_string() == to_stage.value
```
This is a JSONB field extraction used in a WHERE clause. Without a GIN index or a generated
column, PostgreSQL performs a sequential scan of all `audit_events` rows with
`event_type = 'stage_transition'` and extracts the JSON value for each row. As the audit table
grows (every tool call writes an event), these scans become progressively more expensive.

**Suggested fix:** Add a GIN index on `event_data` or a partial index using a generated column:
```sql
CREATE INDEX idx_audit_stage_transition
ON audit_events ((event_data->>'to_stage'))
WHERE event_type = 'stage_transition';
```
This requires a new Alembic migration. Alternatively, promote `to_stage` and `from_stage` to
dedicated nullable columns on `AuditEvent` for stage transition events, written at insert time.

---

### PE-04: PIIMaskingMiddleware Buffers Entire Response Body in Memory for Every CEO Request

**File:** `packages/api/src/middleware/pii.py:102-135`

**Description:**
`PIIMaskingMiddleware.dispatch` reads the **entire response body into a Python `bytes` buffer**
before processing it, even for large paginated list responses. For CEO role requests that return
full application lists or audit exports (up to 10,000 rows per `export_events`), this pattern:

1. Doubles memory usage for the response body (original streaming bytes + new masked bytes)
2. Prevents streaming -- the full response is buffered before the client receives any data
3. Runs a recursive Python-level JSON walk (`_mask_pii_recursive`) on every key of every object

The middleware runs on **all requests** including large analytics and audit endpoints, but only
applies masking when `pii_mask=True`. The check at line 108 short-circuits for non-CEO roles,
but the FastAPI/Starlette middleware stack still routes all responses through `dispatch`.

**Suggested fix:** For MVP scope, the existing approach is acceptable if response sizes stay small.
Document the current behavior and add a comment explaining that audit export (`/api/audit/export`)
should not be enabled for CEO role (or the export endpoint should strip PII at the service layer
rather than relying on middleware). If larger responses are anticipated, move PII masking to the
response model layer via a Pydantic serializer so no buffering is required.

---

### PE-05: `get_pipeline_summary` Issues Five Sequential Database Queries

**File:** `packages/api/src/services/analytics.py:40-104`

**Description:**
`get_pipeline_summary` makes five sequential awaited queries:
1. Stage distribution `GROUP BY` (line 57-58)
2. Initiated count scalar (line 64-66)
3. Closed count scalar (line 68-73)
4. Average close time scalar (line 78-85)
5. Delegates to `_compute_turn_times` which adds 4 more queries (PE-02)

Queries 1-4 could be combined into a single query using conditional aggregates or `FILTER`
clauses, eliminating 3 round trips. For example:

```sql
SELECT
    stage, COUNT(*) as cnt,
    COUNT(*) FILTER (WHERE created_at >= :cutoff) AS initiated,
    COUNT(*) FILTER (WHERE stage = 'closed' AND updated_at >= :cutoff) AS closed,
    AVG(...) FILTER (WHERE stage = 'closed' AND updated_at >= :cutoff) AS avg_days
FROM applications
GROUP BY stage
```

**Suggested fix:** Merge the four scalar queries into a single aggregate query. This is an easy
win -- the result set fits in one pass over the `applications` table.

---

### PE-06: `_compute_top_denial_reasons` Fetches All Denial Rows into Python for Aggregation

**File:** `packages/api/src/services/analytics.py:305-363`

**Description:**
The function fetches `Decision.denial_reasons` for every denial decision in the time window
into a Python list, then iterates in Python to count reason occurrences (lines 323-334). With a
large denial history this loads an unbounded number of rows into application memory.

The `denial_reasons` field is a JSONB array. PostgreSQL can unnest and count these values
entirely in SQL:

```sql
SELECT jsonb_array_elements_text(denial_reasons) AS reason, COUNT(*) AS cnt
FROM decisions
WHERE decision_type = 'denied' AND created_at >= :cutoff
GROUP BY reason
ORDER BY cnt DESC
LIMIT 10
```

**Suggested fix:** Replace the Python-side aggregation with a `jsonb_array_elements_text`
query that does the counting in the database. This eliminates the full table scan result set
being transferred to Python.

---

### PE-07: `agent_capable` Calls `bind_tools` on Every Agent Invocation

**File:** `packages/api/src/agents/base.py:202-207`

**Description:**
The `agent_capable` node calls `capable_llm.bind_tools(tools)` on every invocation of the node:

```python
async def agent_capable(state: AgentState) -> dict:
    llm = capable_llm.bind_tools(tools)  # called on every LLM turn
    messages = [SystemMessage(content=system_prompt), *state["messages"]]
    response = await llm.ainvoke(messages)
```

`bind_tools` creates a new model instance with the tools schema serialized. In LangChain, this
involves JSON schema generation for each tool's Pydantic model on every call. For agents with
many tools (the LO assistant and UW assistant each have ~15 tools), this is measurable CPU work
repeated on every agent turn and every tool call loop iteration.

**Suggested fix:** Pre-bind the tools once at graph construction time and capture the bound LLM
in the closure:

```python
llm_with_tools = capable_llm.bind_tools(tools)  # done once at build time

async def agent_capable(state: AgentState) -> dict:
    messages = [SystemMessage(content=system_prompt), *state["messages"]]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}
```

---

### PE-08: `get_agent` Performs a Filesystem `stat()` Call on Every Chat Message

**File:** `packages/api/src/agents/registry.py:62-106`

**Description:**
Every WebSocket message that triggers an agent invocation calls `get_agent(agent_name, ...)`.
The registry has a 5-second debounce (`_MTIME_CHECK_INTERVAL`), but within those 5 seconds,
any second request within a fast WebSocket session skips the stat(). However, after 5 seconds --
which is likely for a multi-turn conversation -- every message causes a `config_path.stat()` call
(line 77). In production this is a filesystem syscall per message.

Additionally, the cache **does not include the checkpointer** in the cache key. A WebSocket that
passes a different checkpointer instance gets the cached graph built with the original checkpointer.
This is a correctness issue as well as a performance note (noted as S-6 in the deferred list, but
the filesystem stat on every message is a new finding).

**Suggested fix:** The 5-second interval is reasonable for dev hot-reload. In production (where
YAML files never change), an environment flag like `AGENT_HOT_RELOAD=false` could skip filesystem
stat entirely and return the cached graph directly. Document this optimization path.

---

### PE-09: `run_agent_stream` Opens a New DB Session for Every Audit Event

**File:** `packages/api/src/routes/_chat_handler.py:124-137`

**Description:**
The inner `_audit` closure opens a brand new `SessionLocal()` async context for every audit
event write: tool invocations, safety blocks, and tool auth denials. A single agent turn with
3 tool calls produces 3 separate DB connection checkouts plus 3 advisory lock acquisitions
(due to PE-10 in audit.py). For an agent turn with 5 tools this is 5 connections from the pool.

**Suggested fix:** Batch audit events for the turn and write them in a single session after
`graph.astream_events` completes, or pass a shared session into the audit writer if lifecycle
allows it. At minimum, consider whether tool invocation audit events need to be written
synchronously per tool or can be queued and flushed at turn end.

---

### PE-10: `_compute_denial_trend` Uses `func.to_char` for Period Grouping -- Prevents Index Use

**File:** `packages/api/src/services/analytics.py:261-302`

**Description:**
The trend query groups by `func.to_char(Decision.created_at, "YYYY-MM")` for monthly periods
and by `func.concat("Week ", func.extract("week", ...))` for weekly periods. Both expressions
apply a function to `created_at`, which prevents PostgreSQL from using any btree index on
`decision.created_at`. The query falls back to a sequential scan of all decisions in the time
range, extracting and formatting the timestamp for every row.

**Suggested fix:** Use `date_trunc('month', created_at)` for monthly grouping and
`date_trunc('week', created_at)` for weekly grouping. These functions can leverage partial
indexes. The formatting to `"YYYY-MM"` string can be applied in Python after the query.

---

### PE-11: `get_application_status` Runs `check_completeness` Then `get_application` -- Duplicate Load

**File:** `packages/api/src/services/status.py:98-181`

**Description:**
`get_application_status` calls `check_completeness` (line 108) which itself calls
`get_application` inside it. Then on line 113 it calls `get_application` again. The application
ORM object is loaded twice from the database for a single status request.

Additionally, in `applications.py:208-213`, `get_status` also calls `app_service.get_application`
a third time after calling `get_application_status`, meaning a single `GET /applications/{id}/status`
for an LO/admin user loads the application **three times**.

**Suggested fix:** Refactor `check_completeness` to accept an already-loaded `Application` object
as an optional parameter so the caller can reuse the loaded object.

---

## Suggestion

### PE-12: `fetch_observations` Paginates LangFuse API Sequentially

**File:** `packages/api/src/services/langfuse_client.py:60-119`

**Description:**
The LangFuse observation fetch paginates sequentially (`while True: page += 1`). If LangFuse
returns many pages (large time ranges or high call volume), each page is fetched one at a time
with a fresh HTTP request. The 60-second TTL cache prevents repeated fetches, but the initial
population can be slow.

**Suggested fix:** If the LangFuse API supports it, fetch pages in parallel using `asyncio.gather`
once the total page count is known from the first response's `meta.totalPages`. This is a minor
optimization since the 60s TTL makes this infrequent, but worth noting for demo scenarios with
large datasets.

---

### PE-13: `_compute_turn_times` and `_lo_avg_turn_time` Duplicate Subquery Logic

**File:** `packages/api/src/services/analytics.py:107-183, 527-575`

**Description:**
Both functions build near-identical subqueries for pairing `from_events` and `to_events` from
`audit_events`. The `_lo_avg_turn_time` version adds an Application join and LO filter but is
otherwise structurally identical. This duplication means any index or query optimization applied
to one must be manually applied to the other.

**Suggested fix:** Extract a shared `_build_stage_transition_subqueries(from_stage, to_stage, filters)`
helper that both callers use. Addresses maintainability without changing runtime behavior.

---

### PE-14: `export_events` Default Limit of 10,000 Rows Loaded Into Memory at Once

**File:** `packages/api/src/services/audit.py:325-358`

**Description:**
`export_events` fetches up to 10,000 `AuditEvent` rows into a Python list (line 347), builds
a list of dicts from them, then serializes to JSON or CSV in memory before sending. For large
exports this materializes all rows as Python objects simultaneously.

**Suggested fix:** For the CSV format, use a SQLAlchemy `yield_per()` streaming query and write
rows incrementally to the `io.StringIO` buffer. For JSON, consider streaming newline-delimited
JSON. This avoids peak memory proportional to export size. At MVP scale this is low priority.

---

### PE-15: `ceo_model_latency`, `ceo_model_token_usage`, `ceo_model_errors`, `ceo_model_routing` Each Call `get_model_monitoring_summary` Independently

**File:** `packages/api/src/agents/ceo_tools.py:473-657`

**Description:**
The four CEO model monitoring tools (`ceo_model_latency`, `ceo_model_token_usage`,
`ceo_model_errors`, `ceo_model_routing`) each call `get_model_monitoring_summary(hours, model)`.
The LangFuse client has a 60-second TTL cache keyed on `(start_time, end_time, model)`. If the
agent invokes more than one of these tools in the same turn (which is likely when the CEO asks
for a full monitoring report), the cache prevents redundant HTTP calls.

However, if the agent invokes these tools with slightly different effective timestamps (e.g.,
two tool calls 61 seconds apart), the cache misses and LangFuse is called twice. The cache key
uses full ISO timestamps, so two calls within the same second hit the cache but two calls 1 second
apart after TTL expiry both miss.

**Suggested fix:** Round the cache key timestamps to the nearest minute rather than using exact
ISO timestamps. This widens the cache hit window to the configured TTL granularity:

```python
def _cache_key(start_time: datetime, end_time: datetime, model: str | None) -> str:
    # Round to nearest minute for better cache hit rate
    start_min = start_time.replace(second=0, microsecond=0)
    end_min = end_time.replace(second=0, microsecond=0)
    return f"{start_min.isoformat()}|{end_min.isoformat()}|{model or ''}"
```

---

## Summary

| ID | Severity | Area | Description |
|----|----------|------|-------------|
| PE-01 | Critical | Query Efficiency | N+1 queries in `get_lo_performance` (7N+1 round trips) |
| PE-02 | Critical | Query Efficiency | `_compute_turn_times` issues 4 sequential queries that can be merged |
| PE-03 | Warning | Query Efficiency | Unindexed JSONB lookups on `audit_events.event_data` in hot analytics paths |
| PE-04 | Warning | Memory | PIIMaskingMiddleware buffers full response body in memory for CEO requests |
| PE-05 | Warning | Query Efficiency | `get_pipeline_summary` runs 5 sequential queries that can be merged to 2 |
| PE-06 | Warning | Memory | `_compute_top_denial_reasons` loads all denial rows into Python for aggregation |
| PE-07 | Warning | CPU | `agent_capable` calls `bind_tools` on every LLM invocation |
| PE-08 | Warning | I/O | `get_agent` performs filesystem stat() after every 5-second debounce window |
| PE-09 | Warning | Connection Pooling | Chat handler opens new DB session per audit event within a single turn |
| PE-10 | Warning | Query Efficiency | `func.to_char` on `created_at` prevents index use in denial trend query |
| PE-11 | Warning | Query Efficiency | Application loaded 2-3x per status request due to chained service calls |
| PE-12 | Suggestion | Network | LangFuse pagination is sequential; could be parallelized |
| PE-13 | Suggestion | Maintainability | Duplicated audit event subquery logic between two analytics functions |
| PE-14 | Suggestion | Memory | `export_events` materializes up to 10,000 rows into memory at once |
| PE-15 | Suggestion | Caching | CEO model monitoring tools share no result between same-turn calls with stale TTL |
