# Pre-UI Orchestrator Cross-Cutting Review

**Reviewer:** Orchestrator (main session)
**Date:** 2026-03-02
**Scope:** Cross-cutting coherence, UI readiness gaps, assumption gaps, data flow integrity, configuration coherence

This review focuses on issues that fall BETWEEN specialist scopes -- things no single specialist would catch. Items in `known-deferred.md` are excluded.

---

## Critical

### OR-01: Borrower cannot see their own decisions via REST

**Location:** `packages/api/src/routes/decisions.py:19-29`

The decisions list endpoint requires roles `ADMIN, LOAN_OFFICER, UNDERWRITER, CEO` -- borrowers are excluded. However, the product plan (F6, F11) and the borrower assistant YAML both promise borrowers can "track application status and underwriting conditions." Conditions are accessible to borrowers, but the actual decision outcome (approved/denied/conditional) is not exposed via REST. The borrower can only learn their decision through the chat agent or the status endpoint's stage field, never through a direct decisions query.

A frontend building the borrower view has no REST endpoint to show "Your application has been approved" with rationale. The status endpoint (`/applications/{id}/status`) gives the stage label but not the decision details (rationale, denial reasons, AI recommendation, etc.).

**Suggested fix:** Either add `UserRole.BORROWER` to the decisions endpoint RBAC (with data scope filtering to own applications only), or create a dedicated borrower-facing decision summary endpoint that returns a redacted view (no AI internals, just decision type + rationale + denial reasons if applicable).

### OR-02: CORS default blocks containerized UI from reaching API

**Location:** `packages/api/src/core/config.py:33`, `compose.yml:89`

The `ALLOWED_HOSTS` default in config.py is `["http://localhost:5173"]` (Vite dev server). But compose.yml does NOT set `ALLOWED_HOSTS` for the API container. The UI container serves on `http://localhost:3000` (mapped from container port 8080). When the containerized UI makes API requests, the browser sends origin `http://localhost:3000`, which does not match `http://localhost:5173`.

The Helm values.yaml sets `ALLOWED_HOSTS: '["*"]'`, which works for production but is not set in compose.yml. This means `podman-compose up` without the `.env` file results in CORS failures for all UI requests.

**Suggested fix:** Add `ALLOWED_HOSTS: '["http://localhost:5173", "http://localhost:3000"]'` to the API environment in compose.yml. Or change the config.py default to include both origins.

---

## Warning

### OR-03: AUTH_DISABLED dev user is always ADMIN -- no way to test per-role UI views

**Location:** `packages/api/src/middleware/auth.py:146-152`, `packages/api/src/routes/_chat_handler.py:41-49`

When `AUTH_DISABLED=true` (the default in compose.yml), the REST middleware always returns a user with `role=ADMIN` and `full_pipeline=True` data scope. The WebSocket handler is smarter: it uses the required_role to determine what dev user to create. But REST endpoints always behave as admin.

A frontend developer building role-specific views (borrower sees X, LO sees Y, CEO sees Z) cannot test RBAC differences without running Keycloak. Since the UI's stated purpose is to be replaceable and the quickstart promises "single-command local setup", this is a significant friction point.

**Suggested fix:** Accept an optional `X-Dev-Role` header (or query param `?dev_role=borrower`) when `AUTH_DISABLED=true` that overrides the dev user's role. This lets frontend developers switch personas without Keycloak.

### OR-04: Response envelope inconsistency across endpoint families

**Locations:**
- Applications: `{data: [...], pagination: {...}}` (consistent envelope)
- Analytics: Raw object, no `data` wrapper (`PipelineSummary` returned directly)
- Audit session/application/decision: Custom envelope `{session_id, count, events}` / `{application_id, count, events}`
- Audit search: `{count, events}` (no data wrapper)
- Health: Raw array `[{...}]`
- Products: Raw array `[{...}]`
- Admin seed: Raw object `{status, seeded_at, ...}`
- Model monitoring: Raw object `{langfuse_available, latency, ...}`

A frontend team building a generic API client layer will need special handling for each endpoint family. There is no single `response.data` pattern they can rely on.

This is in known-deferred as W-29 (products endpoint) and S-24 (audit endpoints), but the scope of the inconsistency is wider than those two items suggest -- it affects analytics, admin, model monitoring, and health endpoints as well.

**Suggested fix:** For the UI build phase, document the three response patterns (paginated envelope, single-resource envelope, raw response) in the API README with explicit lists of which endpoints use which pattern. Standardization can happen later, but the frontend team needs a map now.

### OR-05: get_decision single-decision endpoint loads ALL decisions then filters in Python

**Location:** `packages/api/src/routes/decisions.py:69-88`

The `get_decision` endpoint calls `get_decisions(session, user, application_id)` which loads ALL decisions for the application, then loops through in Python to find the matching `decision_id`. This is an O(N) scan where a direct SQL `WHERE Decision.id == decision_id` would be O(1). For a UI that shows individual decision detail pages, this is inefficient per request.

**Suggested fix:** Add a `get_decision_by_id` service function that queries by both `application_id` and `decision_id` directly.

### OR-06: WebSocket paths are not discoverable from OpenAPI spec

**Location:** `packages/api/src/main.py:138-142`, `packages/api/src/routes/_chat_handler.py:291`

WebSocket endpoints (`/api/chat`, `/api/borrower/chat`, `/api/loan-officer/chat`, `/api/underwriter/chat`, `/api/ceo/chat`) are registered as WebSocket routes, which FastAPI/OpenAPI does not include in the generated spec. A frontend developer using the Swagger UI or OpenAPI JSON will not see these endpoints at all.

Combined with the WebSocket protocol (message types: `message`, `token`, `done`, `error`, `safety_override`) being documented only in the chat.py module docstring, a frontend team has no single reference for the real-time communication contract.

**Suggested fix:** Create a `docs/websocket-protocol.md` (or add to the API README) that documents: (1) all WebSocket paths with required roles, (2) the authentication mechanism (`?token=<jwt>` query param), (3) the message protocol (client send format, server send types), (4) the conversation history REST endpoint for each persona. This is the highest-value documentation for UI integration.

### OR-07: Keycloak client `summit-cap-ui` redirect URIs don't include container port

**Location:** `config/keycloak/summit-cap-realm.json:26`

The Keycloak client allows redirects to `http://localhost:3000/*` and `http://localhost:5173/*`. The compose.yml maps the UI container to port 3000 (`"3000:8080"`), so this works. However, if the UI is deployed behind the Helm chart's OpenShift Route (which would use HTTPS on a different hostname), the redirect URIs won't match. The Helm chart sets `routes.ui.host: ""` which means the hostname is auto-generated by OpenShift.

For local development this is fine. For the Helm deployment, the Keycloak realm JSON needs to include the route hostname in `redirectUris` and `webOrigins`, or the Keycloak deployment needs a post-import script to add them.

**Suggested fix:** Document in the Helm README that Keycloak redirect URIs must be manually updated after deployment, or add a Helm hook that patches the Keycloak client via the admin API.

### OR-08: Condition and decision schemas use `str` for fields that have enums

**Location:** `packages/api/src/schemas/condition.py:17-18` (`severity: str`, `status: str`), `packages/api/src/schemas/decision.py:16` (`decision_type: str`)

This is already in known-deferred as S-21, but from the UI perspective it creates a concrete problem: the frontend must hardcode enum values (condition severity levels, condition statuses, decision types) rather than getting them from the schema. If a new enum value is added to the DB, the frontend won't know about it.

**Suggested fix:** At minimum, add a `/api/public/enums` endpoint (or include enum values in the OpenAPI schema via Literal types) so the frontend can programmatically discover valid values.

### OR-09: No PATCH/PUT endpoint for application stage transitions -- only embedded in PATCH body

**Location:** `packages/api/src/routes/applications.py:336-399`

Stage transitions are embedded inside the general `PATCH /api/applications/{id}` endpoint -- the frontend sends `{"stage": "underwriting"}` as a patch field. This conflates data edits with state machine transitions. A UI building a "Submit to Underwriting" button must construct a PATCH body with just `{"stage": "processing"}`, which is non-obvious.

Additionally, there is no endpoint to get the list of valid next stages for a given application. The frontend must either hardcode the state machine or guess.

**Suggested fix:** Add a `GET /api/applications/{id}/transitions` endpoint that returns the set of valid next stages. This costs almost nothing to implement (it just calls `ApplicationStage.valid_transitions()`) and dramatically improves frontend ergonomics.

### OR-10: No endpoint to list/search borrowers independently of applications

**Location:** `packages/api/src/routes/` (no borrowers.py)

The `add_borrower` endpoint at `POST /applications/{id}/borrowers` requires a `borrower_id`, but there is no `GET /api/borrowers` or search endpoint to find borrower IDs. A loan officer UI building a "Add co-borrower" flow would need to know the borrower_id already, with no way to look it up through the API.

Borrowers are created through the chat intake flow, not through REST. This means the only way to discover borrower IDs is through the application response (which lists borrowers linked to that application).

**Suggested fix:** Add a `GET /api/borrowers?search=<name_or_email>` endpoint (RBAC: LO, UW, ADMIN) that returns basic borrower info. This enables the co-borrower linking workflow from the UI.

---

## Suggestion

### OR-11: Audit export for CEO includes PII masking via middleware but CSV content type may bypass it

**Location:** `packages/api/src/routes/audit.py:167-204`, `packages/api/src/middleware/pii.py:111-113`

The audit export endpoint can return CSV format (`?fmt=csv`). The PII masking middleware only processes `application/json` responses (line 112 check). If the export returns CSV with PII fields, the CEO would see unmasked PII in the CSV export. The route docstring says "PII masking is applied by the PIIMaskingMiddleware for CEO role" but this is incorrect for CSV format.

**Suggested fix:** Either apply PII masking inside the `export_events` service function before serialization (so it works regardless of format), or document that CSV exports are admin-only (not CEO).

### OR-12: Conversation history response has no pagination and no timestamp

**Location:** `packages/api/src/schemas/conversation.py:7-20`

The `ConversationHistoryResponse` returns a flat list of `{role, content}` messages with no timestamps and no pagination. For a UI rendering chat history, the lack of timestamps means the frontend cannot display "2 hours ago" labels. The lack of pagination means long conversations will return unbounded data.

**Suggested fix:** Add an optional `timestamp` field to `ConversationMessage` and consider a `limit` query parameter on the history endpoint.

### OR-13: No OpenAPI tags for WebSocket-related REST endpoints

**Location:** `packages/api/src/main.py:138-142`

All five chat routers are registered with `tags=["chat"]`, but the conversation history GET endpoints (e.g., `/api/borrower/conversations/history`) are also tagged as "chat". In the Swagger UI, these REST endpoints are mixed in with the WebSocket-related documentation. A frontend developer looking for "borrower endpoints" in the OpenAPI spec would find application CRUD under "applications" but conversation history under "chat".

**Suggested fix:** Use persona-specific tags (e.g., `tags=["borrower"]`, `tags=["loan-officer"]`) or add a secondary tag so REST history endpoints are discoverable alongside their persona's other endpoints.

### OR-14: S3_ENDPOINT port mismatch between config.py default and compose.yml

**Location:** `packages/api/src/core/config.py:108`, `compose.yml:106`

config.py defaults `S3_ENDPOINT` to `http://localhost:9090` (the MinIO API port mapped by compose). compose.yml sets it to `http://minio:9000` (the internal container port). These are both correct for their respective contexts (local dev vs. container). However, the Helm values.yaml also uses `http://minio:9000`. All three agree on the intent but a developer running the API locally (not in container) against a compose-started MinIO needs to know to use port 9090. This is a documentation gap, not a bug.

**Suggested fix:** Document the port mapping in the API README or a `.env.example` file.

### OR-15: No endpoint to get current user's profile/identity

**Location:** `packages/api/src/routes/` (no user profile endpoint)

There is no `GET /api/me` or `GET /api/user/profile` endpoint. A UI that needs to display the current user's name, email, and role in the header must parse the JWT client-side or make a Keycloak userinfo call. While this is common in OIDC applications, providing a server-side endpoint would be simpler for the UI and would confirm that the server agrees on the user's role (which determines UI routing).

**Suggested fix:** Add a `GET /api/me` endpoint that returns `UserContext` (user_id, role, email, name). This is trivial to implement using the existing `get_current_user` dependency.

### OR-16: Keycloak realm has no `prospect` user for testing public flow

**Location:** `config/keycloak/summit-cap-realm.json:40-125`

The Keycloak realm defines a `prospect` role (line 13) but no user has the `prospect` realm role. The public chat endpoint is unauthenticated so this is fine for the chat flow, but a UI may want to distinguish between "anonymous" and "authenticated prospect" states. The missing prospect user is a minor gap for testing.

**Suggested fix:** No action needed now, but note for the UI team that the public persona has no Keycloak user and the public chat WS endpoint does not require authentication.

