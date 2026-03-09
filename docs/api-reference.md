<!-- This project was developed with assistance from AI tools. -->

# API Reference

This page provides an overview of the Mortgage AI API, covering authentication, response patterns, key REST endpoints, and the WebSocket chat protocol. For detailed schema documentation, see the auto-generated interactive docs at `/docs` (Swagger UI) or `/redoc`.

## Base URL Structure

All API routes are mounted under `/api/` except the health check endpoint (`/health/`).

**Development:**
- API: `http://localhost:8000`
- Interactive Docs (Swagger UI): `http://localhost:8000/docs`
- Alternative Docs (ReDoc): `http://localhost:8000/redoc`

**Base URL patterns:**
- REST endpoints: `http://localhost:8000/api/...`
- WebSocket endpoints: `ws://localhost:8000/api/...`
- Health check: `http://localhost:8000/health/`

## Authentication

The API uses JWT Bearer tokens issued by Keycloak via OpenID Connect (OIDC). All authenticated endpoints require a valid token in the `Authorization` header.

### Token Format

```
Authorization: Bearer <jwt>
```

The token is a signed JWT containing the user's identity and roles. Tokens are validated against Keycloak's JWKS endpoint using RS256 signature verification.

### Obtaining a Token

Tokens are obtained through the Keycloak OIDC authorization code flow. The UI handles this flow automatically. For API clients, use the standard OAuth2/OIDC client libraries with the following endpoints:

- **Authorization endpoint:** `{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/auth`
- **Token endpoint:** `{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token`

### Roles

| Role | Description |
|------|-------------|
| `prospect` | Unauthenticated users (public endpoints only) |
| `borrower` | Authenticated borrowers (application management, document upload, chat) |
| `loan_officer` | Loan officers (pipeline management, application review, borrower chat) |
| `underwriter` | Underwriters (risk assessment, compliance checks, decision making) |
| `ceo` | Executives (analytics, audit trails, model monitoring) |
| `admin` | System administrators (full access, seed data, admin dashboard) |

Roles are extracted from the JWT's `realm_access.roles` claim. If a user lacks the required role for an endpoint, a `403 Forbidden` response is returned.

### Development Bypass

For local development and testing without Keycloak, set the environment variable:

```bash
AUTH_DISABLED=true
```

With auth disabled:
- All authenticated endpoints accept requests without a token
- A synthetic admin user is used by default
- HTTP endpoints support role override via `X-Dev-Role` header (e.g., `X-Dev-Role: borrower`)
- WebSocket endpoints infer role from the endpoint path (e.g., `/api/borrower/chat` uses borrower role)

**Never enable `AUTH_DISABLED` in production.**

## Response Patterns

The API uses three distinct response patterns. Frontend clients must handle all three.

### 1. Paginated Envelope

Offset-paginated list endpoints wrap results in a `data` array with a `pagination` object.

```json
{
  "data": [
    { "id": 1, "stage": "application", ... },
    { "id": 2, "stage": "underwriting", ... }
  ],
  "pagination": {
    "total": 42,
    "offset": 0,
    "limit": 20,
    "has_more": true
  }
}
```

**Endpoints using this pattern:**

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/applications/` | Supports `offset`, `limit`, `sort_by`, `filter_stage`, `filter_stalled` |
| `GET` | `/api/applications/{id}/conditions` | Supports `open_only`; pagination reflects full result set |
| `GET` | `/api/applications/{id}/decisions` | Pagination reflects full result set |

The `Pagination` model is defined in `src/schemas/__init__.py`.

### 2. Custom Envelope

Audit endpoints use domain-specific wrappers with a `count` integer, a named events array, and one or more context identifiers. Unlike paginated envelopes, these do not use a `data` key.

**Audit endpoint response shapes:**

| Method | Path | Response Shape |
|--------|------|----------------|
| `GET` | `/api/audit/session` | `{ "session_id": "...", "count": N, "events": [...] }` |
| `GET` | `/api/audit/application/{id}` | `{ "application_id": N, "count": N, "events": [...] }` |
| `GET` | `/api/audit/decision/{id}` | `{ "decision_id": N, "count": N, "events": [...] }` |
| `GET` | `/api/audit/search` | `{ "count": N, "events": [...] }` |
| `GET` | `/api/audit/verify` | `{ "status": "...", "events_checked": N, "first_break_id": N\|null }` |
| `GET` | `/api/audit/decision/{id}/trace` | `{ "decision_id": N, "application_id": N, "decision_type": "...", "events_by_type": {...}, "total_events": N, ... }` |

`GET /api/audit/export` returns a file download (`application/json` or `text/csv`) with a `Content-Disposition` header, not a JSON envelope.

### 3. Raw Response

Object or array returned directly with no wrapper. This is the most common pattern.

**Single objects:**

| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/api/applications/{id}` | `ApplicationResponse` object |
| `GET` | `/api/applications/{id}/status` | `ApplicationStatusResponse` object |
| `GET` | `/api/applications/{id}/rate-lock` | `RateLockResponse` object |
| `POST` | `/api/applications/` | `ApplicationResponse` object (201) |
| `PATCH` | `/api/applications/{id}` | `ApplicationResponse` object |
| `POST` | `/api/applications/{id}/borrowers` | `ApplicationResponse` object (201) |
| `DELETE` | `/api/applications/{id}/borrowers/{bid}` | `ApplicationResponse` object |
| `POST` | `/api/applications/{id}/conditions/{cid}/respond` | `{ "data": ConditionItem }` (single-item wrapper) |
| `GET` | `/api/applications/{id}/decisions/{did}` | `{ "data": DecisionItem }` (single-item wrapper) |
| `GET` | `/api/analytics/pipeline` | `PipelineSummary` object |
| `GET` | `/api/analytics/denial-trends` | `DenialTrends` object |
| `GET` | `/api/analytics/lo-performance` | `LOPerformanceSummary` object |
| `GET` | `/api/analytics/model-monitoring` | `ModelMonitoringSummary` object |
| `GET` | `/api/analytics/model-monitoring/latency` | `LatencyMetrics` object |
| `GET` | `/api/analytics/model-monitoring/tokens` | `TokenUsage` object |
| `GET` | `/api/analytics/model-monitoring/errors` | `ErrorMetrics` object |
| `GET` | `/api/analytics/model-monitoring/routing` | `RoutingDistribution` object |
| `POST` | `/api/admin/seed` | `SeedResponse` object |
| `GET` | `/api/admin/seed/status` | `SeedStatusResponse` object |

**Arrays:**

| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/health/` | `list[HealthResponse]` |
| `GET` | `/api/public/products` | `list[ProductInfo]` |
| `POST` | `/api/public/calculate-affordability` | `AffordabilityResponse` object |

**Known inconsistency:** `GET /api/applications/{id}/decisions/{did}` and `POST /api/applications/{id}/conditions/{cid}/respond` wrap their single item in `{ "data": <item> }` rather than returning the object bare, unlike all other single-resource endpoints.

### Summary Table

| Pattern | Top-Level Shape | Used For |
|---------|-----------------|----------|
| Paginated envelope | `{ "data": [...], "pagination": {...} }` | Offset-paginated collection endpoints |
| Custom envelope | `{ "<context_key>": ..., "count": N, "events": [...] }` | Audit trail query endpoints |
| Raw response | Object or array directly | All other endpoints |

## Error Responses

All errors follow RFC 7807 Problem Details format:

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "Application with ID 999 not found",
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "instance": "/api/applications/999"
}
```

| Field | Description |
|-------|-------------|
| `type` | URI reference identifying the problem type (defaults to `about:blank`) |
| `title` | Human-readable summary of the error type |
| `status` | HTTP status code |
| `detail` | Specific explanation for this occurrence |
| `request_id` | Unique identifier for tracing this request in logs |
| `instance` | The request path that triggered the error |

**Common status codes:**

| Status | Meaning |
|--------|---------|
| `400` | Bad Request (malformed input) |
| `401` | Unauthorized (missing or invalid authentication) |
| `403` | Forbidden (authenticated but insufficient permissions) |
| `404` | Not Found (resource does not exist) |
| `409` | Conflict (state transition invalid) |
| `413` | Payload Too Large (file upload exceeds limit) |
| `422` | Unprocessable Entity (validation failed) |
| `500` | Internal Server Error |
| `503` | Service Unavailable (authentication service down) |

Pydantic validation errors (422) include detailed error information in the `detail` field.

## REST Endpoints

### Public Endpoints (No Authentication)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health/` | Health check for API and database |
| `GET` | `/api/public/products` | List available mortgage products (Conventional, FHA, VA, USDA, Jumbo) |
| `POST` | `/api/public/calculate-affordability` | Estimate maximum loan amount and monthly payment based on income and debts |

### Applications

| Method | Path | Required Role | Description |
|--------|------|---------------|-------------|
| `GET` | `/api/applications/` | borrower, loan_officer, underwriter, ceo, admin | List applications with pagination, filtering, sorting, and urgency calculation |
| `GET` | `/api/applications/{id}` | borrower (own), loan_officer, underwriter, ceo, admin | Get single application with borrower details and prequalification |
| `GET` | `/api/applications/{id}/status` | borrower (own), loan_officer, underwriter, ceo, admin | Get application workflow status and allowed transitions |
| `GET` | `/api/applications/{id}/rate-lock` | borrower (own), loan_officer, underwriter, ceo, admin | Get rate lock status and expiration |
| `GET` | `/api/applications/{id}/disclosures` | borrower (own), loan_officer, underwriter, admin | Get disclosure acknowledgment status |
| `POST` | `/api/applications/` | borrower, admin | Create new application |
| `PATCH` | `/api/applications/{id}` | borrower (own), loan_officer, admin | Update application fields |
| `POST` | `/api/applications/{id}/borrowers` | borrower (own), loan_officer, admin | Add co-borrower |
| `DELETE` | `/api/applications/{id}/borrowers/{bid}` | borrower (own), loan_officer, admin | Remove co-borrower |

**Borrower data scope:** Borrowers can only access their own applications. Other roles see all applications within their scope (LO sees assigned apps, underwriters/CEOs see all).

**PII masking:** CEO role has automatic PII masking applied to all responses (names, SSNs, emails, phone numbers replaced with redacted placeholders).

### Conditions

| Method | Path | Required Role | Description |
|--------|------|---------------|-------------|
| `GET` | `/api/applications/{id}/conditions` | borrower (own), loan_officer, underwriter, admin | List conditions (underwriter requirements) for an application |
| `POST` | `/api/applications/{id}/conditions/{cid}/respond` | borrower (own), admin | Submit response to a condition |

### Decisions

| Method | Path | Required Role | Description |
|--------|------|---------------|-------------|
| `GET` | `/api/applications/{id}/decisions` | borrower (own), loan_officer, underwriter, ceo, admin | List all decision history for an application |
| `GET` | `/api/applications/{id}/decisions/{did}` | borrower (own), loan_officer, underwriter, ceo, admin | Get single decision record |

### Documents

| Method | Path | Required Role | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/applications/{id}/documents` | borrower (own), loan_officer, admin | Upload document (triggers async extraction) |
| `GET` | `/api/applications/{id}/documents` | borrower (own), loan_officer, underwriter, ceo, admin | List documents for an application |
| `GET` | `/api/applications/{id}/documents/{did}` | borrower (own), loan_officer, underwriter, ceo, admin | Get document metadata |
| `GET` | `/api/applications/{id}/documents/{did}/download` | borrower (own), loan_officer, underwriter, admin | Download document file (CEO role cannot download files) |
| `GET` | `/api/applications/{id}/documents/{did}/extractions` | loan_officer, underwriter, admin | Get extraction results for a document |
| `GET` | `/api/applications/{id}/completeness` | loan_officer, underwriter, admin | Check document completeness (which required docs are uploaded) |

**CEO content restriction:** CEO role can view document metadata but cannot download file contents. Attempting to download as CEO returns `403 Forbidden`.

### HMDA Demographics

| Method | Path | Required Role | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/hmda/collect` | borrower, admin | Collect HMDA demographic data (stored in isolated compliance schema) |

**Disclaimer:** HMDA data collection is simulated for demonstration purposes only and is not legally compliant.

### Pipeline (Loan Officer)

| Method | Path | Required Role | Description |
|--------|------|---------------|-------------|
| `GET` | `/api/applications/pipeline` | loan_officer, admin | Get LO's assigned applications with urgency and filtering |

### Underwriting

| Method | Path | Required Role | Description |
|--------|------|---------------|-------------|
| `GET` | `/api/applications/{id}/risk-assessment` | loan_officer, underwriter, ceo, admin | Get latest risk assessment results |
| `GET` | `/api/applications/{id}/compliance-result` | loan_officer, underwriter, ceo, admin | Get latest compliance check results |

### Analytics (CEO & Admin)

| Method | Path | Required Role | Description |
|--------|------|---------------|-------------|
| `GET` | `/api/analytics/pipeline` | ceo, admin | Pipeline summary: volume, stage distribution, turn times, pull-through rate |
| `GET` | `/api/analytics/denial-trends` | ceo, admin | Denial rate trends with time series and top reasons by product |
| `GET` | `/api/analytics/lo-performance` | ceo, admin | Loan officer performance metrics |

**Query parameters:**
- `days`: Time range (1-365, default 90)
- `product`: Filter by loan type (optional, for denial trends)

### Model Monitoring (CEO & Admin)

All model monitoring endpoints require `ceo` or `admin` role.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/analytics/model-monitoring` | Overall LangFuse metrics summary |
| `GET` | `/api/analytics/model-monitoring/latency` | Latency metrics (p50, p95, p99) |
| `GET` | `/api/analytics/model-monitoring/tokens` | Token usage by model |
| `GET` | `/api/analytics/model-monitoring/errors` | Error rate and breakdown |
| `GET` | `/api/analytics/model-monitoring/routing` | Model routing distribution |

### Audit Trail

All audit endpoints require `ceo` or `admin` role unless otherwise noted.

| Method | Path | Required Role | Description |
|--------|------|---------------|-------------|
| `GET` | `/api/audit/session` | ceo, admin | Query audit events by session ID |
| `GET` | `/api/audit/application/{id}` | ceo, admin | Query audit events for an application |
| `GET` | `/api/audit/decision/{id}` | ceo, admin | Query audit events for a decision |
| `GET` | `/api/audit/search` | ceo, admin | Search audit events by type, user, date range |
| `GET` | `/api/audit/verify` | ceo, admin | Verify audit chain integrity (hash chain validation) |
| `GET` | `/api/audit/decision/{id}/trace` | ceo, admin | Get detailed decision trace (all events leading to a decision) |
| `GET` | `/api/audit/export` | ceo, underwriter, admin | Export audit events (JSON or CSV) |

**Export format:** Use `Accept: application/json` or `Accept: text/csv` header to specify format. Returns a downloadable file.

### Admin

| Method | Path | Required Role | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/admin/seed` | admin | Seed database with demo data |
| `GET` | `/api/admin/seed/status` | admin | Check seeding status |

**SQLAdmin dashboard:** `http://localhost:8000/admin` provides a web UI for database inspection (admin role required).

## WebSocket Chat Protocol

The API provides real-time chat interfaces for five personas via WebSocket. Authenticated personas persist conversation history; the public endpoint is ephemeral.

### Chat Endpoints

| WebSocket Path | Required Role | Auth Required | Conversation Persisted |
|----------------|---------------|---------------|------------------------|
| `ws://host/api/chat` | None (public) | No | No (ephemeral per connection) |
| `ws://host/api/borrower/chat` | `borrower` | Yes | Yes |
| `ws://host/api/loan-officer/chat` | `loan_officer` | Yes | Yes |
| `ws://host/api/underwriter/chat` | `underwriter` | Yes | Yes |
| `ws://host/api/ceo/chat` | `ceo` | Yes | Yes |

The public endpoint (`/api/chat`) is for unauthenticated prospects. It does not persist conversation history and assigns a new ephemeral session on every connection.

Authenticated endpoints persist conversation history across connections using a deterministic thread ID derived from the user's identity. When a user reconnects, the conversation resumes where it left off.

### WebSocket Authentication

Authenticated endpoints require a Keycloak JWT passed as a query parameter on the WebSocket upgrade request:

```
ws://host/api/borrower/chat?token=<jwt>
```

The `token` parameter must be the raw JWT string (the same token obtained from the Keycloak OIDC flow). Do not prefix it with `Bearer`.

The public endpoint does not require a token. Providing one is accepted but has no effect on access control.

**Token validation:**
- Tokens are validated against Keycloak's JWKS endpoint (RS256)
- The token's `realm_access.roles` claim is checked for the required role
- Expired tokens are rejected with close code 4001

### WebSocket Close Codes

The server closes the WebSocket before the message loop begins if authentication or authorization fails.

| Code | Meaning |
|------|---------|
| `4001` | Missing or invalid authentication token (includes expired tokens) |
| `4003` | Insufficient permissions — token is valid but the role does not match the required role for this endpoint |

After receiving a close code, the client should not attempt to send messages. For 4001, redirect to the login flow. For 4003, the user's session has an unexpected role.

### Message Format

#### Client to Server

Send one message object per turn. The WebSocket connection stays open; send a new message after the server signals `done`.

```json
{"type": "message", "content": "What documents do I need for a mortgage application?"}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"message"` |
| `content` | string | Yes | The user's message text (must not be empty) |

Sending a message with a missing or empty `content`, or with a `type` other than `"message"`, results in an `error` response. The connection remains open.

#### Server to Client

The server streams the response as a sequence of events terminated by `done` or `error`.

**Token (streaming chunk):**

```json
{"type": "token", "content": "To apply for a mortgage..."}
```

Tokens arrive in order and should be concatenated to assemble the full response. Token boundaries are arbitrary — do not assume they align with words or sentences.

**Done (end of response):**

```json
{"type": "done"}
```

Signals that the current response is complete. The connection stays open. The client may send the next message.

**Error:**

```json
{"type": "error", "content": "Our chat assistant is temporarily unavailable. Please try again later."}
```

Errors caused by invalid client messages (malformed JSON, wrong `type`) keep the connection open. Errors caused by agent failures also keep the connection open, though a retry may be warranted. In both cases, `done` is not sent — `error` replaces it as the terminal event for that turn.

**Safety override:**

```json
{"type": "safety_override", "content": "I can only assist with mortgage-related questions."}
```

Sent when the output safety shield replaces the agent's response. The `content` is the safe replacement text and should be rendered in place of any tokens already received for that turn. After a `safety_override`, the server sends `done` to close the turn normally.

### Typical Message Sequence

Normal interaction:

```
Client                              Server
  |                                   |
  |-- {"type":"message","content":"?"}|
  |                                   |-- {"type":"token","content":"Sure"}
  |                                   |-- {"type":"token","content":", here"}
  |                                   |-- {"type":"token","content":" are..."}
  |                                   |-- {"type":"done"}
  |                                   |
  |-- {"type":"message","content":"?"}|
  |                                   |-- {"type":"token","content":"..."}
  |                                   |-- {"type":"done"}
```

When the output safety shield fires:

```
Client                              Server
  |                                   |
  |-- {"type":"message","content":"?"}|
  |                                   |-- {"type":"safety_override","content":"..."}
  |                                   |-- {"type":"done"}
```

### PII Masking

The CEO role has PII masking enabled at the data scope level. All WebSocket messages sent to CEO connections — including `token`, `error`, and `safety_override` payloads — are automatically masked before transmission. Names, SSNs, phone numbers, email addresses, and other PII fields are replaced with redacted placeholders.

No other role has PII masking enabled. The masking is server-side and transparent to the client.

### Conversation History (REST)

Authenticated personas can retrieve prior conversation messages via a REST endpoint. Use this to render existing history when the chat panel first opens.

| Endpoint | Required Role |
|----------|---------------|
| `GET /api/borrower/conversations/history` | borrower, admin |
| `GET /api/loan-officer/conversations/history` | loan_officer, admin |
| `GET /api/underwriter/conversations/history` | underwriter, admin |
| `GET /api/ceo/conversations/history` | ceo, admin |

Authentication uses the standard `Authorization: Bearer <jwt>` header (not the query parameter used for WebSocket).

**Response schema:**

```json
{
  "data": [
    {"role": "human", "content": "What is my application status?"},
    {"role": "ai", "content": "Your application is currently under review..."}
  ]
}
```

The history is scoped to the authenticated user. Each user's history is stored under a deterministic thread ID so reconnecting to the WebSocket resumes the same conversation.

The public chat endpoint (`/api/chat`) does not have a history endpoint — public sessions are ephemeral.

### Development Mode

When the API is started with `AUTH_DISABLED=true`, all WebSocket endpoints bypass JWT validation and return a dev user with the matching role. The `?token` parameter is ignored.

For HTTP endpoints in dev mode, the role can be overridden with the `X-Dev-Role` header (e.g., `X-Dev-Role: borrower`). This header has no effect on WebSocket connections — the role is determined by which endpoint is connected to.

## Common HTTP Headers

### Request Headers

| Header | Purpose | Example |
|--------|---------|---------|
| `Authorization` | JWT Bearer token for authenticated endpoints | `Bearer eyJhbGciOiJSUzI1NiIsInR5...` |
| `Content-Type` | Request body format (for POST/PATCH) | `application/json` |
| `Accept` | Response format preference | `application/json`, `text/csv` |
| `X-Dev-Role` | Role override in dev mode (HTTP only) | `borrower`, `loan_officer` |

### Response Headers

| Header | Purpose | Example |
|--------|---------|---------|
| `Content-Type` | Response body format | `application/json` |
| `Content-Disposition` | File download name | `attachment; filename="audit.csv"` |
| `Location` | New resource URI (201 responses) | `/api/applications/42` |

## Field Naming Conventions

All JSON fields use `snake_case` (e.g., `first_name`, `application_id`, `created_at`). This follows Pydantic's default naming convention and avoids alias boilerplate.

URLs use kebab-case for multi-word paths (e.g., `/api/analytics/denial-trends`, `/api/applications/{id}/rate-lock`).

## Further Reference

For complete schema definitions, validation rules, and request examples, visit the auto-generated API documentation:

- **Swagger UI:** `http://localhost:8000/docs` (interactive, allows testing endpoints directly)
- **ReDoc:** `http://localhost:8000/redoc` (read-only, cleaner presentation)
- **OpenAPI JSON:** `http://localhost:8000/openapi.json` (machine-readable schema)

The interactive Swagger UI is the authoritative reference for detailed request/response schemas and validation constraints.
