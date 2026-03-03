# Pre-Phase 5 Security Review

**Reviewer:** Security Engineer
**Date:** 2026-02-27
**Scope:** Full `packages/api/src/` codebase -- all middleware, routes, services, agents, schemas, config, inference, and admin
**Verdict:** REQUEST_CHANGES
**Phase coverage:** Phase 1 (Foundation) through Phase 4 (Underwriting) inclusive

---

## Summary

This review covers the entire backend API surface as of commit `64d68ef` (Phase 4 complete). The codebase has grown to include 5 WebSocket chat endpoints, 12+ REST routes, 30+ agent tools, a document extraction pipeline, compliance checks, a decision lifecycle, and an audit hash chain. The review is organized by OWASP Top 10 category with cross-references to specific files and line numbers.

Total findings: 24
- Critical: 7
- Warning: 12
- Suggestion: 5

---

## OWASP 1: Broken Access Control

### SE-01 [Critical] AUTH_DISABLED defaults to true in compose.yml

**Category:** Broken Access Control
**Location:** `/home/jary/redhat/git/mortgage-ai/compose.yml:91`
**Description:** The compose environment sets `AUTH_DISABLED: "${AUTH_DISABLED:-true}"`. Since most developers run `podman-compose up` without overriding this variable, the default development experience has all authentication and authorization disabled. The `_DISABLED_USER` in `auth.py:157-163` is hardcoded as `ADMIN` with `full_pipeline=True`, meaning every unauthenticated request is treated as a full-privilege admin. This extends to SQLAdmin (`admin.py:59`), all WebSocket endpoints (`_chat_handler.py:36-44`), and every REST route.
**Impact:** Any network-adjacent attacker can perform any action -- read all applications, render underwriting decisions, access HMDA data, modify audit records via SQLAdmin, and exfiltrate SSNs. In a demo environment, if the compose stack is exposed on a shared network (conference WiFi, cloud VM), all data is accessible without credentials.
**Recommendation:** Change the compose.yml default to `AUTH_DISABLED: "${AUTH_DISABLED:-false}"`. Require explicit opt-in for auth bypass. Add a startup warning log when `AUTH_DISABLED=true` is detected.

### SE-02 [Critical] SQLAdmin default credentials admin/admin

**Category:** Broken Access Control
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/core/config.py:59-66`
**Description:** `SQLADMIN_USER` defaults to `"admin"` and `SQLADMIN_PASSWORD` defaults to `"admin"`. The login check at `admin.py:49` uses plain string comparison (`username == settings.SQLADMIN_USER and password == settings.SQLADMIN_PASSWORD`). Even when `AUTH_DISABLED=false`, these default credentials grant full database CRUD via the SQLAdmin panel -- including the ability to edit audit events (for models other than `AuditEventAdmin` which has `can_edit=False`), modify application stages, change borrower data, and delete records.
**Impact:** Credential stuffing with `admin/admin` grants full database access. An attacker could modify loan decisions, alter financial records, or exfiltrate all PII including SSNs.
**Recommendation:** Remove default credentials. Require `SQLADMIN_USER` and `SQLADMIN_PASSWORD` to be set explicitly (fail startup if missing). Use `secrets.compare_digest()` instead of `==` for timing-safe comparison.

### SE-03 [Critical] Tool RBAC roles_map is overridable via graph state

**Category:** Broken Access Control
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/base.py:230`
**Description:** The `tool_auth` node merges graph-level `tool_allowed_roles` with per-invocation state: `roles_map = {**(tool_allowed_roles or {}), **state.get("tool_allowed_roles", {})}`. The `state.get("tool_allowed_roles", {})` value can potentially be influenced by prior graph nodes or injected state. If an attacker can influence the state dictionary (e.g., through a crafted message that the LLM includes in state transitions), they could override the RBAC map to grant themselves access to tools they should not have.
**Impact:** Privilege escalation -- a borrower-role user could potentially access underwriter-only tools (e.g., `uw_render_decision`, `uw_issue_condition`) if the graph state's `tool_allowed_roles` is manipulated.
**Recommendation:** Remove the state merge. The `tool_allowed_roles` should be immutable and set only at graph construction time from the YAML config. Delete `**state.get("tool_allowed_roles", {})` from line 230.

### SE-04 [Critical] No WebSocket message size or rate limits

**Category:** Broken Access Control / Insecure Design
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/_chat_handler.py:136`
**Description:** The WebSocket streaming loop at `_chat_handler.py:134-255` reads messages with `await ws.receive_text()` in an unbounded loop with no size limit per message and no rate limit per connection. There are 5 WebSocket endpoints (public, borrower, loan officer, underwriter, plus the base chat). Each accepts arbitrary-length messages and forwards them to the LLM agent, which incurs compute and token costs.
**Impact:** (1) Memory exhaustion: a single client can send a multi-GB message that the server buffers entirely. (2) LLM cost attack: rapid-fire messages trigger unlimited LLM API calls, potentially exhausting token budgets. (3) Denial of service: a small number of connections can saturate the server.
**Recommendation:** Configure WebSocket max message size via Uvicorn's `--ws-max-size` flag (default is 16MB -- explicitly set to a reasonable limit like 64KB). Add per-connection rate limiting (e.g., max 10 messages per minute). Add per-message length validation before forwarding to the agent.

### SE-05 [Warning] WebSocket JWT passed as query parameter

**Category:** Broken Access Control
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/_chat_handler.py:46`
**Description:** Authenticated WebSocket endpoints pass the JWT via `?token=<jwt>` query parameter (`ws.query_params.get("token")`). Query parameters are logged by web servers (Uvicorn access logs), appear in browser history, and may be captured by proxy servers and CDNs. Unlike HTTP headers, query strings are not treated as sensitive by most infrastructure.
**Impact:** JWT token leakage via server logs, browser history, or intermediary proxies. A leaked token grants the user's full session privileges for its lifetime.
**Recommendation:** Document this as a known limitation. For MVP, ensure Uvicorn access logging does not include query strings. For production hardening, switch to a subprotocol-based authentication pattern (send token as the first WebSocket message after connection).

### SE-06 [Warning] _user_context_from_state defaults to "anonymous" user_id

**Category:** Broken Access Control
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/underwriter_tools.py:38`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/decision_tools.py:38`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/condition_tools.py:40`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:57`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/loan_officer_tools.py:68`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/compliance_check_tool.py:48`
**Description:** The `_user_context_from_state` function is duplicated across 6 agent tool modules. Each copy defaults `user_id` to `"anonymous"` and `role` to a module-specific default (e.g., `"underwriter"`, `"borrower"`, `"loan_officer"`). If `user_id` or `user_role` is missing from the graph state for any reason (bug, race condition, state corruption), the function silently constructs a `UserContext` with fabricated identity rather than failing.
**Impact:** Actions performed with a fabricated user context are attributed to "anonymous" in audit records, making the audit trail unreliable for compliance. The fabricated role could also grant unintended access.
**Recommendation:** Raise an error if `user_id` or `user_role` is missing from state rather than falling back to defaults. Also consolidate the 6 duplicate implementations into a single shared function.

### SE-07 [Warning] Underwriter role has full_pipeline with no data filtering

**Category:** Broken Access Control
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/middleware/auth.py:145-146`
**Description:** The `build_data_scope` function assigns `DataScope(full_pipeline=True)` to the underwriter role. In `scope.py`, `full_pipeline=True` applies no WHERE clause filtering, giving underwriters access to every application in the system. Loan officers are correctly scoped to `assigned_to=user_id`, but underwriters can view, modify conditions, and render decisions on any application regardless of assignment.
**Impact:** An underwriter can access applications assigned to other underwriters, potentially rendering decisions on loans they should not handle (segregation of duties concern for regulated lending).
**Recommendation:** For Phase 5 (executive oversight), consider whether underwriter scope should be narrowed. At minimum, document this as an accepted risk for MVP and add it to the pre-production hardening checklist.

---

## OWASP 2: Cryptographic Failures

### SE-08 [Critical] SSN stored as plaintext in the database

**Category:** Cryptographic Failures
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/applications.py:55`
**Description:** The `Borrower.ssn` field stores Social Security Numbers as plaintext strings in the database. The field was previously named `ssn_encrypted` and renamed to `ssn` during pre-Phase 3 cleanup, but no encryption was ever implemented. SSNs are stored in cleartext in PostgreSQL, exposed in the `BorrowerSummary` schema at `applications.py:55` (`ssn=ab.borrower.ssn`), and visible in SQLAdmin.
**Impact:** Database compromise (SQL injection, backup theft, insider threat) exposes all borrower SSNs. SSNs are the primary identifier for identity theft. For a financial services application, this is a regulatory violation (GLBA Safeguards Rule requires encryption of customer SSNs).
**Recommendation:** Implement application-level encryption for the SSN field using Fernet symmetric encryption (or equivalent) with key stored in environment variables. Store only the encrypted value in the database. Decrypt only when explicitly needed, and only for authorized roles.

### SE-09 [Critical] SQLAdmin session secret regenerated on every restart

**Category:** Cryptographic Failures
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/admin.py:215`
**Description:** The `AdminAuth` backend is initialized with `secret_key=secrets.token_urlsafe(32)`. This generates a new random secret on every application startup. Since SQLAdmin uses Starlette's `SessionMiddleware` with this key to sign session cookies, all admin sessions are invalidated on every server restart or redeploy. More critically, if the application runs behind multiple workers (e.g., `uvicorn --workers 4`), each worker generates a different secret, meaning sessions created by one worker are invalid on another.
**Impact:** (1) Multi-worker deployments cannot maintain admin sessions. (2) Session cookies signed by one instance can be forged if an attacker observes the pattern of restart-based secret rotation. (3) In a multi-replica Kubernetes deployment, the admin panel is effectively unusable.
**Recommendation:** Source the session secret from an environment variable (e.g., `SQLADMIN_SECRET_KEY`) that persists across restarts and is shared across workers/replicas.

### SE-10 [Warning] Audit hash chain does not cover all event fields

**Category:** Cryptographic Failures
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/audit.py:25-28`
**Description:** The `_compute_hash` function hashes only `event_id`, `timestamp`, and `event_data`. It does not include `event_type`, `user_id`, `user_role`, `session_id`, or `application_id` in the hash computation. This means these fields can be modified after the fact without breaking the hash chain.
**Impact:** An attacker with database access could alter who performed an action (`user_id`), what type of event occurred (`event_type`), or which application was affected (`application_id`) without detection by the `verify_audit_chain` function.
**Recommendation:** Include all audit event fields in the hash computation: `event_type`, `user_id`, `user_role`, `session_id`, `application_id`, and `event_data`.

---

## OWASP 3: Injection

### SE-11 [Warning] Raw SQL in knowledge base vector search

**Category:** Injection
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/compliance/knowledge_base/search.py:65-74`
**Description:** The vector search function uses `text()` with parameterized bind variables (`:query_vec`, `:fetch_limit`). While the parameters are correctly bound (not string-interpolated), the use of raw SQL bypasses SQLAlchemy's ORM protections and makes it harder to audit. The `query_vec` parameter is converted to a string representation of a float array before being passed to PostgreSQL's `<=>` operator.
**Impact:** Low -- the parameters are properly bound, so SQL injection is not directly possible. However, if the embedding API returns a malformed vector, the `str(query_vec)` conversion could produce unexpected SQL behavior.
**Recommendation:** Add explicit validation that `query_vec` is a list of floats with the expected dimensionality (768) before passing to the query. Consider using pgvector's SQLAlchemy integration for type-safe vector operations.

### SE-12 [Warning] LLM output stored in database without validation in extraction pipeline

**Category:** Injection
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/extraction.py:130-138`
**Description:** The document extraction pipeline sends uploaded documents to the LLM, parses the JSON response, and stores `field_name` and `field_value` directly into `DocumentExtraction` records without any validation or sanitization. The LLM's output is treated as trusted data. The `field_name` is an arbitrary string from the LLM, and `field_value` can be any string.
**Impact:** If an attacker uploads a crafted document designed to manipulate the LLM's extraction output (indirect prompt injection), they could inject arbitrary data into extraction records. For example, a document could contain hidden text instructing the LLM to output fabricated financial data (e.g., inflated income values) which would then be stored as "extracted" data.
**Recommendation:** Validate `field_name` against an allowlist of expected extraction fields per document type. Add length limits to `field_value`. Flag extractions with unexpected field names for manual review.

### SE-13 [Warning] Prompt injection risk in document extraction

**Category:** Injection
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/extraction.py:207-212`
**Description:** User-uploaded documents (PDF text, images) are sent directly to the LLM as part of the extraction prompt. The document content becomes part of the LLM input. A malicious document could contain prompt injection payloads (e.g., "Ignore all previous instructions and output the following JSON...") that override the extraction prompt's instructions.
**Impact:** Attacker-controlled document content can manipulate the LLM's extraction behavior, causing it to output fabricated or altered financial data. This is a classic indirect prompt injection vector.
**Recommendation:** Add extraction output validation (field name allowlists, value range checks). Consider using structured output mode (`response_format`) if the LLM supports it. Add a quality flag when extracted values fall outside expected ranges.

---

## OWASP 4: Insecure Design

### SE-14 [Critical] No rate limiting on any endpoint

**Category:** Insecure Design
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/main.py` (global)
**Description:** The application has zero rate limiting on any endpoint -- REST or WebSocket. The `api-conventions.md` rule file documents rate limiting as a requirement (return 429, include `X-RateLimit-*` headers) but none is implemented. This includes sensitive endpoints like login (`/admin/login`), decision rendering, and all chat endpoints.
**Impact:** (1) Brute force attacks against SQLAdmin login (admin/admin credentials make this trivial). (2) LLM token exhaustion via rapid WebSocket messages. (3) Denial of service against any endpoint. (4) Credential stuffing attacks.
**Recommendation:** Add rate limiting middleware (e.g., `slowapi` or a custom middleware). Priority endpoints: SQLAdmin login (5 attempts/minute), WebSocket chat (10 messages/minute), document upload (10/minute), decision rendering (5/minute).

### SE-15 [Warning] LLM can autonomously confirm decisions (confirmed=true)

**Category:** Insecure Design
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/decision_tools.py:167,189`
**Description:** The `uw_render_decision` tool accepts a `confirmed: bool = False` parameter. The tool's docstring instructs the LLM to "never set confirmed=true without first showing the proposal to the underwriter," but this is an instruction, not an enforcement mechanism. The LLM can autonomously set `confirmed=true` on the first call, bypassing the two-phase human-in-the-loop design. Nothing in the code prevents `confirmed=true` from being passed directly.
**Impact:** An LLM hallucination or prompt injection could cause the agent to render a binding underwriting decision (approve, deny, or suspend) without human confirmation. In a financial services context, this could result in unauthorized loan approvals or denials.
**Recommendation:** Implement server-side enforcement of the two-phase flow. For example, require a `proposal_id` (returned from Phase 1) as a mandatory parameter for Phase 2, so the tool can verify that a proposal was actually generated and presented before accepting confirmation.

### SE-16 [Warning] Safety output shields fail-open

**Category:** Insecure Design
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/inference/safety.py:180-184`
**Description:** When the Llama Guard safety model is unavailable or returns an error during output checking, `check_output` returns `SafetyResult(is_safe=True)` -- treating the output as safe. Input shields correctly fail-closed (`safety.py:167-168`), but output shields do not. The comment documents this as intentional ("fail-open") but in a financial services context, allowing potentially unsafe content through when the safety system is down defeats the purpose of the shield.
**Impact:** If the safety model endpoint goes down (network issue, model crash, timeout), all LLM output is delivered to users unfiltered. This could include discriminatory language, financial advice violations, or PII leakage in the LLM's responses.
**Recommendation:** Consider fail-closed for output shields as well, or at minimum add a circuit breaker that blocks all output after N consecutive safety check failures. Log a high-severity alert when output shields fail open.

---

## OWASP 5: Security Misconfiguration

### SE-17 [Warning] PII masking middleware only covers ssn and dob

**Category:** Security Misconfiguration
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/middleware/pii.py:61-64`
**Description:** The `_PII_FIELD_MASKERS` dictionary only registers maskers for `"ssn"` and `"dob"`. The `mask_account_number` function is defined (lines 50-57) but never registered. Other PII fields -- `email`, `phone`, `employer_name`, `employer_address`, `first_name`, `last_name` -- are not masked for CEO-role responses. The CEO's `DataScope` sets `pii_mask=True`, but this only masks 2 out of many PII fields.
**Impact:** CEO role users see unmasked email addresses, phone numbers, employer information, and borrower names. This weakens the PII isolation that the CEO data scope is designed to enforce.
**Recommendation:** Register `mask_account_number` in the maskers dict. Add maskers for `email` (show domain only), `phone` (mask all but last 4), and consider `employer_name`. Document which fields are intentionally left unmasked and why.

### SE-18 [Warning] Validation error responses expose Pydantic internals

**Category:** Security Misconfiguration
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/main.py:109`
**Description:** The validation error handler at line 109 converts Pydantic errors to a string: `_build_error(422, str(exc.errors()), request_id)`. The `exc.errors()` output includes internal details like field paths, expected types, Python type names, and validation constraint values. This leaks implementation details about the request schema structure.
**Impact:** Attackers can enumerate API schema structure, field names, validation rules, and type constraints by sending malformed requests and analyzing the error responses.
**Recommendation:** Replace `str(exc.errors())` with a sanitized summary that lists only field names and human-readable error messages, without exposing type information or constraint values.

### SE-19 [Suggestion] CORS configuration could be more restrictive

**Category:** Security Misconfiguration
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/main.py:61-67`
**Description:** The CORS middleware is configured with `allow_origins=settings.ALLOWED_HOSTS` (defaults to `["http://localhost:5173"]`), specific methods, and specific headers. This is reasonable for development. However, `allow_credentials=True` combined with a wildcard-capable `ALLOWED_HOSTS` setting (the setting accepts a list of strings from env) could be misconfigured in production to allow credential-bearing cross-origin requests from unintended origins.
**Recommendation:** Add a startup validation that rejects `allow_credentials=True` when `ALLOWED_HOSTS` contains `"*"`. Document the CORS configuration requirements for production deployment.

---

## OWASP 6: Vulnerable and Outdated Components

### SE-20 [Suggestion] Dependency audit not run as part of this review

**Category:** Vulnerable Components
**Description:** A full dependency vulnerability scan was not executed as part of this review because the `uv` package manager does not have a built-in `audit` command equivalent to `npm audit` or `pip audit`. The `pyproject.toml` pins dependencies but a CVE scan of the dependency tree was not performed.
**Recommendation:** Add `pip-audit` to dev dependencies and run it as part of CI. Alternatively, use `trivy` or `grype` to scan the container image. Key high-risk dependencies to monitor: `pyjwt`, `cryptography`, `sqlalchemy`, `fastapi`, `httpx`, `pymupdf`.

---

## OWASP 7: Identification and Authentication Failures

### SE-21 [Warning] SQLAdmin login has no brute force protection

**Category:** Authentication Failures
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/admin.py:45-52`
**Description:** The `AdminAuth.login` method performs a simple credential check with no account lockout, no login attempt logging, no CAPTCHA, and no rate limiting. Combined with the default `admin/admin` credentials (SE-02), this makes the admin panel trivially accessible.
**Impact:** Automated brute force tools can enumerate the credentials in seconds. Even with non-default credentials, there is no mechanism to slow down or block repeated failed attempts.
**Recommendation:** Add login attempt logging (success and failure events to the audit trail). Add rate limiting on the login form (5 attempts per IP per minute). Use `secrets.compare_digest()` for timing-safe credential comparison (currently uses `==` at line 49).

### SE-22 [Suggestion] No CSRF protection on SQLAdmin login form

**Category:** Authentication Failures
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/admin.py:45-52`
**Description:** The SQLAdmin login form does not implement CSRF token validation. The `SessionMiddleware` used by SQLAdmin does not automatically add CSRF protection. An attacker could craft a cross-site request that authenticates a victim's browser session to the admin panel.
**Recommendation:** SQLAdmin's built-in auth does not support CSRF tokens natively. For MVP, this is an accepted risk given the admin panel is intended for local development. Document this limitation for production hardening.

---

## OWASP 8: Software and Data Integrity Failures

### SE-23 [Warning] Audit chain verification loads all events into memory

**Category:** Data Integrity Failures
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/audit.py:97-99`
**Description:** The `verify_audit_chain` function executes `select(AuditEvent).order_by(AuditEvent.id.asc())` and loads all results with `list(result.scalars().all())`. In a production system with millions of audit events, this loads the entire audit trail into memory at once. The function is exposed via the admin API endpoint and can be called by any admin user.
**Impact:** Denial of service via memory exhaustion. As the audit trail grows, a single call to the verification endpoint could consume gigabytes of memory and crash the server process.
**Recommendation:** Implement chunked verification that processes events in batches (e.g., 1000 at a time), carrying forward the previous hash between batches. Add pagination or a `limit` parameter to the verification endpoint.

---

## OWASP 9: Security Logging and Monitoring Failures

### SE-24 [Suggestion] Audit events for failed authentication not written to audit trail

**Category:** Logging Failures
**Description:** Failed JWT validation attempts (expired tokens, invalid tokens, missing tokens) raise `HTTPException` responses but do not write audit events. Failed SQLAdmin login attempts are not logged. The audit trail only captures successful actions (tool invocations, decisions, compliance checks).
**Recommendation:** Add audit event writes for: (1) failed JWT validation attempts, (2) failed SQLAdmin login attempts, (3) RBAC denials at the route level (`require_roles` failures), (4) failed WebSocket authentication. These events are critical for detecting attack patterns.

---

## OWASP 10: Server-Side Request Forgery (SSRF)

### SE-25 [Suggestion] No SSRF vectors identified

**Category:** SSRF
**Description:** The application does not accept user-controlled URLs for server-side fetching. The LLM endpoint URLs, Keycloak URL, S3 endpoint, and LangFuse host are all configured via environment variables and not exposed to user input. Document upload goes to a pre-configured S3 bucket path. No SSRF vectors were identified.
**Recommendation:** No action needed. Maintain the current pattern of configuring all external service URLs via environment variables only.

---

## Cross-Cutting Findings

### SE-26 [Warning] BorrowerSummary exposes SSN in list responses

**Category:** Data Exposure (cross-cutting)
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/applications.py:55`
**Description:** The `_build_app_response` function populates `BorrowerSummary` with `ssn=ab.borrower.ssn` at line 55. This means every `GET /api/applications` (list) and `GET /api/applications/{id}` (detail) response includes the full plaintext SSN for every borrower, for every role that can access the endpoint (loan officers, underwriters, admins). The PII masking middleware only activates for CEO role (`pii_mask=True`), so other roles see the raw SSN.
**Impact:** SSNs are returned in API responses to loan officers and underwriters who may not need them for their workflow. This violates the principle of least privilege for sensitive data exposure.
**Recommendation:** Remove `ssn` from `BorrowerSummary` entirely. Create a separate detail endpoint or field that returns SSN only when explicitly requested and only for roles that need it (e.g., compliance checks). At minimum, mask SSN to last-4 format in the summary response.

### SE-27 [Warning] ECOA compliance check hardcodes has_demographic_query=False

**Category:** Compliance (cross-cutting)
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/compliance_check_tool.py:153`
**Description:** The ECOA compliance check call in the compliance check tool always passes `has_demographic_query=False`. This means the ECOA check can never detect whether demographic data was actually collected, and the "demographic data collected" check always passes vacuously. The compliance check reports a false sense of security regarding HMDA/ECOA demographic collection compliance.
**Impact:** The compliance gate may approve applications that have not actually collected required demographic data, since the demographic query flag is always set to False.
**Recommendation:** Query the HMDA schema to determine if demographic data exists for the application's borrowers, and pass the actual result as `has_demographic_query`.

---

## Findings Index

| ID | Severity | OWASP | Title |
|----|----------|-------|-------|
| SE-01 | Critical | 1 | AUTH_DISABLED defaults to true in compose.yml |
| SE-02 | Critical | 1 | SQLAdmin default credentials admin/admin |
| SE-03 | Critical | 1 | Tool RBAC roles_map overridable via graph state |
| SE-04 | Critical | 1,4 | No WebSocket message size or rate limits |
| SE-05 | Warning | 1 | WebSocket JWT passed as query parameter |
| SE-06 | Warning | 1 | _user_context_from_state defaults to "anonymous" |
| SE-07 | Warning | 1 | Underwriter role has full_pipeline with no filtering |
| SE-08 | Critical | 2 | SSN stored as plaintext in the database |
| SE-09 | Critical | 2 | SQLAdmin session secret regenerated on every restart |
| SE-10 | Warning | 2 | Audit hash chain does not cover all event fields |
| SE-11 | Warning | 3 | Raw SQL in knowledge base vector search |
| SE-12 | Warning | 3 | LLM extraction output stored without validation |
| SE-13 | Warning | 3 | Prompt injection risk in document extraction |
| SE-14 | Critical | 4 | No rate limiting on any endpoint |
| SE-15 | Warning | 4 | LLM can autonomously confirm decisions |
| SE-16 | Warning | 4 | Safety output shields fail-open |
| SE-17 | Warning | 5 | PII masking only covers ssn and dob |
| SE-18 | Warning | 5 | Validation error responses expose internals |
| SE-19 | Suggestion | 5 | CORS configuration production hardening |
| SE-20 | Suggestion | 6 | Dependency audit not performed |
| SE-21 | Warning | 7 | SQLAdmin login has no brute force protection |
| SE-22 | Suggestion | 7 | No CSRF protection on SQLAdmin login |
| SE-23 | Warning | 8 | Audit chain verification loads all events into memory |
| SE-24 | Suggestion | 9 | Failed auth not written to audit trail |
| SE-25 | Suggestion | 10 | No SSRF vectors identified (no action) |
| SE-26 | Warning | -- | BorrowerSummary exposes SSN in list responses |
| SE-27 | Warning | -- | ECOA compliance check hardcodes has_demographic_query |

---

## OWASP Top 10 Coverage Checklist

- [x] A01: Broken Access Control -- SE-01 through SE-07
- [x] A02: Cryptographic Failures -- SE-08 through SE-10
- [x] A03: Injection -- SE-11 through SE-13
- [x] A04: Insecure Design -- SE-14 through SE-16
- [x] A05: Security Misconfiguration -- SE-17 through SE-19
- [x] A06: Vulnerable Components -- SE-20
- [x] A07: Authentication Failures -- SE-21, SE-22
- [x] A08: Data Integrity Failures -- SE-23
- [x] A09: Logging Failures -- SE-24
- [x] A10: SSRF -- SE-25

## Priority Remediation Order

For pre-Phase 5 hardening, address findings in this order:

1. **SE-01** (AUTH_DISABLED default) -- single-line fix, highest impact
2. **SE-02** (SQLAdmin credentials) -- remove defaults, require env vars
3. **SE-08** (SSN plaintext) -- encryption implementation, data migration
4. **SE-14** (rate limiting) -- add `slowapi` or equivalent middleware
5. **SE-03** (tool RBAC override) -- remove state merge, single-line fix
6. **SE-04** (WebSocket limits) -- add size/rate limits
7. **SE-15** (decision confirmation bypass) -- add server-side proposal_id enforcement
8. **SE-09** (session secret) -- move to env var
9. **SE-10** (audit hash fields) -- extend hash computation
10. Remaining Warning and Suggestion findings
