# API Design Review -- Pre-Phase 3

**Reviewer:** API Designer
**Date:** 2026-02-26
**Scope:** All REST + WebSocket endpoints, Pydantic schemas, response envelopes, error format, naming conventions
**Reference:** `plans/interface-contracts-phase-1.md`, `.claude/rules/api-conventions.md`, `.claude/rules/error-handling.md`

---

## API-01: No RFC 7807 error responses anywhere

**Severity:** Critical
**Location:** All route files (`packages/api/src/routes/*.py`)
**Description:** The project rule `.claude/rules/error-handling.md` mandates RFC 7807 Problem Details for all API error responses (`type`, `title`, `status`, `detail`). The interface contract in `plans/interface-contracts-phase-1.md` also specifies an `ErrorResponse` model with `error`, `detail`, and `request_id` fields. Neither format is implemented. Every endpoint uses bare `HTTPException(status_code=..., detail="...")`, which produces FastAPI's default `{"detail": "..."}` body. This means:
- No `type` URI for programmatic error classification
- No `title` field
- No `status` field in the body (only in the HTTP status line)
- No `request_id` for trace correlation
- No `ErrorResponse` Pydantic model exists anywhere in the codebase
**Recommendation:** Implement a global exception handler that converts `HTTPException` (and any custom domain exceptions) into RFC 7807 responses. Define an `ErrorResponse` schema and register it as the default error response in the OpenAPI spec via `app = FastAPI(responses={...})`.

---

## API-02: JSON field naming uses snake_case instead of camelCase

**Severity:** Warning
**Location:** All schema files (`packages/api/src/schemas/*.py`)
**Description:** The project convention in `.claude/rules/api-conventions.md` states: "Use camelCase for JSON field names: `firstName`, not `first_name`." Every Pydantic model in the project uses snake_case for field names (`gross_annual_income`, `loan_term_years`, `application_id`, `ssn_encrypted`, `doc_type`, `created_at`, etc.). This contradicts the documented convention.
**Recommendation:** Either update all Pydantic models to use `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)` to produce camelCase in JSON responses while keeping snake_case in Python, or update the `api-conventions.md` rule to codify snake_case as the project standard. The latter is more pragmatic given how deeply snake_case is embedded across 50+ fields in 13 schema files. Whichever direction is chosen, the code and the rule must agree.

---

## API-03: Inconsistent response envelope -- some endpoints return raw dicts

**Severity:** Warning
**Location:** `packages/api/src/routes/applications.py:240`, `packages/api/src/routes/borrower_chat.py:79`, `packages/api/src/routes/documents.py:192`
**Description:** The `api-conventions.md` rule mandates a consistent response envelope: `{"data": {...}}` for single resources and `{"data": [...], "pagination": {...}}` for collections. Three endpoints return ad-hoc dict shapes with no `response_model`:
- `POST /api/applications/{id}/conditions/{cid}/respond` returns `{"data": result}` but has no typed `response_model`, so the OpenAPI spec has no schema for this endpoint's response.
- `GET /api/borrower/conversations/history` returns `{"data": messages}` with no typed `response_model`.
- `GET /api/documents/{id}/content` returns `{"file_path": file_path}` -- no envelope, no typed response.
**Recommendation:** Define Pydantic response models for all three endpoints. The condition response and conversation history endpoints should use the `data` envelope. The document content endpoint should either use `{"data": {"file_path": "..."}}` or a dedicated `DocumentContentResponse` schema.

---

## API-04: List endpoints use `count` instead of `pagination` object

**Severity:** Warning
**Location:** `packages/api/src/schemas/application.py:63-65`, `packages/api/src/schemas/document.py:46-50`, `packages/api/src/schemas/condition.py:19-23`, `packages/api/src/schemas/admin.py:19-24`
**Description:** The `api-conventions.md` rule specifies that collection responses should include a `pagination` object (`{"data": [...], "pagination": {"nextCursor": "...", "hasMore": true}}`). All list endpoints instead use a flat `count` field alongside `data`. There is no `hasMore` flag, no `nextCursor` or `nextOffset`, and no indication to the client whether more pages exist. The offset/limit query parameters are accepted but the response provides no information about pagination state.
**Recommendation:** Add a `Pagination` schema (with at minimum `total`, `offset`, `limit`, `has_more`) and include it in all list response models. This is necessary for any frontend to implement pagination correctly. Example:
```python
class Pagination(BaseModel):
    total: int
    offset: int
    limit: int
    has_more: bool

class ApplicationListResponse(BaseModel):
    data: list[ApplicationResponse]
    pagination: Pagination
```

---

## API-05: Public products endpoint returns bare list, not envelope

**Severity:** Warning
**Location:** `packages/api/src/routes/public.py:14`
**Description:** `GET /api/public/products` returns `list[ProductInfo]` -- a raw JSON array. The `api-conventions.md` rule requires collection responses to use the `{"data": [...]}` envelope. Raw arrays also prevent adding metadata (count, pagination, cache headers hint) without a breaking change.
**Recommendation:** Wrap in a response model: `ProductListResponse(data=list[ProductInfo], count=int)`.

---

## API-06: Health endpoint returns bare list, not envelope

**Severity:** Info
**Location:** `packages/api/src/routes/health.py:24`
**Description:** `GET /health` returns `list[HealthResponse]` -- a raw JSON array. While health endpoints are often exempt from API conventions, this is inconsistent with the envelope pattern used elsewhere. More importantly, the interface contract specifies the response as `HealthResponse` (singular), but the implementation returns a list.
**Recommendation:** Either update the interface contract to document the list return, or restructure the health response to return a single object with a `services` array inside it (e.g., `{"status": "healthy", "services": [...]}`).

---

## API-07: Document routes have inconsistent URL nesting

**Severity:** Warning
**Location:** `packages/api/src/routes/documents.py`, `packages/api/src/main.py:55`
**Description:** Document routes are registered under `prefix="/api"` (not `/api/documents`), which means the actual paths are:
- `POST /api/applications/{application_id}/documents` -- nested under applications
- `GET /api/applications/{application_id}/documents` -- nested under applications
- `GET /api/documents/{document_id}` -- top-level documents
- `GET /api/documents/{document_id}/content` -- top-level documents
- `GET /api/applications/{application_id}/completeness` -- nested under applications

This mixes two resource hierarchies in the same router. The single-document endpoints (`/api/documents/{id}`, `/api/documents/{id}/content`) break the nesting pattern established by the list/upload endpoints (`/api/applications/{id}/documents`). Clients must track two different base URLs for the same resource type.
**Recommendation:** Choose one strategy: either all document endpoints are nested under `/api/applications/{application_id}/documents` (with `GET /api/applications/{application_id}/documents/{document_id}` for single fetch), or promote documents to a top-level resource at `/api/documents` for all operations. The former is more consistent with the current design. `completeness` should be a sub-resource of the applications router, not the documents router.

---

## API-08: Verb in URL path -- `calculate-affordability` and `collect`

**Severity:** Warning
**Location:** `packages/api/src/routes/public.py:20`, `packages/api/src/routes/hmda.py:16`
**Description:** The `api-conventions.md` rule states: "URLs represent resources (nouns), not actions (verbs): `/users`, not `/getUsers`." Two endpoints use verbs in their paths:
- `POST /api/public/calculate-affordability` -- verb "calculate"
- `POST /api/hmda/collect` -- verb "collect"
**Recommendation:** Rename to noun-based resource paths:
- `POST /api/public/affordability-estimates` (or `/api/public/affordability-calculations`)
- `POST /api/hmda/demographics` (the resource being created is a demographics record)

---

## API-09: No `Location` header on 201 responses

**Severity:** Info
**Location:** `packages/api/src/routes/applications.py:243-246`, `packages/api/src/routes/documents.py:49-52`, `packages/api/src/routes/applications.py:306-309`, `packages/api/src/routes/hmda.py:16-19`
**Description:** The `api-conventions.md` rule states: "POST returns 201 with `Location` header pointing to the new resource." None of the four 201-returning endpoints include a `Location` header in the response.
**Recommendation:** Use `Response` parameter and set `response.headers["Location"]` to the URL of the created resource (e.g., `/api/applications/{id}`, `/api/applications/{id}/documents/{doc_id}`).

---

## API-10: DELETE on borrower returns 200 with full application body instead of 204

**Severity:** Info
**Location:** `packages/api/src/routes/applications.py:361-419`
**Description:** The `api-conventions.md` rule states: "DELETE returns 204 with no body." The `DELETE /api/applications/{application_id}/borrowers/{borrower_id}` endpoint returns 200 with the full `ApplicationResponse`. While returning the updated parent resource after a sub-resource deletion is a valid design choice, it contradicts the documented convention.
**Recommendation:** Either update the convention to document that DELETE on junction resources returns the parent, or change this endpoint to return 204 with no body (the client can re-fetch if needed).

---

## API-11: No API versioning prefix

**Severity:** Info
**Location:** `packages/api/src/main.py:50-57`
**Description:** The `api-conventions.md` rule specifies URL path versioning: `/v1/users`, `/v2/users`. The current API has no version prefix -- routes are at `/api/public/...`, `/api/applications/...`, etc. This means introducing a breaking change later requires either a disruptive migration or a retroactive versioning scheme.
**Recommendation:** Introduce `/api/v1/` as the prefix now, while the API surface is still small. This is a straightforward change: update `prefix` in `main.py` from `/api/applications` to `/api/v1/applications`, etc.

---

## API-12: `POST /api/admin/seed` returns 200 instead of 201 on resource creation

**Severity:** Info
**Location:** `packages/api/src/routes/admin.py:23-26`
**Description:** The seed endpoint creates demo data (borrowers, applications, loans, HMDA demographics). The `status_code` is explicitly set to `HTTP_200_OK`. When seed data is created for the first time, 201 would be more appropriate. When re-seeded (force=true), 200 is correct. The current implementation always returns 200.
**Recommendation:** Return 201 on initial seed, 200 on force re-seed. Alternatively, keep 200 since this is an admin/dev-only idempotent operation and document the rationale.

---

## API-13: `open_only` query param on conditions endpoint uses non-standard naming

**Severity:** Info
**Location:** `packages/api/src/routes/applications.py:204`
**Description:** The `api-conventions.md` rule says to filter via query parameters like `?status=active`. The conditions endpoint uses `?open_only=true` (a boolean toggle) instead of the more conventional `?status=open`. This prevents future filtering by other statuses without adding more boolean flags.
**Recommendation:** Replace `open_only: bool` with `status: str | None = Query(default=None)` that accepts values like `open`, `cleared`, `waived`. This is more extensible and consistent with standard REST filtering patterns.

---

## API-14: Audit events endpoint uses `session_id` as required query param instead of path param

**Severity:** Info
**Location:** `packages/api/src/routes/admin.py:67`
**Description:** `GET /api/admin/audit?session_id=...` requires `session_id` as a query parameter. Since `session_id` is the primary key for this query and is mandatory, it would be more RESTful as a path parameter: `GET /api/admin/audit/sessions/{session_id}/events`. The current design makes the collection endpoint (`/audit`) unusable without a filter, suggesting it is not truly a collection endpoint but a lookup-by-key.
**Recommendation:** Restructure as `GET /api/admin/audit/sessions/{session_id}` to make the resource hierarchy explicit. Alternatively, make `session_id` optional and return paginated audit events when omitted.

---

## API-15: WebSocket message protocol lacks version field

**Severity:** Warning
**Location:** `packages/api/src/routes/_chat_handler.py`
**Description:** The WebSocket protocol defines message types (`message`, `token`, `done`, `error`, `safety_override`) but includes no protocol version field. The client sends `{"type": "message", "content": "..."}` and the server sends `{"type": "token", "content": "..."}`. If the protocol evolves (new fields, new message types, changed semantics), there is no way for client and server to negotiate or detect version mismatches. This is especially important since the frontend is explicitly documented as replaceable.
**Recommendation:** Add a `version` field to the initial WebSocket handshake or to each message envelope (e.g., `{"v": 1, "type": "message", "content": "..."}`). At minimum, document the current protocol version in the OpenAPI spec or a separate protocol spec document.

---

## API-16: WebSocket close codes are non-standard

**Severity:** Info
**Location:** `packages/api/src/routes/_chat_handler.py:50-75`
**Description:** The WebSocket authentication uses custom close codes 4001 and 4003. While the 4000-4999 range is reserved for application use per RFC 6455, the specific codes are not documented anywhere. A client connecting to these endpoints has no reference for interpreting close codes.
**Recommendation:** Document the custom close codes in the WebSocket protocol specification. Suggested documentation:
- 4001: Authentication failed (missing, invalid, or expired token)
- 4003: Authorization failed (valid token but insufficient role)

---

## API-17: `HmdaCollectionRequest` includes `application_id` in body -- redundant if URL-nested

**Severity:** Info
**Location:** `packages/api/src/schemas/hmda.py:9-10`, `packages/api/src/routes/hmda.py:16`
**Description:** The HMDA endpoint is at `POST /api/hmda/collect`, and the `application_id` is in the request body. If this endpoint were nested under applications (`POST /api/applications/{application_id}/hmda`), the `application_id` would come from the URL path and need not be in the body. The current design means `application_id` is not validated against the URL context -- any authenticated borrower can submit HMDA data for any `application_id` in the body.
**Recommendation:** Either nest the endpoint under applications to leverage path-parameter binding and existing RBAC scope checks, or add explicit authorization validation ensuring the authenticated user has access to the specified `application_id`.

---

## API-18: `AuditEventItem.timestamp` and date fields use `str` instead of `datetime`

**Severity:** Warning
**Location:** `packages/api/src/schemas/admin.py:12`, `packages/api/src/schemas/rate_lock.py:13-14`, `packages/api/src/schemas/condition.py:16`
**Description:** Several schemas use `str` for date/time fields instead of `datetime`:
- `AuditEventItem.timestamp: str`
- `RateLockResponse.lock_date: str | None`
- `RateLockResponse.expiration_date: str | None`
- `ConditionItem.created_at: str | None`
- `SeedResponse.seeded_at: str | None`
- `SeedStatusResponse.seeded_at: str | None`

Using `str` means there is no format validation or consistent serialization. Clients receive whatever format the Python code produces, which may vary. Pydantic serializes `datetime` to ISO 8601 by default, which is the standard for JSON APIs.
**Recommendation:** Change all date/time fields to `datetime` type. This ensures ISO 8601 serialization and enables Pydantic validation of incoming date values.

---

## API-19: `AuditEventItem.event_data` typed as `dict | str | None` -- overly permissive

**Severity:** Info
**Location:** `packages/api/src/schemas/admin.py:16`
**Description:** The `event_data` field accepts both `dict` and `str`, meaning the client must handle two different types for the same field. This makes client-side parsing unreliable and the OpenAPI spec ambiguous (union of object and string).
**Recommendation:** Standardize on `dict | None`. If some audit events store string data, wrap it in a dict (e.g., `{"value": "the string"}`).

---

## API-20: `GET /api/documents/{document_id}` returns union type `DocumentResponse | DocumentDetailResponse`

**Severity:** Warning
**Location:** `packages/api/src/routes/documents.py:129`
**Description:** The `response_model` is `DocumentResponse | DocumentDetailResponse`. This means the OpenAPI spec generates a `oneOf` schema where the response shape changes based on the caller's role. While the RBAC-driven response is a valid business requirement, a union `response_model` makes the API contract ambiguous for clients -- they cannot know in advance which shape they will receive. OpenAPI tooling and code generators handle `oneOf` poorly.
**Recommendation:** Split into two endpoints with distinct contracts:
- `GET /api/documents/{document_id}` always returns `DocumentDetailResponse` (which includes `file_path` as nullable)
- Keep the role-based masking server-side by setting `file_path = None` for CEO rather than switching response types
This gives clients a single, predictable schema while still enforcing the business rule.

---

## API-21: `POST /api/admin/seed` takes `force` as a bare query parameter without explicit `Query`

**Severity:** Info
**Location:** `packages/api/src/routes/admin.py:31`
**Description:** The `force` parameter is defined as `force: bool = False` without `Query()` wrapper. While FastAPI infers query parameters from non-path, non-body parameters, using explicit `Query(default=False, description="Re-seed even if data already exists")` improves OpenAPI documentation and makes the intent clear to readers.
**Recommendation:** Add explicit `Query()` with description for self-documenting OpenAPI spec.

---

## API-22: No OpenAPI tags descriptions or grouping documentation

**Severity:** Info
**Location:** `packages/api/src/main.py:33-37`
**Description:** The `FastAPI()` app defines tags via `include_router(..., tags=[...])` but provides no tag descriptions or metadata. The OpenAPI spec will list tag groups ("health", "public", "applications", "chat", "documents", "hmda", "admin") without any explanation of their purpose. Since the frontend is explicitly documented as replaceable, the OpenAPI spec is a key integration contract.
**Recommendation:** Add `openapi_tags` metadata to the FastAPI app:
```python
tags_metadata = [
    {"name": "health", "description": "Health check endpoints"},
    {"name": "public", "description": "Public endpoints (no auth required)"},
    {"name": "applications", "description": "Mortgage application CRUD"},
    ...
]
app = FastAPI(..., openapi_tags=tags_metadata)
```

---

## API-23: Conversation history endpoint is under chat router but uses GET -- REST mismatch

**Severity:** Warning
**Location:** `packages/api/src/routes/borrower_chat.py:67-79`
**Description:** `GET /api/borrower/conversations/history` is in the borrower_chat router (tagged "chat") alongside the WebSocket endpoint. The URL path `/borrower/conversations/history` is resource-oriented but oddly structured -- `history` is redundant when the resource is `conversations`. The conventional REST path would be `GET /api/borrower/conversations` (list conversations) or `GET /api/conversations/{thread_id}/messages` (list messages in a conversation).

Additionally, this endpoint returns `dict` with no `response_model`, so the OpenAPI spec has no response schema.
**Recommendation:** Rename to `GET /api/conversations/history` or `GET /api/borrower/conversations` with a typed response model. Define a `ConversationHistoryResponse` schema.

---

## API-24: Interface contract divergence -- multiple Phase 2 endpoints not in Phase 1 contract

**Severity:** Info
**Location:** `plans/interface-contracts-phase-1.md` vs. actual routes
**Description:** The Phase 1 interface contract defines 6 routes. The actual API has grown significantly through Phase 2 with no updated interface contract:
- Application CRUD (GET/POST/PATCH, borrower management, conditions, rate-lock, status)
- Document upload/list/get/content/completeness
- Borrower chat WebSocket + conversation history
- Audit events + chain verification

This is expected growth, but the absence of an updated contract means there is no single document describing the full API surface. The OpenAPI spec auto-generated by FastAPI serves this purpose partially, but it lacks the auth requirements, role restrictions, and data scope rules that the Phase 1 contract documented.
**Recommendation:** Create `plans/interface-contracts-phase-2.md` (or a combined `interface-contracts.md`) documenting all current routes with their auth requirements, role restrictions, and request/response shapes. This is especially important given that Phase 3 (Loan Officer) will add more endpoints and the frontend is replaceable.
