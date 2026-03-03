# Cross-Cutting Review (Orchestrator)

Pre-Phase 3 review focusing on issues that fall between specialist scopes --
inconsistencies across layers, assumptions that break across modules, and
integration gaps.

---

## ORCH-01: JWKS fetch blocks the async event loop

**Severity:** Warning
**Location:** packages/api/src/middleware/auth.py:34-38

`_fetch_jwks()` uses synchronous `httpx.get()` inside an async middleware
chain. When a JWT needs JWKS validation and the cache is stale, the entire
event loop blocks for up to 5 seconds (the timeout). This affects all
concurrent requests, not just the one triggering the refresh.

**Why specialists may miss it:** The security reviewer focuses on JWT
correctness. The backend reviewer sees `async def get_current_user` and
assumes the chain is async. The performance reviewer looks at DB queries.

**Recommendation:** Use `httpx.AsyncClient` or run the sync call in a
thread executor (`asyncio.to_thread`).

---

## ORCH-02: Borrower tools use independent DB sessions outside request transaction

**Severity:** Warning
**Location:** packages/api/src/agents/borrower_tools.py (all tool functions)

Every borrower tool creates its own session via `async with SessionLocal() as session:`.
This means:
- Tool operations commit independently of the agent's stream lifecycle
- If the WebSocket disconnects mid-tool-call, the audit event is committed but the
  user never sees the response
- Multiple tool calls within a single agent turn are NOT transactional -- if tool B
  fails, tool A's changes are already committed
- Advisory lock contention: each tool's session competes for the audit lock
  independently

**Why specialists may miss it:** The backend reviewer sees correct async
session usage per-tool. The database reviewer sees correct query patterns.
Neither looks at the aggregate transaction boundary across an agent turn.

**Recommendation:** Pass a session through the agent state or use a shared
session per agent invocation. At minimum, document the design decision that
tool operations are intentionally non-transactional.

---

## ORCH-03: Application.financials relationship is uselist=False but schema supports multiple

**Severity:** Critical
**Location:** packages/db/src/db/models.py:91-93, line 144-146

`Application.financials` is defined as `uselist=False`, meaning SQLAlchemy
expects at most ONE `ApplicationFinancials` row per application. But the
`ApplicationFinancials` table has a unique constraint on
`(application_id, borrower_id)`, explicitly designed for multiple financials
records per application (one per borrower, for co-borrowers).

Currently this works because only one financials record is created per
application. In Phase 3, when the loan officer manages co-borrowers with
separate financial profiles, SQLAlchemy will either raise a warning or
silently return only the first match.

**Why specialists may miss it:** The database reviewer checks the table
schema (which is correct). The backend reviewer checks the service layer
(which works today). The tech lead looks at extensibility patterns. None
tests what happens when a second financials row is inserted.

**Recommendation:** Change to `uselist=True` (returns a list) or add a
`primaryjoin` filter for "primary borrower's financials only". This is a
breaking change to service code that accesses `app.financials` directly.

---

## ORCH-04: asyncio.create_task for extraction without reference retention

**Severity:** Warning
**Location:** packages/api/src/routes/documents.py:98

```python
asyncio.create_task(extraction_svc.process_document(doc.id))
```

The task reference is never stored. Consequences:
- If the task raises an exception, it is silently lost (Python logs a
  "Task exception was never retrieved" warning but the error is not
  actionable)
- Server shutdown kills running extractions without cleanup
- No way to cancel or track running extractions
- If the extraction updates document status in DB and the task is killed,
  the document stays in "processing" status forever

**Why specialists may miss it:** The backend reviewer sees a valid
`asyncio.create_task` call. The debug specialist looks for error handling
within functions, not around task creation. The devops reviewer looks at
container health checks.

**Recommendation:** Store task references in a set, add a done callback
that logs exceptions, and drain the set on shutdown.

---

## ORCH-05: Module-level mutable caches are not thread-safe

**Severity:** Info
**Location:** Multiple files:
- packages/api/src/agents/registry.py:23 (`_graphs` dict)
- packages/api/src/inference/safety.py:182 (`_checker_instance`)
- packages/api/src/inference/client.py:19 (`_clients` dict)
- packages/api/src/inference/config.py:26-27 (`_cached_config`, `_cached_mtime`)
- packages/api/src/middleware/auth.py:29-30 (`_jwks_data`, `_jwks_fetched_at`)

All these are module-level mutable state with no locking. In Python's
asyncio model (single-threaded event loop), this is generally safe because
there's no true parallelism. However:
- If uvicorn runs with `--workers > 1`, each process has its own copy
  (no sharing issue but no sharing benefit either)
- The pattern is fragile -- any future use of threads (e.g., for blocking I/O)
  introduces race conditions

**Why specialists may miss it:** Each module's cache looks correct in
isolation. The pattern is standard Python asyncio. Only when viewed across
the whole system does the accumulated fragility become apparent.

**Recommendation:** No immediate action needed for asyncio-only deployment.
Add a `# NOTE: not thread-safe, asyncio single-thread only` comment to each
cache to prevent future regressions.

---

## ORCH-06: Config path resolution uses brittle magic parent counts

**Severity:** Warning
**Location:**
- packages/api/src/core/config.py:15 (`parents[4]`)
- packages/api/src/inference/config.py:25 (`parents[4]`)
- packages/api/src/agents/registry.py:20 (`parents[4]`)

Each module resolves the project root by counting parent directories from
`__file__`. The magic number `4` assumes a specific nesting depth
(`packages/api/src/core/` = 4 levels up from project root). If any module
is moved, or if the project structure changes, these silently resolve to
the wrong directory.

**Why specialists may miss it:** Each reviewer sees a working path
resolution in the file they're reviewing. The pattern inconsistency (all
using `parents[4]` from different depths) is only visible when reading
multiple modules side by side.

**Recommendation:** Define `PROJECT_ROOT` once in a shared location (e.g.,
`core/config.py`) and import it everywhere. Or use a package resource /
importlib approach.

Wait -- actually checking: `core/config.py` is at
`packages/api/src/core/config.py`, so `parents[4]` goes to the repo root.
`inference/config.py` is at `packages/api/src/inference/config.py`, also
`parents[4]` to repo root. `agents/registry.py` is at
`packages/api/src/agents/registry.py`, also `parents[4]`. These are all at
the same depth, so the number is consistent. But it's still brittle -- any
file reorganization breaks all three.

**Recommendation (revised):** Define `PROJECT_ROOT` once in `core/config.py`
and import it in `inference/config.py` and `agents/registry.py`.

---

## ORCH-07: Audit event write serializes ALL concurrent operations

**Severity:** Warning
**Location:** packages/api/src/services/audit.py:60

```python
await session.execute(text(f"SELECT pg_advisory_xact_lock({AUDIT_LOCK_KEY})"))
```

Every audit event write acquires the same advisory lock, serializing ALL
audit writes system-wide. During a busy chat turn, multiple events fire:
`tool_invocation` per tool call, `safety_block` if shields trigger,
`data_collection` for field updates, `disclosure_acknowledged`, etc.

Combined with ORCH-02 (each tool uses its own session), a single agent turn
can acquire and release this lock 5+ times across different connections.
Under concurrent multi-user load, this becomes a bottleneck.

**Why specialists may miss it:** The database reviewer sees correct
advisory lock usage for hash chain integrity. The performance reviewer
looks at query patterns, not lock contention. The security reviewer
validates the hash chain logic.

**Recommendation:** For MVP, this is acceptable. Before production load
testing, consider: (1) batching audit events per-turn and flushing once,
(2) using a sequence-based approach instead of advisory locks, or
(3) moving audit writes to an async queue.

---

## ORCH-08: Conversation service uses single psycopg connection for all checkpoints

**Severity:** Warning
**Location:** packages/api/src/services/conversation.py:73-74

```python
conn = await AsyncConnection.connect(psycopg_url, autocommit=True, ...)
self._checkpointer = AsyncPostgresSaver(conn=conn)
```

A single database connection is shared across all concurrent WebSocket
sessions for checkpoint operations. Under load:
- Checkpoint reads/writes from different users queue on the same connection
- If the connection drops, ALL active chat sessions lose checkpoint ability
- No connection pool resilience

**Why specialists may miss it:** The backend reviewer sees a valid psycopg
connection. The database reviewer looks at query patterns. The performance
reviewer looks at application-level queries, not checkpoint infrastructure.

**Recommendation:** Use a connection pool (psycopg `AsyncConnectionPool`)
instead of a single connection. The `AsyncPostgresSaver` supports pool-based
initialization.

---

## ORCH-09: SSN column named "ssn_encrypted" but stores plaintext

**Severity:** Warning
**Location:**
- packages/db/src/db/models.py:49 (`ssn_encrypted = Column(String(255))`)
- packages/api/src/services/intake.py:127 (`"ssn": ("borrower", "ssn_encrypted", _identity)`)

The column is named `ssn_encrypted` suggesting encryption-at-rest, but the
`_identity` converter passes the value through unchanged. The PII masking
in `middleware/pii.py` masks SSNs in API responses, and `intake.py:338`
masks SSNs in the progress summary, but the actual database stores
plaintext SSNs.

This is a known deferred item from Phase 1 review, but it creates a
cross-cutting inconsistency: the column name misleads developers into
thinking the data is protected, and the masking layers give a false sense
of security when DB access exposes plaintext.

**Why specialists may miss it:** The security reviewer may flag the column
as needing encryption but assume the name reflects intent. The database
reviewer sees a valid column definition. The backend reviewer sees the
`_identity` converter and moves on.

**Recommendation:** Either (a) implement encryption before Phase 3 adds
more PII handling for loan officers, or (b) rename the column to `ssn`
to avoid the misleading name. Option (b) requires a migration.

---

## ORCH-10: WebSocket chat has no message size or rate limits

**Severity:** Warning
**Location:** packages/api/src/routes/_chat_handler.py:134

```python
raw = await ws.receive_text()
```

No limit on:
- Message size (a client can send megabytes of JSON)
- Message rate (a client can flood with messages)
- Concurrent connections per user
- Total concurrent connections

**Why specialists may miss it:** The security reviewer checks auth on WS.
The backend reviewer checks the message handling logic. The performance
reviewer checks DB queries. None systematically tests resource exhaustion
through the WebSocket.

**Recommendation:** Add `max_size` to the WebSocket accept, implement a
simple rate limiter (e.g., max 10 messages per minute per connection), and
limit concurrent connections per user.

---

## ORCH-11: Inconsistent error response format across REST and WebSocket

**Severity:** Info
**Location:**
- REST endpoints: FastAPI HTTPException produces `{"detail": "..."}`
- WebSocket: `{"type": "error", "content": "..."}`
- API conventions rule: RFC 7807 (`{"type": "...", "title": "...", "status": ..., "detail": "..."}`)

The codebase has three different error formats. REST uses FastAPI's default
`{"detail": ...}`, WebSocket uses `{"type": "error", "content": ...}`, and
the project rules specify RFC 7807. None of the three are aligned.

**Why specialists may miss it:** The API reviewer checks REST conventions.
The backend reviewer checks WebSocket protocol. Neither compares the two
against the project rules.

**Recommendation:** For MVP, document the intentional divergence (REST and
WS have different error shapes, RFC 7807 is a future goal). For Phase 3,
standardize REST errors to RFC 7807 since loan officer endpoints will be
the first "production-like" API surface.

---

## ORCH-12: `_build_data_scope` is imported as private function across packages

**Severity:** Info
**Location:**
- packages/api/src/middleware/auth.py:136 (definition)
- packages/api/src/routes/_chat_handler.py:17 (import)
- packages/api/src/agents/borrower_tools.py:18 (import)

`_build_data_scope` is a private function (underscore prefix) that is
imported and used by three different modules. The function is the single
source of truth for role-to-scope mapping, so it SHOULD be shared. But the
private naming suggests it's an implementation detail of auth.py.

**Why specialists may miss it:** Each reviewer sees a valid import.
The naming convention violation is only visible across files.

**Recommendation:** Rename to `build_data_scope` (remove underscore) since
it's part of the public interface of the auth module.

---

## ORCH-13: LangGraph graph is rebuilt on every call when checkpointer changes

**Severity:** Info
**Location:** packages/api/src/agents/registry.py:47-85, routes/chat.py:40

The agent cache in `_graphs` caches by agent name only, not by
checkpointer. Each WebSocket connection calls `get_agent("public-assistant", checkpointer=checkpointer)`. If the checkpointer reference is the same
singleton, the cached graph is returned. But the cache key doesn't include
the checkpointer -- if the conversation service restarts and produces a new
checkpointer instance, the cached graph has a stale checkpointer reference.

Currently this doesn't happen because the conversation service is a
singleton initialized once at startup. But if hot-reload or reconnection
logic is added, cached graphs would silently use the old checkpointer.

**Recommendation:** No action needed for MVP. Note the assumption in a
comment on the cache.
