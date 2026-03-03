# API Design Review -- Pre-UI

**Reviewer:** API Designer
**Scope:** `packages/api/src/routes/`, `packages/api/src/schemas/`
**Focus:** REST conventions, response consistency, pagination, error format, OpenAPI spec completeness, query parameter design, WebSocket protocol, frontend discoverability

---

## Critical

### AD-01: `audit/export` endpoint missing `response_model` -- breaks OpenAPI contract

**File:** `packages/api/src/routes/audit.py:163`

The `audit_export` endpoint returns a `fastapi.responses.Response` directly and has no `response_model` declared. FastAPI cannot generate a schema for this endpoint in the OpenAPI spec, so frontend developers see no contract for what the response body looks like (or that it is binary/CSV). This is the only endpoint in the codebase without any response schema.

**Suggested fix:** Add `responses` metadata so OpenAPI documents both formats:

```python
@router.get(
    "/export",
    responses={
        200: {
            "description": "Audit trail export",
            "content": {
                "application/json": {"schema": {"type": "string"}},
                "text/csv": {"schema": {"type": "string"}},
            },
        }
    },
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.CEO, UserRole.UNDERWRITER))],
)
```

---

### AD-02: `POST /api/admin/seed` accepts query parameter `force` instead of a request body

**File:** `packages/api/src/routes/admin.py:16-38`

`force: bool = False` is declared as a plain function parameter on a `POST` handler, which FastAPI resolves as a **query parameter** (`?force=true`). Per `api-conventions.md`, GET and DELETE use query parameters; POST receives state-changing inputs in the request body. A seed endpoint with a boolean control flag should use a body schema. Frontend code that passes `force` as a query param on a POST is unusual and easy to miss, especially when generated from OpenAPI clients.

**Suggested fix:**

```python
class SeedRequest(BaseModel):
    force: bool = False

@router.post("/seed", ...)
async def seed_data(body: SeedRequest, ...) -> SeedResponse:
```

---

### AD-03: `GET /health/` returns a bare array, not a standard envelope

**File:** `packages/api/src/routes/health.py:24-44`

The health endpoint `response_model=list[HealthResponse]` returns a JSON array at the top level. Every other collection endpoint in the codebase uses `{"data": [...], "pagination": {...}}`. A bare array breaks the frontend's uniform response-parsing contract and prevents the standard data-extraction path from working without a special case.

The health endpoint is a legitimate exception in many APIs, but here it is served under `/health/` without any documented exception. The deferred item W-29 covers the products endpoint returning a bare array; the same pattern applies here and was not deferred.

**Suggested fix:** Wrap in a consistent envelope or explicitly document this as an intentional deviation in the OpenAPI description so frontend developers know not to apply the standard envelope unwrap.

---

## Warning

### AD-04: `RateLockResponse` uses `str` literal for `status` instead of an enum

**File:** `packages/api/src/schemas/rate_lock.py:12`

`status: str  # "active", "expired", "none"` is documented only in a comment. Frontend developers cannot derive a TypeScript union type from a comment; they must read the source or the comment may go stale. `ConditionItem.status` and `ConditionItem.severity` have the same pattern (flagged as S-21, which is deferred), but `RateLockResponse.status` is a separate, independent instance not covered by S-21.

**Suggested fix:** Define a `RateLockStatus` enum and use it:

```python
class RateLockStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    none = "none"

class RateLockResponse(BaseModel):
    status: RateLockStatus
```

---

### AD-05: `DecisionTraceResponse.denial_reasons` typed as `list | dict | None`

**File:** `packages/api/src/schemas/audit.py:71`

`denial_reasons: list | dict | None = None` is an untyped union that generates an `anyOf: [array, object]` in OpenAPI. Frontend TypeScript clients have no way to know which shape to expect at runtime. `DecisionItem.denial_reasons` (in `schemas/decision.py:21`) correctly types this as `list[str] | None`. The `DecisionTraceResponse` should match.

**Suggested fix:**

```python
denial_reasons: list[str] | None = None
```

---

### AD-06: `HmdaCollectionResponse.conflicts` typed as `list[dict] | None`

**File:** `packages/api/src/schemas/hmda.py:33`

`conflicts: list[dict] | None = None` generates an untyped array-of-object schema in OpenAPI. Frontend developers cannot know what properties a conflict object contains without reading the service-layer code. This makes typed client generation impossible for this field.

**Suggested fix:** Define a `HmdaDemographicConflict` schema with concrete fields (e.g., `field`, `existing_value`, `new_value`) and use it:

```python
class HmdaDemographicConflict(BaseModel):
    field: str
    existing_value: str | None
    new_value: str | None

class HmdaCollectionResponse(BaseModel):
    ...
    conflicts: list[HmdaDemographicConflict] | None = None
```

---

### AD-07: `AuditEventItem.event_data` typed as `dict | str | None`

**File:** `packages/api/src/schemas/audit.py:19`

`event_data: dict | str | None = None` is a union of two incompatible shapes. This generates an `anyOf: [object, string]` in OpenAPI, which is not consumable by TypeScript generators. If `event_data` can genuinely be either format, it should be normalized to `dict | None` (with the service layer always producing a dict) or documented as opaque JSON.

**Suggested fix:** Normalize to `dict[str, object] | None` and enforce dict at the service boundary. If the raw string case is needed for legacy records, document it as a known deviation.

---

### AD-08: `SeedStatusResponse.summary` typed as `dict | None`

**File:** `packages/api/src/schemas/admin.py:29`

`summary: dict | None = None` generates an untyped object in OpenAPI. Even for an admin-only demo endpoint, the frontend needs to know what fields `summary` contains in order to render a meaningful status display. This is an opaque blob.

**Suggested fix:** Define a `SeedSummary` schema with the known fields (borrowers, active_applications, etc.) and use it.

---

### AD-09: `DecisionTraceResponse.events_by_type` typed as `dict[str, list]`

**File:** `packages/api/src/schemas/audit.py:73`

`events_by_type: dict[str, list]` uses an untyped inner list. The values should be `list[AuditEventItem]` so frontend clients know the shape of each grouped event.

**Suggested fix:**

```python
events_by_type: dict[str, list[AuditEventItem]] = Field(default_factory=dict)
```

---

### AD-10: `PATCH /api/applications/{id}` conflates field updates and stage transitions in one endpoint

**File:** `packages/api/src/routes/applications.py:336-399`

The `update_application` handler internally separates `stage` from other fields and routes them through different code paths (state machine vs. direct update). To a frontend developer reading the OpenAPI spec, there is no signal that setting `stage` in a PATCH body is fundamentally different from setting `loan_amount`. This leads to confusing error handling: a 422 with `InvalidTransitionError` text versus a 400 "No fields to update" for other errors.

Additionally, the handler can succeed for the stage transition but fail for field updates (or vice versa), leaving the application in a partially-updated state with no indication of which part succeeded.

**Suggested fix (preferred):** Expose stage transitions as a dedicated sub-resource: `POST /api/applications/{id}/stage-transitions` with `{"stage": "underwriting"}`. This makes the state-machine semantics explicit in the URL.

**Suggested fix (minimal):** Document the `stage` field behavior in the OpenAPI description so frontend developers know to expect 422 for invalid transitions, separately from other 422 validation errors.

---

### AD-11: `GET /api/applications/{id}/completeness` not nested under documents

**File:** `packages/api/src/routes/documents.py:172-189`

The completeness endpoint lives at `/api/applications/{id}/completeness` but is registered on the documents router under the `/api` prefix -- not the `/api/applications` prefix. This places it outside the applications resource hierarchy without clear ownership. Compare: decisions are at `/api/applications/{id}/decisions`, conditions are at `/api/applications/{id}/conditions`, but completeness is at `/api/applications/{id}/completeness` (correct URL) via a different mount point. The actual URL is correct but the router organization is misleading for anyone maintaining the codebase and the OpenAPI tag is "documents" rather than "applications".

**Suggested fix:** Move the completeness endpoint into the applications router so it is co-located with other application sub-resources, or document the routing decision.

---

### AD-12: WebSocket token delivery via query parameter is not documented in OpenAPI spec

**File:** `packages/api/src/routes/_chat_handler.py:51`

All authenticated WebSocket endpoints receive the JWT via `?token=<jwt>` query param. This is a common WebSocket auth pattern, but it is not reflected anywhere in the OpenAPI spec (WebSocket endpoints with query parameters are not formally described). Frontend developers have no machine-readable contract for which parameters are required, what close codes mean, or what the message protocol looks like.

The `chat.py` docstring at line 1 is the best documentation in the codebase, but it is only in the public chat file, not in the authenticated endpoints generated by `create_authenticated_chat_router`.

**Suggested fix:** Add OpenAPI-compatible documentation for the WebSocket protocol. Since OpenAPI 3.0 does not support WebSocket specs natively, use one of:
- AsyncAPI spec (preferred for WebSocket documentation)
- Extended OpenAPI descriptions on a companion REST endpoint that describes the protocol
- At minimum, ensure the docstring in `create_authenticated_chat_router`'s generated endpoint includes the full protocol (token param, message format, close codes)

---

### AD-13: `GET /api/audit/application/{application_id}` uses singular `application` while all other audit paths use plural nouns

**File:** `packages/api/src/routes/audit.py:74`

The audit router mounts at `/api/audit` with sub-paths:
- `/session` (no resource noun -- uses query param)
- `/application/{application_id}` (singular)
- `/decision/{decision_id}` (singular)
- `/search`
- `/verify`
- `/export`

Per `api-conventions.md`, collection sub-resources use plural nouns. `application` and `decision` should be `applications` and `decisions` to be consistent with the rest of the API (`/api/applications/`, `/api/applications/{id}/decisions`).

**Suggested fix:** Rename to `/applications/{application_id}` and `/decisions/{decision_id}`.

---

### AD-14: `GET /api/audit/session` accepts `session_id` as query parameter instead of path parameter

**File:** `packages/api/src/routes/audit.py:56-71`

`session_id: str = Query(...)` on a GET endpoint makes `session_id` a required query parameter. For a resource lookup by ID, the convention is a path parameter: `GET /api/audit/sessions/{session_id}`. Using a required query param for a resource identifier is unusual and breaks the REST resource model -- it cannot be bookmarked as a URL, and OpenAPI clients may not distinguish it from optional filters.

**Suggested fix:** Move `session_id` to a path parameter: `GET /api/audit/sessions/{session_id}`.

---

### AD-15: `POST /api/hmda/collect` -- "collect" is a verb in the URL path

**File:** `packages/api/src/routes/hmda.py:16`

The HMDA endpoint is mounted at `/api/hmda` with path `/collect`, resulting in `/api/hmda/collect`. Per `api-conventions.md`, URLs represent resources (nouns), not actions (verbs). The deferred item S-23 covers verb-based URLs generally, but this is a distinct instance on a different router. S-23 does not enumerate which specific endpoints are affected; if `/api/hmda/collect` was included in S-23's scope, this finding should be skipped. If not, this is a new instance.

**Suggested fix:** Use `POST /api/hmda/demographics` (the resource being created is a demographic record).

---

### AD-16: `GET /api/analytics/model-monitoring` duplicates a sub-resource already exposed at granular paths

**File:** `packages/api/src/routes/model_monitoring.py:37-47`

The summary endpoint at `/api/analytics/model-monitoring` fetches all four sub-metrics (latency, tokens, errors, routing) and returns the combined object. The granular endpoints (`/latency`, `/tokens`, `/errors`, `/routing`) each fetch the same summary internally and extract one field. This means a frontend showing only latency makes four LangFuse API calls instead of one. Conversely, a dashboard wanting all four metrics could just call the summary endpoint. The granular endpoints add no caching or independent fetch -- they are wrapper-facades over the same underlying call.

The issue for frontend integration: there are five endpoints where one (summary) suffices for most use cases. The granular endpoints will cause confusion about when to use each.

**Suggested fix:** Document in the OpenAPI descriptions which endpoint is intended for which use case (full dashboard vs. single panel). Alternatively, remove the granular sub-endpoints if they add no independent value -- the frontend can destructure fields from the summary response.

---

### AD-17: `PATCH /api/applications/{id}` returns `ApplicationResponse` (not wrapped in `data:`) but `GET` single-resource also returns unwrapped

**File:** `packages/api/src/schemas/application.py:54`
**File:** `packages/api/src/routes/applications.py:149-176`

The single-resource response convention per `api-conventions.md` is `{ "data": { ... } }`. `ApplicationResponse` is returned directly (not wrapped in a `data` key) from both `GET /api/applications/{id}` and `PATCH /api/applications/{id}`. The same applies to `DecisionResponse` (single decision) and `ConditionResponse` (single condition after respond).

Collection responses correctly use `{ "data": [...], "pagination": {...} }`. But single-resource responses skip the `data` envelope. This inconsistency means frontend code must conditionally unwrap or not depending on whether the response is a list or single item.

**Suggested fix:** Either (a) consistently wrap all single-resource responses in `{ "data": { ... } }`, or (b) explicitly document that the `data` envelope is only used for collections, so frontend developers know which convention applies where.

---

## Suggestion

### AD-18: `AuditSearchResponse` and audit-by-* responses have inconsistent envelope shapes

**File:** `packages/api/src/schemas/audit.py:22-50`

Each audit query endpoint returns a different top-level envelope:
- `AuditBySessionResponse`: `{session_id, count, events}`
- `AuditByApplicationResponse`: `{application_id, count, events}`
- `AuditByDecisionResponse`: `{decision_id, count, events}`
- `AuditSearchResponse`: `{count, events}`

None of these use the standard `{ "data": [...], "pagination": {...} }` pattern. This is noted in the deferred item S-24, but the specific inconsistency between the audit-by-* schemas (some include the filter key, some do not) is a new observation. Frontend code must handle four different response shapes for what are essentially the same kind of query. Consider a single `AuditQueryResponse` with optional context fields.

---

### AD-19: `DocumentFilePathResponse` leaks an internal storage path to the frontend

**File:** `packages/api/src/schemas/document.py:48-51`

`GET /api/applications/{id}/documents/{did}/content` returns `{"file_path": "/some/internal/minio/path"}`. This exposes an internal file system or object storage path to the frontend, which then presumably must perform another request to fetch actual content. If the frontend renders documents by constructing a MinIO URL from `file_path`, that couples the frontend to the internal storage layout.

**Suggested fix:** Either return a pre-signed URL (so the frontend can fetch the document directly without knowing storage internals) or rename `file_path` to `download_url` and return a ready-to-use URL. At minimum, document what the frontend is expected to do with this value.

---

### AD-20: `GET /api/public/products` and `POST /api/public/calculate-affordability` have no API version prefix

**File:** `packages/api/src/routes/public.py:14-23`
**File:** `packages/api/src/main.py:136`

All authenticated endpoints are under `/api/`, and there is no version prefix (`/v1/`) anywhere. This is consistent across the whole API. However, the public endpoints are particularly exposed because they are the integration point for external or unauthenticated frontends. Per `api-conventions.md`, URL versioning is the recommended strategy for major versions. If a breaking change is needed to a public endpoint, there is no versioning mechanism to maintain backward compatibility.

**Suggested fix:** Document the versioning strategy explicitly (e.g., "v1 is implicit, versioning will be added if breaking changes are needed post-MVP") so frontend developers know what to expect.

---

### AD-21: `ConversationHistoryResponse.data` field name matches list envelope convention but the schema is not paginated

**File:** `packages/api/src/schemas/conversation.py:14-19`

`ConversationHistoryResponse` uses `data: list[ConversationMessage]` which looks like the standard list envelope but has no `pagination` field. A long conversation history could return hundreds of messages with no pagination capability. Frontend developers may expect pagination to exist (given the `data` key) and be confused when it is absent. This will become a UX issue if conversation histories grow long.

**Suggested fix:** Either add pagination parameters to the history endpoints (`?limit=50&offset=0`) and the response schema, or rename the field from `data` to `messages` to avoid the false implication of a paginated envelope.

---

### AD-22: `GET /api/analytics/pipeline`, `denial-trends`, and `lo-performance` return raw objects without `data` envelope

**File:** `packages/api/src/schemas/analytics.py`
**File:** `packages/api/src/routes/analytics.py`

The analytics endpoints return their schemas directly: `PipelineSummary`, `DenialTrends`, `LOPerformanceSummary`. This is consistent among themselves but inconsistent with how collection resources are returned (`{ "data": [...] }`). Single-resource and aggregate objects not using the envelope is potentially fine, but it should be documented as the intended deviation so frontend developers do not wrap/unwrap inconsistently.

---

### AD-23: `DELETE /api/applications/{id}/borrowers/{borrower_id}` returns `ApplicationResponse` body instead of 204

**File:** `packages/api/src/routes/applications.py:456-495`

Per `api-conventions.md`, DELETE returns 204 with no body. Returning the full `ApplicationResponse` after a DELETE is non-standard and makes the endpoint behave more like a PATCH. While returning the updated resource after a sub-resource deletion is a common pattern, it should be explicitly documented and consistently applied (the `respond_condition` POST also returns the resource, which is consistent with POST-create, but DELETE should differ).

**Suggested fix:** Either adopt a consistent "return updated parent after sub-resource mutation" convention and document it, or change DELETE to return 204 and require a separate GET to refresh the application state.
