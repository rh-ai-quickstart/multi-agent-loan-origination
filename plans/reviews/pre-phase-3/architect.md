# Architecture Review -- Pre-Phase 3

Reviewer: Architect
Date: 2026-02-26
Scope: Structural issues affecting Phase 3 (Loan Officer) readiness and beyond

---

## ARCH-01: Agent Registry Hardcodes Agent-to-Module Mapping

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/registry.py:34-44`
**Description:** The `_build_graph()` function uses an if/elif chain to map agent names to Python modules. Adding the three Phase 3 agents (LO Assistant, Underwriter Assistant, CEO Assistant) requires modifying this function each time, contradicting the architecture's "configuration-driven extensibility" principle (Section 2.3) which states: "A Quickstart user can add a persona by adding configuration, not by modifying framework code."
**Impact:** Every new agent requires a code change in the registry in addition to adding a YAML config file and a Python module. At 5 agents this becomes a maintenance burden and diverges from the stated architecture. The pattern also makes it impossible for a Quickstart adopter to add an agent without modifying framework code.
**Recommendation:** Use a convention-based lookup (e.g., agent name maps to a module via `importlib.import_module(f".{agent_name.replace('-', '_')}", package=__name__)`) or a registry dict populated by decorators. Each agent module already exports a `build_graph()` function, so the interface is consistent.

---

## ARCH-02: Borrower Tools Create Independent DB Sessions, Bypassing Route-Level Session Management

**Severity:** Critical
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py` (lines 71, 121, 175, 293, 320, 365, 427, 469, 501, 571, 627, 677)
**Description:** Every borrower tool function creates its own `SessionLocal()` context manager for database access, completely separate from the session managed by the route handler. This means:
1. Agent tool calls and the route handler operate in different transactions.
2. The audit events written in tools (e.g., `start_application`, `update_application_data`) and the audit events written in `_chat_handler.py` use different sessions, so a failure in one does not roll back the other.
3. Data written by a tool is committed independently. If the agent invocation fails after a tool commits, the side effects persist without a corresponding completion event.

This also differs from how REST route handlers work (they receive a session via `Depends(get_db)` and commit once at the end), creating an inconsistent transaction boundary pattern across the codebase.

**Impact:** Phase 3 introduces LO and UW agents that will perform higher-stakes operations (submit to underwriting, issue conditions, render decisions). The current pattern means these operations will commit independently of the conversation context, making it impossible to maintain transactional consistency between agent actions and their audit trail. A tool that commits a decision followed by a crashed agent leaves an orphaned decision with no audit completion record.
**Recommendation:** Pass the database session through the LangGraph state (or via a contextvar set by the chat handler) so that tool calls participate in the same transaction scope as the conversation. Alternatively, wrap the entire agent invocation in a transaction and have tools flush rather than commit, with the handler committing once after the full turn completes.

---

## ARCH-03: Dual Configuration Systems for LLM Settings

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/core/config.py:83-98`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/inference/config.py`
**Description:** LLM configuration exists in two parallel systems:
1. `core/config.py` Settings has `LLM_BASE_URL`, `LLM_MODEL_FAST`, `LLM_MODEL_CAPABLE`, `LLM_API_KEY` as environment variables.
2. `inference/config.py` loads `config/models.yaml` which also defines model endpoints, names, and API keys (with `${ENV_VAR}` substitution).

The agent modules (`public_assistant.py`, `borrower_assistant.py`) use `inference/config.py` to get model tiers, which reads from `models.yaml`. The `inference/client.py` also reads from `models.yaml`. But the Settings object in `core/config.py` carries its own LLM fields that nothing in the agent path reads.

**Impact:** A developer changing `LLM_MODEL_FAST` in the environment expects it to affect model routing, but agents use `models.yaml` (which may have different values unless the YAML uses `${LLM_MODEL_FAST}` placeholders). This dual source of truth creates confusion about which config governs agent behavior, especially as Phase 3 adds more agents. The Settings fields are effectively dead code for the agent path.
**Recommendation:** Choose one authoritative config path. Either: (a) remove the LLM fields from Settings and route everything through `models.yaml`, or (b) have `models.yaml` be the sole configuration but ensure its env var placeholders reference the same Settings fields. Document clearly which file governs what.

---

## ARCH-04: No Agent Interface Contract for Phase 3 Agents

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/` (directory structure)
**Description:** The architecture (Section 2.3) defines five agents, but only two exist: `public_assistant.py` and `borrower_assistant.py`. Both follow the same pattern (duplicate code for LLM construction, tool wiring, and `build_graph()` signature), but there is no abstract base class, protocol, or interface that formalizes what an agent module must provide. The `build_routed_graph()` in `base.py` is the de facto framework, but the per-agent modules duplicate ~20 lines of boilerplate each (LLM construction, tool role extraction, the `build_graph` wrapper).

**Impact:** Phase 3 adds three agents (LO, UW, CEO). Without a formalized interface, each will copy-paste the boilerplate, increasing the risk of divergence (e.g., one agent forgets to extract `tool_allowed_roles`, or constructs LLMs differently). The existing duplication between `public_assistant.py` and `borrower_assistant.py` already demonstrates this: they are nearly identical except for the tool list.
**Recommendation:** Extract the common boilerplate (LLM construction from tiers, tool role extraction from YAML, `build_graph` delegation to `build_routed_graph`) into a shared factory function in `base.py`. Each agent module would then only define its unique tool list and any per-agent customizations.

---

## ARCH-05: PII Masking Is Route-Level Only, Not Middleware

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/applications.py:81-87`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/middleware/pii.py`
**Description:** Despite `pii.py` living in the `middleware/` directory, PII masking is applied manually in each route handler via explicit `if user.data_scope.pii_mask` checks. The architecture (Section 2.2) states: "PII masking for the CEO role is applied at this layer before data reaches the response" and describes it as part of the RBAC middleware pipeline. Currently:
- `applications.py` manually calls `mask_application_pii()` in both `list_applications` and `get_application`.
- No other route applies PII masking (documents, conditions, rate locks).
- The agent tools do not apply PII masking at all.

**Impact:** Phase 3 introduces LO and CEO agents that access application data through tools. The CEO agent's tools will need PII masking, but the current pattern requires adding masking logic to every tool and every route individually. This is error-prone and violates the architecture's intent of centralizing PII masking at the gateway layer. Missing masking in any new route or tool leaks PII to the CEO role.
**Recommendation:** Implement PII masking as actual FastAPI middleware (response middleware) that intercepts JSON responses for CEO-role requests and applies masking rules consistently. This eliminates the need for per-route masking code and guarantees coverage for all current and future routes.

---

## ARCH-06: Conversation Service Uses Separate Connection Pool from Application DB

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/conversation.py:73`, `/home/jary/redhat/git/mortgage-ai/packages/db/src/db/database.py:16-17`
**Description:** The `ConversationService` opens its own `psycopg` connection directly to PostgreSQL (line 73), completely outside of SQLAlchemy's connection pool. Meanwhile, the rest of the application uses SQLAlchemy's async engine via `SessionLocal`. The architecture (Section 3.2) states that the DB package "exports via `db` namespace" and is "imported by the API package," but the conversation service bypasses this entirely.

This creates three separate connection paths to the same database:
1. `SessionLocal` (lending_app via asyncpg/SQLAlchemy)
2. `ComplianceSessionLocal` (compliance_app via asyncpg/SQLAlchemy)
3. `ConversationService._conn` (psycopg3, direct connection, lending_app credentials)

**Impact:** The third connection is not pool-managed, so it does not participate in connection limits, health checks, or graceful shutdown beyond its own `shutdown()` method. Under load, this unmanaged connection could compete with the pool. More importantly, this connection uses the `lending_app` credentials derived from `DATABASE_URL`, meaning checkpoint tables are accessed with the same role that accesses lending data -- there is no checkpoint-specific access control.
**Recommendation:** This is a `langgraph-checkpoint-postgres` library constraint (it requires psycopg3, not asyncpg). Document this as a known deviation. Consider at minimum setting connection limits on the psycopg connection and ensuring the lifespan shutdown is robust. For Phase 3+, evaluate whether a dedicated `conversation_app` PostgreSQL role with restricted grants is warranted.

---

## ARCH-07: No Structured Error Responses (RFC 7807)

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/` (all route files)
**Description:** The API conventions rule (`.claude/rules/api-conventions.md`) specifies RFC 7807 structured error responses: `{type, title, status, detail}`. The implementation uses FastAPI's default `HTTPException` which returns `{"detail": "..."}`. There is no global exception handler that transforms errors into the specified format.

**Impact:** Phase 3 introduces the LO agent which needs programmatic error handling (the agent tools need to distinguish "application not found" from "insufficient permissions" from "validation error"). The current flat `detail` string requires parsing. Downstream consumers (frontend, agent tools) cannot reliably categorize errors. The inconsistency between the documented API convention and the implementation will compound as more endpoints are added.
**Recommendation:** Add a FastAPI exception handler that wraps all HTTPException responses in RFC 7807 format. This is a cross-cutting concern that should be addressed before Phase 3 adds more endpoints.

---

## ARCH-08: Agent State Does Not Propagate UserContext Fully

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/base.py:62-70`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:46-57`
**Description:** The `AgentState` carries `user_role: str` and `user_id: str` as flat strings. The `_user_context_from_state()` function in `borrower_tools.py` reconstructs a `UserContext` from these strings, but:
1. It fabricates the email as `{user_id}@summit-cap.local` (line 54) rather than propagating the actual email.
2. It sets the name to the user_id (line 55).
3. It recomputes `data_scope` from scratch via `_build_data_scope()`.

The `DataScope` computed at the route level (by `get_current_user()`) is thrown away when entering the agent -- only `user_role` and `user_id` survive into the graph state.

**Impact:** For Phase 3, the LO agent needs accurate `data_scope.assigned_to` filtering. Currently, the reconstruction works because `_build_data_scope` recomputes the same scope. But if the route-level scope ever includes additional context (e.g., a specific pipeline filter), that context is lost. The fabricated email could also be problematic for any agent tool that sends notifications or creates records with the user's email.
**Recommendation:** Either: (a) serialize the full `UserContext` (or at least `DataScope`) into the agent state so tools receive the actual context, or (b) pass the `UserContext` via a contextvar set by the chat handler so tools can read it without reconstruction. This also eliminates the private `_build_data_scope` import in `borrower_tools.py`.

---

## ARCH-09: Background Task for Document Extraction Has No Error Recovery

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/documents.py:98`
**Description:** Document extraction is launched via `asyncio.create_task(extraction_svc.process_document(doc.id))` as a fire-and-forget background task. The architecture (Section 2.5) describes this as "async processing" and notes it could be upgraded to a proper queue. Currently:
1. The task reference is not stored, so there is no way to cancel or monitor it.
2. If the FastAPI process restarts during extraction, the document is stuck in `processing` status permanently.
3. If the extraction task raises an exception not caught by `ExtractionService.process_document()`, it is silently swallowed by asyncio (unless an exception handler is registered).

**Impact:** Phase 3's LO agent needs to review document extraction results and conditions. Documents stuck in `processing` status block the pipeline. With more documents flowing through the system in Phase 3, the probability of orphaned processing jobs increases.
**Recommendation:** At minimum, add a startup recovery job that finds documents in `processing` status that have been there longer than a threshold (e.g., 5 minutes) and requeues them or marks them failed. Also consider storing the task reference for graceful shutdown cancellation in the lifespan handler.

---

## ARCH-10: Architecture Specifies `packages/api/src/summit_cap/` But Implementation Uses `packages/api/src/`

**Severity:** Info
**Location:** Architecture Section 10 project structure vs. actual codebase
**Description:** The architecture document (Section 10) specifies the API package structure as `packages/api/src/summit_cap/` with modules underneath. The implementation uses a flat `packages/api/src/` layout where `main.py` sits directly under `src/` and modules are `src/agents/`, `src/services/`, etc.

This was noted in the Phase 1 review (Architect Memory) but remains undocumented in the architecture. The `db` package similarly uses `packages/db/src/db/` rather than the architecture's `packages/db/src/summit_cap_db/`.

**Impact:** Quickstart adopters referencing the architecture document will find the actual codebase layout differs. This is a documentation drift issue, not a code issue.
**Recommendation:** Update Section 10 of `plans/architecture.md` to reflect the actual layout (`packages/api/src/` and `packages/db/src/db/`).

---

## ARCH-11: No WebSocket Authentication for Public Chat Endpoint

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/chat.py:29-69`
**Description:** The public chat WebSocket endpoint (`/chat`) accepts connections without any authentication or rate limiting. The architecture (Section 4.1) states that "Prospect routes bypass authentication entirely," which is by design. However, there is no abuse mitigation:
1. No rate limiting on connections or messages.
2. No connection limit per IP.
3. Each message triggers a full LLM inference call (classify + agent), which is expensive.
4. The session_id is a random UUID with no client correlation, so a client can open unlimited sessions.

**Impact:** Phase 3 makes the system more complex and resource-intensive. An unauthenticated endpoint that triggers LLM calls with no throttling is an abuse vector that becomes more impactful as the system serves authenticated users alongside public ones. A simple script opening many WebSocket connections and sending messages could exhaust LLM API quotas or degrade service for authenticated users.
**Recommendation:** Add per-connection message rate limiting at the WebSocket handler level (e.g., max N messages per minute). Consider a connection limit per IP at the reverse proxy or middleware level. This was flagged in the Phase 1 review deferred items but should be addressed before Phase 3 since the LO and UW agents share the same LLM resources.

---

## ARCH-12: Module-Level Singletons Complicate Testing and Multi-Instance Scenarios

**Severity:** Info
**Location:** Multiple files:
- `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/storage.py:117` (`_service`)
- `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/extraction.py:280` (`_service`)
- `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/conversation.py:169` (`_service`)
- `/home/jary/redhat/git/mortgage-ai/packages/api/src/inference/safety.py:182` (`_checker_instance`)
- `/home/jary/redhat/git/mortgage-ai/packages/api/src/inference/config.py:26-27` (`_cached_config`)
- `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/registry.py:23` (`_graphs`)

**Description:** The codebase uses module-level global singletons initialized at startup. This is a common Python pattern and appropriate for a single-process FastAPI application. However, the pattern has implications:
1. **Testing:** Tests must manually clear caches between test cases (e.g., `clear_agent_cache()`, `clear_client_cache()`). If a test fails to clear, subsequent tests see stale state.
2. **Workers:** If the app runs with multiple Uvicorn workers (e.g., `--workers 4`), each worker gets its own singleton instances. The agent registry cache, model config cache, and safety checker are all per-worker, which is fine. But the conversation service's psycopg connection is also per-worker, meaning N workers = N unmanaged connections outside the pool.

**Impact:** For Phase 3 development velocity, the testing concern is more immediate -- developers adding new agents and tools need clean test isolation. The multi-worker concern is a production readiness issue.
**Recommendation:** Acceptable for MVP. Document that multi-worker deployment requires awareness of per-worker connection counts. For testing, ensure each service's "clear/reset" function is called in the test fixture teardown.

---

## ARCH-13: HMDA Isolation CI Lint Check Not Implemented

**Severity:** Warning
**Location:** Architecture Section 3.3, Section 8.1
**Description:** The architecture specifies two verification mechanisms for HMDA isolation:
1. "Database role verification: `psql -U lending_app -c 'SELECT * FROM hmda.demographics'` must return permission denied error."
2. "CI lint check: no code outside `services/compliance/` references the `hmda` schema."

Neither check exists in the current CI pipeline. The codebase does correctly limit HMDA access to `services/compliance/hmda.py` and uses `ComplianceSessionLocal`, but this is enforced by convention, not by automated verification.

**Impact:** Phase 3 introduces the LO and UW agents, which add new services and tools that access lending data. Without automated enforcement, a developer could inadvertently import `ComplianceSessionLocal` or reference HMDA tables in a lending-path service. The architecture designed these checks as a safety net for exactly this growth scenario.
**Recommendation:** Add a CI step (or pre-commit hook) that greps for `hmda` schema references and `ComplianceSessionLocal` imports outside the compliance service directory. This is a simple `grep -r` check that provides high value.

---

## ARCH-14: Audit Hash Chain Advisory Lock Creates Serialization Bottleneck

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/audit.py:60`
**Description:** Every audit event write acquires a PostgreSQL advisory lock (`pg_advisory_xact_lock(900001)`) to serialize hash chain computation. The architecture (Section 3.4) acknowledges this: "At PoC scale advisory lock contention is negligible." However, the current implementation writes audit events from both REST endpoints (via route handlers) and WebSocket chat (via the `_audit()` helper in `_chat_handler.py`). Each tool invocation, safety check, and tool auth event generates an audit write.

Additionally, tool calls in `borrower_tools.py` write audit events inside their own `SessionLocal()` sessions (see ARCH-02), meaning those sessions also acquire the advisory lock, potentially contending with the chat handler's audit writes from the same conversation.

**Impact:** Phase 3 adds three more agents with more tools, significantly increasing the volume of concurrent audit writes. The LO agent performing pipeline reviews will trigger many tool invocations in rapid succession. The advisory lock serializes ALL audit writes across ALL concurrent conversations, creating a bottleneck. A single slow PostgreSQL transaction holding the advisory lock blocks every other conversation's audit writes.
**Recommendation:** The architecture explicitly states this is "a PoC-specific mechanism that would be replaced for production." For Phase 3, consider: (a) batching audit writes per conversation turn rather than per tool call, or (b) using a monotonic sequence (bigserial) for ordering instead of the hash chain for non-production deployments, with a flag to enable the hash chain for demo scenarios that showcase tamper evidence.

---

## ARCH-15: No Graceful Degradation Path When LLM Service Is Down

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/chat.py:40-47`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/documents.py:97-98`
**Description:** When the LLM service is unavailable:
- Chat endpoints: The agent invocation fails, and the generic "assistant is temporarily unavailable" error is sent. This is acceptable.
- Document extraction: `get_completion()` raises an exception caught by `ExtractionService.process_document()`, which sets the document to `PROCESSING_FAILED`. But there is no retry mechanism -- the document is permanently failed.
- The architecture (Section 7.2) says "Non-chat API operations (document upload, application status) continue to function," which is correct -- REST endpoints that don't need LLM still work.

However, there is no circuit breaker or health check that proactively detects LLM unavailability. Each request independently discovers the failure, paying the full timeout cost.

**Impact:** Phase 3 depends heavily on LLM availability for both chat (LO agent) and document processing. Without a circuit breaker, a downed LLM service causes every concurrent chat message and document extraction to individually timeout, wasting resources and creating a poor user experience. The extraction pipeline permanently fails documents that could succeed on retry.
**Recommendation:** Add a lightweight LLM health probe (e.g., periodic ping to the LLM endpoint) and expose it in the health check response. For document extraction, add a simple retry with backoff (1-2 retries) before marking a document as permanently failed.

---

## ARCH-16: Architecture Section 9.3 Config Hot-Reload Not Fully Implemented

**Severity:** Info
**Location:** Architecture Section 9.3, `/home/jary/redhat/git/mortgage-ai/packages/api/src/inference/config.py`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/registry.py`
**Description:** The architecture specifies that "Agent configuration files (`config/agents/*.yaml`) and the model routing configuration (`config/models.yaml`) support hot-reload." The implementation does support this:
- `agents/registry.py` uses mtime-based caching and rebuilds graphs on config change.
- `inference/config.py` uses mtime-based caching and clears client caches on config change.

However, the architecture also states: "Existing in-progress conversations continue using the config snapshot they started with -- only new conversations pick up changes." The current implementation does NOT isolate config snapshots per conversation. When `get_agent()` is called for each message in a conversation, it checks mtime and may rebuild the graph mid-conversation. Similarly, `get_config()` in inference may return a new config mid-conversation.

**Impact:** During a live demo where a presenter modifies agent config, in-progress conversations may see inconsistent behavior mid-stream. This is low-impact at MVP maturity since conversations are short, but worth noting as a deviation from the stated architecture.
**Recommendation:** Document this as a known deviation. The per-conversation isolation described in the architecture requires caching the graph reference at conversation start rather than re-resolving it per message. This could be addressed by storing the graph reference in the WebSocket handler's local scope (which `chat.py` already partially does by calling `get_agent()` once before the message loop).

---

## ARCH-17: Scope Service Does Not Handle Underwriter Queue Filtering

**Severity:** Warning
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/scope.py:15-49`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/middleware/auth.py:136-149`
**Description:** The architecture (Section 4.2, data access matrix) specifies that Underwriters have "Read (UW queue: R/W)" access to the pipeline. The current `_build_data_scope()` gives underwriters `DataScope(full_pipeline=True)`, which grants unfiltered access to all applications. The `apply_data_scope()` function has no filtering logic for underwriter-specific queue filtering.

For Loan Officers, the architecture specifies "Pipeline (own)" with `assigned_to` filtering, which IS implemented. But there is no equivalent "UW queue" concept.

**Impact:** Phase 3 directly introduces the Underwriter persona. The underwriter should see applications in the underwriting stage that are in their queue, not all applications across all stages. Without queue filtering, the UW agent's tools will return the full pipeline, which is both a security concern (UW seeing applications not yet submitted for underwriting) and a UX concern (noise from irrelevant applications).
**Recommendation:** Add an `underwriting_queue` scope filter to `DataScope` and implement it in `apply_data_scope()`. This should filter by application stage (only applications in `underwriting` or later stages) and optionally by assigned underwriter.

---

## ARCH-18: Compose Configuration Exposes Database on Non-Standard Port

**Severity:** Info
**Location:** `/home/jary/redhat/git/mortgage-ai/compose.yml:65`
**Description:** PostgreSQL is exposed on port 5433 (`"5433:5432"`) rather than the standard 5432. The `DATABASE_URL` defaults in `core/config.py` use port 5433 for local dev. However, the compose service-level URLs (used by the API container) correctly use port 5432 (internal Docker networking). This is a minor but common source of confusion when developers mix local and containerized development.

**Impact:** Low -- this is a developer experience issue, not a structural problem.
**Recommendation:** Document the port mapping in a .env.example or README so developers know to use 5433 for host-level access and 5432 for inter-container access.
