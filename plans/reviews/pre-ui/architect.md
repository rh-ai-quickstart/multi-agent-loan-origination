# Pre-UI Architecture Review

**Reviewer:** Architect
**Scope:** `packages/api/src/`, `packages/db/src/`, `config/`, `compose.yml`
**Date:** 2026-03-02

All items in `plans/reviews/pre-ui/known-deferred.md` were excluded from this review.

---

## Critical

None.

---

## Warning

### AR-01: Dual Settings classes with duplicated defaults create config divergence risk

**Location:** `packages/api/src/core/config.py:19` and `packages/db/src/db/config.py:10`

Both `Settings` (API) and `DatabaseSettings` (DB) independently define `DATABASE_URL` and `COMPLIANCE_DATABASE_URL` with identical default values. These are loaded independently at import time by their respective `BaseSettings` instantiations. If someone changes a default in one file but not the other, the API and DB packages will silently connect to different databases.

The DB package's `DatabaseSettings` reads from environment variables but does NOT read from `.env` (no `env_file` configured in its `SettingsConfigDict`), while the API's `Settings` does read `.env` (via `_ENV_FILE`). This means in local dev without explicit env vars, the DB package falls back to its hardcoded defaults while the API may pick up values from `.env`, creating a subtle divergence path.

**Suggested fix:** The DB package should receive its connection URLs from the API at engine creation time rather than independently resolving them. Alternatively, add `env_file` to `DatabaseSettings.model_config` to match the API's behavior, and add a startup assertion that `settings.DATABASE_URL == db_settings.DATABASE_URL`.

---

### AR-02: ALLOWED_CONTENT_TYPES defined in two locations with independent maintenance

**Location:** `packages/api/src/services/document.py:24` and `packages/api/src/services/storage.py:22`

Both modules define the same `ALLOWED_CONTENT_TYPES` set (`application/pdf`, `image/jpeg`, `image/png`). The document route (`routes/documents.py:73`) references `doc_service.ALLOWED_CONTENT_TYPES`, while the document service also validates internally at line 168. The storage module's copy is not referenced by any consumer but creates a maintenance burden -- if a new type is added to one copy but not the other, behavior becomes inconsistent.

**Suggested fix:** Define `ALLOWED_CONTENT_TYPES` in exactly one place (the document service is the logical owner since it enforces the business rule) and remove the copy from storage.py.

---

### AR-03: Service layer imports from middleware layer (intake.py -> middleware.pii)

**Location:** `packages/api/src/services/intake.py:20`

The intake service imports `mask_ssn` from `middleware.pii`. This is a dependency direction violation: the service layer should not depend on the middleware layer. The middleware layer wraps HTTP concerns (request/response interception); utility functions like `mask_ssn` that are needed by both middleware and services should live in a shared layer below both.

This was previously identified (W-20 covers `build_data_scope`, which was already moved to `core.auth`), but `mask_ssn` in `services/intake.py` is a new instance of the same pattern not covered by W-20 or S-2.

**Suggested fix:** Move `mask_ssn` (and the other masking functions that are pure utility functions) from `middleware/pii.py` to `core/pii.py` or a new `core/masking.py`. The middleware class itself stays in `middleware/pii.py` and imports from core. This preserves the current `build_data_scope` pattern established in the pre-phase-3 cleanup.

---

### AR-04: Document upload content-type validation duplicated across route and service layers

**Location:** `packages/api/src/routes/documents.py:72-78` and `packages/api/src/services/document.py:168-171`

The route layer checks `content_type not in doc_service.ALLOWED_CONTENT_TYPES` and raises an HTTP 422 if invalid. The service layer (`upload_document`) then checks the same condition and raises `DocumentUploadError`. The route-level check will always fire first, making the service-level check dead code.

This is architecturally unclear: if the service is meant to be the single source of validation (defense-in-depth), then the route should not duplicate the check. If both checks are intentional (belt-and-suspenders), the error messages should differ to make it clear which layer caught the issue.

**Suggested fix:** Remove the route-level content-type check and let the service own validation. The route already catches `DocumentUploadError` and converts it to an HTTP response. This follows the existing pattern where routes delegate validation to services.

---

### AR-05: `_chat_handler.py` imports private functions from middleware.auth

**Location:** `packages/api/src/routes/_chat_handler.py:20`

The chat handler imports `_decode_token` and `_resolve_role` from `middleware.auth`. These are underscore-prefixed (private by Python convention) functions being used as a public API. This creates a fragile coupling -- any refactoring of the auth middleware's internals could break the chat handler without any public API contract warning.

**Suggested fix:** Either remove the underscore prefix to promote these to public API (they are functionally stable), or extract a `core.auth.decode_and_resolve(token: str) -> tuple[TokenPayload, UserRole]` function that both the HTTP middleware and WebSocket auth can use.

---

### AR-06: Model monitoring routes fetch full summary then discard most of it

**Location:** `packages/api/src/routes/model_monitoring.py:55-111`

The five sub-endpoints (`/latency`, `/tokens`, `/errors`, `/routing`) each call `_safe_summary()` which fetches the complete `ModelMonitoringSummary` (all four metric categories), then return only one field. This means a request to `/model-monitoring/latency` also computes token usage, errors, and routing distribution -- all discarded.

With LangFuse as the data source (external HTTP calls), this means 4x the necessary external API calls per sub-endpoint request.

**Suggested fix:** Either (a) make the service accept a filter parameter so it only computes the requested metric category, or (b) remove the sub-endpoints and only expose the full summary endpoint (which already exists). Option (b) is simpler for an MVP.

---

### AR-07: Conversation service singleton bypasses FastAPI dependency injection

**Location:** `packages/api/src/services/conversation.py:187-192`

`ConversationService` is a module-level singleton accessed via `get_conversation_service()`, initialized in the app lifespan (`main.py:50-51`). This bypasses FastAPI's dependency injection system, making it harder to replace in tests and invisible to FastAPI's dependency resolution.

Similarly, `StorageService` (`services/storage.py:122-143`) and `ExtractionService` (`services/extraction.py`) use the same module-singleton pattern. While this works, it creates three different patterns for service lifecycle management:
1. FastAPI `Depends()` for DB sessions and user context
2. Module-level singletons for conversation, storage, and extraction
3. Stateless module functions for most other services (application, document, audit, etc.)

**Suggested fix:** Not a blocking issue for MVP, but the three patterns should be documented as intentional. The singleton services are the ones that manage connections (Postgres checkpointer, S3 client) and must survive across requests, which is a valid reason to not use `Depends()`. Add a docstring or architecture note explaining the three lifecycle patterns.

---

## Suggestion

### AR-08: Missing `env_file` in DatabaseSettings causes silent .env divergence

**Location:** `packages/db/src/db/config.py:12`

`DatabaseSettings` uses `SettingsConfigDict(extra="ignore")` without `env_file`. The API's `Settings` uses `env_file=str(_ENV_FILE)`. This means if a developer sets `DATABASE_URL` in `.env` (the documented approach), the DB package will not see it -- it only reads from actual environment variables. In practice this works because `compose.yml` sets real env vars, and local dev uses the hardcoded defaults. But it could confuse developers who expect `.env` to apply globally.

**Suggested fix:** Add `env_file` to `DatabaseSettings` matching the API's pattern, or document that the DB package only reads real env vars.

---

### AR-09: No explicit layering documentation for import rules

**Location:** Project-wide

The codebase has a clear implicit layering: `db` (lowest) -> `core` / `schemas` -> `services` -> `middleware` / `agents` -> `routes` (highest). The `main.py` sits above everything. Dependency direction is correctly enforced (verified: no service imports from routes/agents, no DB imports from API).

However, this layering is not documented anywhere. One violation already exists (AR-03: intake.py imports from middleware), and more could creep in without explicit rules. The architecture document (`plans/architecture.md`) describes component boundaries at the system level but not within the API package.

**Suggested fix:** Add a brief package-internal layer diagram to either `plans/architecture.md` Section 4 or a new `.claude/rules/` file. The diagram should make the allowed import directions explicit: `routes -> services -> core/schemas; agents -> services -> core/schemas; middleware -> core/schemas`.

---

### AR-10: `routes/_chat_handler.py` naming convention inconsistency

**Location:** `packages/api/src/routes/_chat_handler.py`

The underscore prefix suggests this is a private module, but it is imported by four public route modules (`borrower_chat.py`, `loan_officer_chat.py`, `underwriter_chat.py`, `ceo_chat.py`). It also exports `create_authenticated_chat_router` which is a factory function, not a route handler. Functionally it is shared infrastructure for the chat subsystem.

**Suggested fix:** Either rename to `chat_support.py` or `chat_factory.py` (dropping the underscore prefix since it is not private), or move the `create_authenticated_chat_router` factory to a separate module and keep `_chat_handler.py` for the streaming internals only.
