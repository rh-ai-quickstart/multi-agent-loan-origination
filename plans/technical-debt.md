# Technical Debt

Tracked items to address before production or during hardening phases. Items from Phase 1 review deferred list are prefixed with their original ID (D1-D21).

## Pre-Production (address before any non-local deployment)

### (D2) WebSocket chat: no rate limits, no message size limits, no connection limits

`packages/api/src/routes/chat.py` and `borrower_chat.py` accept unbounded messages without rate limiting or connection caps. Add per-user connection limits and message throttling.

### (D4) No rate limiting on any endpoint

No rate limiting exists project-wide. Add `slowapi` or equivalent middleware. Critical for public endpoints (`/api/public/*`) and auth endpoints.

### (D7) Unbounded conversation history in WebSocket

`routes/chat.py` accumulates messages in a local list for non-checkpointer fallback. No sliding window or max-messages cap. For long sessions this could exhaust memory. Add a max-messages limit (e.g., 100) with oldest-message eviction.

### (D17) Fragile `Path(__file__).parents[4]` resolution

`agents/registry.py:20` and `inference/config.py:25` use hardcoded parent traversal depth. Breaks if the package is restructured. Use a project root marker file or env var instead.

### Admin panel uses separate sync engine

`packages/api/src/admin.py` creates its own `sqlalchemy.create_engine`. SQLAdmin requires a sync engine, but the URL derivation should be centralized.

### JWKS key rotation lacks integration test

Cache-bust-on-kid-mismatch logic in `middleware/auth.py` has no automated test coverage. Add integration test once Keycloak is in CI.

### Data scope query filtering lacks integration tests

`_apply_scope` in `services/application.py` is the core RBAC enforcement on data access. Needs integration tests with real DB.

## Deferred Features (out of MVP scope)

### F26: Agent Adversarial Defenses (4 stories deferred)

S-4-F26-01 through S-4-F26-04. Adds regex-based prompt injection detection (Layer 1), HMDA data leakage output scanning (Layer 4), demographic proxy detection, and security_event audit logging.

**Why deferred:** Existing defenses are stronger than what F26 adds at PoC maturity:
- Llama Guard 3 (ML-based) already handles prompt injection detection -- regex keyword matching is strictly weaker and will produce false positives on legitimate mortgage queries
- HMDA schema isolation (architectural boundary, separate DB schema + session) prevents data leakage -- output text scanning for demographic keywords would flag compliance KB content referencing fair lending laws
- Proxy discrimination detection requires ML-based semantic analysis to distinguish legitimate property assessment (ZIP code for flood zone) from demographic inference; pattern matching at PoC maturity would have unacceptable false positive rates
- Tool RBAC (Layer 3) already prevents unauthorized tool access with audit logging

**Revisit when:** Moving toward production hardening, or if adversarial testing reveals gaps in Llama Guard coverage that keyword patterns could cheaply address.

### F38: TrustyAI Fairness Metrics (4 stories deferred)

S-4-F38-01 through S-4-F38-04. Adds SPD/DIR fairness metrics computed from HMDA demographics vs underwriting decisions, threshold-based alerts, and a CEO/ADMIN dashboard endpoint.

**Why deferred:** Stakeholder decision -- too much scope for the MVP timeline. The TrustyAI library requires JPype + JVM which adds infrastructure complexity. A full implementation plan exists at `plans/deferred/f38-trustyai-fairness-metrics.md` and can be picked up post-MVP.

**Revisit when:** Post-MVP hardening, or when a frontend dashboard for executive metrics is prioritized.

## Resolved

| ID | Finding | Resolution |
|----|---------|------------|
| D1 | SQLAdmin had no authentication | Added `AdminAuth` backend -- login required when `AUTH_DISABLED=false` |
| D3 | `AUTH_DISABLED=true` hardcoded in compose.yml | Now uses `${AUTH_DISABLED:-true}` with env override |
| D5 | CORS wildcards for methods/headers | Restricted to actual methods and `Authorization`/`Content-Type` headers |
| D6 | Sync JWKS fetch blocks event loop | Migrated to async `httpx.AsyncClient` |
| D8 | `verify_aud` disabled in JWT validation | Fixed in PR #73 -- `verify_aud: True` with `KEYCLOAK_CLIENT_ID` |
| D9 | HMDA route didn't verify application ownership (IDOR) | Fixed in `collect_demographics()` -- uses `apply_data_scope` |
| D10 | `audit_events.event_data` was Text, not JSONB | Migrated to `JSON` column type |
| D11 | SSN field named `ssn_encrypted` but stored plaintext | Renamed to `ssn` |
| D12 | Safety shields fail-open on output errors | Changed to fail-closed (PR #89) |
| D14 | Application service untested | Tests added across Phases 2-5 |
| D15 | HMDA `collection_method` only stored race method | Per-field methods for race, ethnicity, sex, age |
| D16 | Agent registry stat() on every WS message | Added 5s mtime check interval |
| D18 | DB package reads `os.environ` directly | Both packages now use `pydantic_settings.BaseSettings` |
| D19 | HMDA borrower_id not validated against junction table | Validates via `ApplicationBorrower` lookup |
| D20 | Co-borrower management endpoints missing | POST/DELETE `/applications/{id}/borrowers` implemented |
| D21 | Per-borrower financials missing | `borrower_id` FK on `ApplicationFinancials` |
| P-1 | CEO persona unimplemented | Phase 5 complete (PRs #73-88) |
| P-4 | F23 Container Deployment not started | Helm charts complete (PRs #82, #87) |
| P-5 | LoanType ARM missing | Added `ARM` enum value + product catalog entry |
| -- | SQLAlchemy deprecated `declarative_base()` | Migrated to `DeclarativeBase` |
| -- | Pydantic v2 deprecated `class Config` | Migrated to `SettingsConfigDict` |
| -- | Ruff extends nonexistent shared config | Replaced with inline config |
| -- | Config-driven tool auth registry | Loads from YAML config files |
