# API Design Review -- Pre-Phase 5

**Reviewer:** api-designer
**Date:** 2026-02-27
**Scope:** All REST and WebSocket endpoints in `packages/api/src/routes/` and `packages/api/src/schemas/`

## Findings

### [AD-01] Severity: Warning
**File(s):** `packages/api/src/routes/applications.py:451-509`
**Finding:** The `DELETE /api/applications/{application_id}/borrowers/{borrower_id}` endpoint returns `200` with a full `ApplicationResponse` body. The project's own `api-conventions.md` states: "DELETE returns 204 with no body." Additionally, this is not a resource deletion in the traditional sense (it unlinks a borrower from an application), and the caller receives the refreshed parent application. This deviates from the convention and creates an inconsistency that a replacement frontend would need to know about.
**Recommendation:** Either change the status code to `204` with no response body (matching convention), or if the use case genuinely requires the updated application back, change the HTTP method to `POST /api/applications/{id}/borrowers/{borrower_id}/remove` to make it a command rather than a REST delete. If keeping `DELETE` with a body, at minimum set `status_code=200` explicitly in the decorator for clarity and document the deviation.

---

### [AD-02] Severity: Warning
**File(s):** `packages/api/src/routes/borrower_chat.py:69-81`, `packages/api/src/routes/loan_officer_chat.py:69-81`, `packages/api/src/routes/underwriter_chat.py:69-81`
**Finding:** The conversation history endpoints (`GET /api/borrower/conversations/history`, `GET /api/loan-officer/conversations/history`, `GET /api/underwriter/conversations/history`) declare a return type of `-> dict` and return a raw `{"data": messages}` dictionary. This means:
1. No `response_model` is declared, so OpenAPI docs show no response schema for these three endpoints. For a project where the frontend is explicitly stated to be replaceable and the "OpenAPI spec is the contract," this is a gap.
2. The response shape is not validated by Pydantic; if the `messages` structure changes, the API will silently return unexpected shapes.
3. The `messages` list content type is unspecified -- consumers cannot know what fields each message contains.
**Recommendation:** Define a `ConversationHistoryResponse` Pydantic model (e.g., `data: list[ConversationMessage]` with role, content, timestamp fields) and set it as `response_model` on all three endpoints.

---

### [AD-03] Severity: Warning
**File(s):** `packages/api/src/routes/public.py:14`
**Finding:** `GET /api/public/products` returns `list[ProductInfo]` directly -- a bare array, not wrapped in the `{"data": [...], "pagination": {...}}` envelope that `api-conventions.md` mandates for collections. This is the only list endpoint in the API that skips the envelope. While the product list is small and static, the inconsistency means consumers must special-case this endpoint.
**Recommendation:** Wrap in the standard envelope: `{"data": [...], "pagination": {"total": N, "offset": 0, "limit": N, "has_more": false}}`. Create a `ProductListResponse` schema for this.

---

### [AD-04] Severity: Warning
**File(s):** `packages/api/src/routes/public.py:20`
**Finding:** `POST /api/public/calculate-affordability` uses a verb in the URL path. The `api-conventions.md` states: "URLs represent resources (nouns), not actions (verbs)." The endpoint is a pure computation with no side effects, which is a known REST gray area, but it could be modeled as a resource.
**Recommendation:** Rename to `POST /api/public/affordability-estimates` (creating an affordability estimate resource) or `POST /api/public/affordability-calculations`. This is a lower priority since calculators are a well-known REST exception, but it would improve consistency with the project's own stated conventions.

---

### [AD-05] Severity: Warning
**File(s):** `packages/api/src/routes/hmda.py:16`
**Finding:** `POST /api/hmda/collect` uses a verb in the URL path. The endpoint creates HMDA demographic data for an application, which is naturally modeled as a resource creation. The URL structure also does not nest under the application resource, despite the `application_id` being in the request body rather than the URL path. This means there is no URL-based way to identify which application's HMDA data is being accessed, and it breaks the nesting convention established by conditions, documents, rate-lock, and completeness.
**Recommendation:** Restructure to `POST /api/applications/{application_id}/hmda-demographics` with `application_id` as a path parameter. This makes HMDA data a sub-resource of the application, consistent with the rest of the API. The request body still carries the remaining fields.

---

### [AD-06] Severity: Warning
**File(s):** `packages/api/src/schemas/condition.py:16-17`
**Finding:** `ConditionItem.severity` and `ConditionItem.status` are typed as `str | None` instead of using the `ConditionSeverity` and `ConditionStatus` enums that exist in `db.enums`. This loses type safety in the API contract -- consumers see `"string"` in OpenAPI docs instead of an enumerated set of valid values. By contrast, `ApplicationResponse.stage` correctly uses the `ApplicationStage` enum and `DocumentResponse.status` correctly uses `DocumentStatus`.
**Recommendation:** Change the types to `ConditionSeverity | None` and `ConditionStatus | None` respectively. Also consider doing the same for `ConditionItem.issued_by` and `ConditionItem.cleared_by` if they correspond to known user ID patterns.

---

### [AD-07] Severity: Warning
**File(s):** `packages/api/src/schemas/decision.py:16-17`
**Finding:** Same issue as AD-06: `DecisionItem.decision_type` is typed as `str` instead of the `DecisionType` enum from `db.enums`. The OpenAPI spec will show `"string"` rather than the valid values (`approved`, `conditional_approval`, `suspended`, `denied`). The `DecisionItem` schema also has `ai_recommendation: str | None` and `contributing_factors: str | None` where the former could use the same `DecisionType` enum if it represents a decision recommendation.
**Recommendation:** Use `DecisionType` for `decision_type`. Evaluate whether `ai_recommendation` should also be `DecisionType | None`.

---

### [AD-08] Severity: Warning
**File(s):** `packages/api/src/schemas/error.py`, `packages/api/src/main.py:84-91`
**Finding:** The `ErrorResponse` schema omits the RFC 7807 `instance` field, which the project's own `error-handling.md` documents as expected: "Include `detail` for human-readable context and `instance` for the specific resource." The `_build_error` helper in `main.py` does not populate `instance` either. The `instance` field is meant to carry the URI of the specific resource that triggered the error, helping consumers and support engineers identify the exact resource involved.
**Recommendation:** Add `instance: str = ""` to `ErrorResponse` and populate it with `request.url.path` in the exception handlers. This is a low-cost change that improves error diagnostics.

---

### [AD-09] Severity: Warning
**File(s):** `packages/api/src/routes/applications.py:285-310`
**Finding:** `POST /api/applications/{application_id}/conditions/{condition_id}/respond` uses a verb (`respond`) in the URL path. This endpoint records a borrower's text response to a condition, which is naturally modeled as creating a response resource or updating the condition resource. The verb-based URL is inconsistent with the resource-oriented approach used elsewhere (e.g., `POST /api/applications/{id}/borrowers` for adding a borrower, not `/add-borrower`).
**Recommendation:** Restructure as `PATCH /api/applications/{application_id}/conditions/{condition_id}` with the `response_text` field in the request body (partial update to the condition), or `POST /api/applications/{application_id}/conditions/{condition_id}/responses` (creating a response sub-resource). The PATCH approach is simpler and consistent with the existing `PATCH /api/applications/{id}` pattern.

---

### [AD-10] Severity: Warning
**File(s):** `packages/api/src/routes/admin.py:62-88`
**Finding:** `GET /api/admin/audit` requires `session_id` as a mandatory query parameter (`Query(...)`) to filter audit events. This means there is no way to list all audit events -- you must always provide a specific session ID. The companion endpoint `GET /api/admin/audit/application/{application_id}` uses a path parameter for the application ID filter. The two filtering approaches are inconsistent: one uses a path parameter, the other a required query parameter. Additionally, neither endpoint supports pagination -- both return all matching events in a single response.
**Recommendation:** Standardize on one pattern. Either (a) make session_id a path parameter: `GET /api/admin/audit/session/{session_id}`, which parallels the application variant, or (b) make both session_id and application_id optional query parameters on a single `GET /api/admin/audit` endpoint with pagination support. Option (b) is more extensible and enables combined filtering.

---

### [AD-11] Severity: Warning
**File(s):** `packages/api/src/schemas/admin.py:21-26`, `packages/api/src/schemas/admin.py:29-34`
**Finding:** `AuditEventsResponse` and `AuditEventsByApplicationResponse` use a non-standard envelope with `count` + `events` fields instead of the project-wide `data` + `pagination` convention. All other list responses (`ApplicationListResponse`, `DocumentListResponse`, `ConditionListResponse`, `DecisionListResponse`) use `data` as the collection key and include a `Pagination` object. The audit endpoints break this pattern, making them inconsistent for consumers who expect the standard envelope.
**Recommendation:** Rename `events` to `data`, replace `count` with a `Pagination` object, and add offset/limit query parameters to the audit endpoints. If backward compatibility is a concern, do this alongside adding pagination (AD-10) since both changes affect the same response shape.

---

### [AD-12] Severity: Warning
**File(s):** `packages/api/src/routes/applications.py:247-282`
**Finding:** `GET /api/applications/{application_id}/conditions` returns all conditions in a single response and constructs a `Pagination` object with `total=len(result), offset=0, limit=len(result), has_more=False`. This is "fake" pagination -- the endpoint always returns all conditions and the pagination metadata is cosmetic. The service function `get_conditions` does not accept offset/limit parameters. For applications with many conditions (iterative conditions clearing is a key Phase 4 feature), this could return large payloads.
**Recommendation:** Add real offset/limit query parameters to the endpoint and pass them through to the service layer, matching the pagination pattern used by `list_applications` and `list_documents`.

---

### [AD-13] Severity: Suggestion
**File(s):** `packages/api/src/routes/applications.py:106`
**Finding:** The sort parameter is named `sort_by` with a `Literal` type listing specific allowed values. The `api-conventions.md` specifies a `sort` parameter with prefix-based direction: `?sort=createdAt` (ascending), `?sort=-createdAt` (descending). The current implementation does not support sort direction (always ascending for `updated_at` and `loan_amount`, custom for `urgency`) and uses a different parameter name.
**Recommendation:** Rename to `sort` and support the `-` prefix for descending order (e.g., `?sort=-updated_at`). Parse the prefix in the route handler and pass direction to the service layer. This aligns with the project convention and gives consumers control over sort direction.

---

### [AD-14] Severity: Suggestion
**File(s):** `packages/api/src/routes/applications.py:107-108`
**Finding:** Filter parameters use a `filter_` prefix (`filter_stage`, `filter_stalled`). The `api-conventions.md` convention is: "Filter via query parameters: `?status=active&role=admin`" -- no prefix. The `filter_` prefix is redundant since query parameters on collection endpoints are inherently filters. It also creates an inconsistency with `open_only` on the conditions endpoint (line 265), which does not use the `filter_` prefix.
**Recommendation:** Rename to `stage` and `stalled` (or `is_stalled`) for consistency with the convention. If there is a concern about parameter name collisions with other query parameters, document the naming decision.

---

### [AD-15] Severity: Suggestion
**File(s):** `packages/api/src/main.py:130`, `packages/api/src/routes/documents.py:57-58`
**Finding:** The `documents` router is registered with `prefix="/api"` and tags `["documents"]`, and the route paths include the full `/applications/{application_id}/documents` prefix. This means document endpoints live under `/api/applications/{application_id}/documents/...` but are registered on a separate router from the `applications` router (which has `prefix="/api/applications"`). This split is fine architecturally, but it means the OpenAPI tags show "documents" and "applications" as separate groups when conditions, rate-lock, status, and borrowers -- which are also application sub-resources -- live under the "applications" tag. The tagging is inconsistent for sub-resources of the same parent.
**Recommendation:** Either tag all application sub-resource endpoints consistently (e.g., keep them all under "applications" or split them all into their own tag groups: "conditions", "rate-lock", "documents"), or add sub-tags. The most readable approach for the OpenAPI consumer is to keep documents under "applications" (or "application-documents") since they are sub-resources.

---

### [AD-16] Severity: Suggestion
**File(s):** `packages/api/src/routes/applications.py:313-316`, `packages/api/src/routes/applications.py:396-399`, `packages/api/src/routes/documents.py:57-60`, `packages/api/src/routes/hmda.py:16-19`
**Finding:** The `api-conventions.md` states: "POST returns 201 with `Location` header pointing to the new resource." All four POST-create endpoints correctly return `status_code=201` but none include a `Location` header in the response. This means consumers cannot discover the URL of the newly created resource from the response headers.
**Recommendation:** Add a `Location` header to all POST-create responses. For example, `create_application` should return `Location: /api/applications/{new_id}`. This can be done with a `Response` parameter in the handler: `response.headers["Location"] = f"/api/applications/{app.id}"`.

---

### [AD-17] Severity: Suggestion
**File(s):** `packages/api/src/routes/applications.py:164-165`, `packages/api/src/routes/documents.py:64`, `packages/api/src/routes/admin.py:97`
**Finding:** All path parameters that accept resource IDs use `int` type (`application_id: int`, `document_id: int`, `condition_id: int`, `borrower_id: int`). While the database uses integer primary keys, there are no constraints on the path parameters (e.g., `gt=0`) to reject obviously invalid values like `0` or negative numbers before hitting the database. This is a minor validation gap -- the database would return 404 anyway, but rejecting bad input early with a clear 422 is better API hygiene.
**Recommendation:** Add `Path(gt=0)` constraints to all integer path parameters, e.g., `application_id: int = Path(gt=0)`.

---

### [AD-18] Severity: Suggestion
**File(s):** `packages/api/src/routes/applications.py:172-175`, `packages/api/src/routes/applications.py:202-206`, `packages/api/src/routes/applications.py:240-244`, `packages/api/src/routes/documents.py:99-102`, `packages/api/src/routes/documents.py:162-165`, `packages/api/src/routes/documents.py:185-188`, `packages/api/src/routes/documents.py:206-209`
**Finding:** Multiple endpoints raise `HTTPException` with bare string `detail` messages (e.g., `detail="Application not found"`, `detail="Document not found"`). While the global exception handler wraps these into RFC 7807 format, the `detail` messages are generic and do not include the resource identifier that was not found. For example, "Application not found" does not tell the consumer which application ID was requested. This makes debugging harder, especially for automated consumers.
**Recommendation:** Include the resource identifier in the detail message, e.g., `detail=f"Application {application_id} not found"`, `detail=f"Document {document_id} not found"`. This is low-cost and significantly improves the diagnostic value of error responses.

---

### [AD-19] Severity: Suggestion
**File(s):** `packages/api/src/routes/_chat_handler.py:140-148`
**Finding:** WebSocket error messages for invalid client input use a bare JSON structure `{"type": "error", "content": "..."}` that does not follow any documented protocol schema. The initial WebSocket protocol is documented in `chat.py` docstring (lines 5-9), but there is no Pydantic model defining the WebSocket message types. For a project where the frontend is replaceable and the API contract is the integration boundary, the WebSocket message protocol should be as formally specified as the REST endpoints.
**Recommendation:** Define Pydantic models for WebSocket messages (e.g., `ChatMessage`, `ChatToken`, `ChatError`, `ChatDone`) and document them in a shared location. This does not need to change runtime behavior -- FastAPI WebSocket does not validate messages -- but the models serve as contract documentation for replacement frontends.

---

### [AD-20] Severity: Suggestion
**File(s):** `packages/api/src/main.py:138-141`
**Finding:** The root endpoint `GET /` returns `{"message": "Welcome to Summit Cap Financial API"}` with no `response_model`. This means the OpenAPI spec shows no schema for the root response. While this is a trivial endpoint, it is the first thing an API consumer sees.
**Recommendation:** Add a `response_model` with a simple schema (e.g., `RootResponse` with `message: str` and optionally `version: str`, `docs_url: str`).

---

### [AD-21] Severity: Suggestion
**File(s):** `packages/api/src/schemas/health.py:14`
**Finding:** `HealthResponse.start_time` is typed as `str | None` rather than `datetime | None`. Since `API_START_TIME` is a `datetime` object (line 19 of `health.py` route), it is converted to a string via `.isoformat()` before being passed to the schema. Using a `datetime` type would leverage Pydantic's built-in ISO 8601 serialization and provide a proper `date-time` format in the OpenAPI spec instead of a generic `string`.
**Recommendation:** Change `start_time: str | None` to `start_time: datetime | None` and pass the `datetime` object directly instead of calling `.isoformat()`.

---

### [AD-22] Severity: Suggestion
**File(s):** `packages/api/src/schemas/hmda.py:33`
**Finding:** `HmdaCollectionResponse.conflicts` is typed as `list[dict] | None`. The use of untyped `dict` means the OpenAPI spec cannot describe what each conflict object contains. Consumers must guess the structure or read source code.
**Recommendation:** Define a `HmdaConflict` Pydantic model with explicit fields (e.g., `field: str`, `existing_value: str`, `new_value: str`, `resolution: str`) and type `conflicts` as `list[HmdaConflict] | None`.

---

### [AD-23] Severity: Suggestion
**File(s):** `packages/api/src/schemas/admin.py:18`
**Finding:** `AuditEventItem.event_data` is typed as `dict | str | None`. The union of `dict` and `str` is unusual and suggests the data can come back in different shapes depending on the event type. This makes it difficult for consumers to parse reliably and produces an imprecise OpenAPI schema.
**Recommendation:** Standardize `event_data` to always be `dict | None`. If some audit events store string data, wrap it in a dict (e.g., `{"message": "string value"}`). This simplifies consumer parsing.

---

### [AD-24] Severity: Suggestion
**File(s):** `packages/api/src/main.py:123`
**Finding:** The health check endpoint is mounted at `/health` (no `/api` prefix), while all other endpoints are under `/api/...`. This is a deliberate choice (health checks are often outside the API namespace for load balancer probes), but it is not documented anywhere in the OpenAPI description or the API conventions doc. A replacement frontend team might not know to look for health at a different prefix.
**Recommendation:** Add a note to the FastAPI description field or a separate "operational endpoints" tag documenting that `/health` lives outside the `/api` prefix. No code change needed -- just documentation.

---

### [AD-25] Severity: Critical
**File(s):** `packages/api/src/schemas/decision.py` (schema exists, no route file)
**Finding:** `DecisionItem`, `DecisionResponse`, and `DecisionListResponse` schemas are defined but there are no REST route endpoints exposing decisions. The `get_decisions` service function exists (`packages/api/src/services/decision.py:351`) but is only called from agent tools, not from any REST handler. This means:
1. The frontend has no way to list or retrieve underwriting decisions via REST.
2. The `decision.py` schema defines a `Pagination` import and `DecisionListResponse` that are never used.
3. Phase 5 (Executive) will need decision data for the CEO dashboard, but there is no REST surface to fetch it.

This is critical because the frontend is explicitly stated to be replaceable and must not contain business logic -- it needs a REST API to read decisions.
**Recommendation:** Add REST endpoints for decisions before Phase 5:
- `GET /api/applications/{application_id}/decisions` -- list decisions (paginated)
- `GET /api/applications/{application_id}/decisions/{decision_id}` -- get single decision
These should be read-only (decision creation happens through the underwriter agent, not REST). Apply RBAC to restrict CEO to aggregate/masked views if needed per the data scope rules.
