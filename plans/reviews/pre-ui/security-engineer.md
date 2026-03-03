# Security Engineer Review -- Pre-UI

**Scope:** `packages/api/src/`, `packages/db/src/`, `config/`
**Date:** 2026-03-02
**Reviewer:** Security Engineer agent
**Verdict:** REQUEST_CHANGES (2 Critical, 3 Warning, 4 Suggestion)

All items from `plans/reviews/pre-ui/known-deferred.md` have been excluded.
This report contains only NEW findings not previously identified.

---

## Critical

### SE-01: PII masking bypassed on WebSocket agent tool responses (CEO role)

**Category:** OWASP A01 -- Broken Access Control
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/_chat_handler.py:93-266`, `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/ceo_tools.py:257-291`
**CWE:** CWE-200 (Exposure of Sensitive Information)

**Description:** The `PIIMaskingMiddleware` in `middleware/pii.py` intercepts HTTP JSON responses and masks PII fields (SSN, DOB, account_number) when `request.state.pii_mask` is True (CEO role). However, WebSocket messages are streamed directly via `ws.send_json()` in `_chat_handler.py` and bypass HTTP middleware entirely. When the CEO agent calls tools like `ceo_application_lookup`, borrower names are returned in tool output that flows through `run_agent_stream` as LLM-generated text tokens. The LLM may include PII from the tool response in its conversational output, and that output is sent raw to the WebSocket client without any PII masking.

Additionally, `ceo_application_lookup` (line 270-274) directly includes borrower first/last names in its output string. While names are not currently in `_PII_FIELD_MASKERS`, the broader issue is that any PII flowing through agent tool responses to WebSocket is entirely unmasked.

**Impact:** CEO users receive unmasked PII through the chat interface even though the REST API correctly masks it. This undermines the defense-in-depth PII isolation strategy.

**Recommendation:** Add PII masking to WebSocket output path. Either: (a) apply `_mask_pii_recursive` to the `full_response` string before sending the `done` event, or (b) add a post-processing step in `run_agent_stream` that scans outbound token content against known PII field patterns before `ws.send_json`. Also verify that agent tools for CEO role do not return raw PII values -- they should use the same masking utilities available in `middleware/pii.py`.

---

### SE-02: Audit export endpoint missing user identity in audit trail

**Category:** OWASP A09 -- Security Logging and Monitoring Failures
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/audit.py:186-197`
**CWE:** CWE-778 (Insufficient Logging)

**Description:** The `audit_export` endpoint writes an audit event for the export action but does not pass `user_id` or `user_role` to `write_audit_event()`. The endpoint has `require_roles(UserRole.ADMIN, UserRole.CEO, UserRole.UNDERWRITER)` but never injects `CurrentUser`, so the audit record is written with `user_id=None` and `user_role=None`. Every other audit-writing endpoint and tool in the codebase correctly captures user identity.

This is specifically a compliance concern: bulk data exports are high-risk operations that should always record who performed them. An audit trail with null user identity on export events is useless for incident investigation.

**Impact:** If an unauthorized export occurs (or if an authorized user exports data they should not), the audit trail cannot identify who performed the action.

**Recommendation:** Add `user: CurrentUser` as a parameter to `audit_export()` and pass `user_id=user.user_id, user_role=user.role.value` to `write_audit_event()`.

---

## Warning

### SE-03: No security response headers configured

**Category:** OWASP A05 -- Security Misconfiguration
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/main.py:58-75`
**CWE:** CWE-693 (Protection Mechanism Failure)

**Description:** The FastAPI application configures CORS middleware but sets no security response headers. Missing headers include:
- `X-Content-Type-Options: nosniff` -- prevents MIME sniffing
- `X-Frame-Options: DENY` -- prevents clickjacking
- `Content-Security-Policy` -- prevents XSS and injection
- `Referrer-Policy: strict-origin-when-cross-origin` -- limits referrer leakage
- `Permissions-Policy` -- restricts browser features

While the frontend is replaceable and may add its own headers, the API itself serves JSON that could be rendered in a browser context (e.g., via the Swagger UI at `/docs`). The SQLAdmin panel at `/admin` is particularly susceptible to clickjacking without `X-Frame-Options`.

**Impact:** Browser-based clients interacting with the API directly (or via SQLAdmin) are exposed to clickjacking, MIME confusion, and XSS vectors that standard headers would mitigate.

**Recommendation:** Add a Starlette middleware that sets security headers on all responses. At minimum: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.

---

### SE-04: Conversation history endpoint does not verify thread ownership

**Category:** OWASP A01 -- Broken Access Control (IDOR)
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/_chat_handler.py:334-347`
**CWE:** CWE-639 (Authorization Bypass Through User-Controlled Key)

**Description:** The `get_conversation_history_endpoint` in `create_authenticated_chat_router` constructs a thread ID using `ConversationService.get_thread_id(user.user_id, agent_name)`, which is correct for the authenticated user. However, the `ConversationService.verify_thread_ownership()` method exists (line 134 of conversation.py) but is never called anywhere in the codebase. If a future code change or a different endpoint allows specifying a thread_id directly, there is no enforcement layer to prevent one user from accessing another user's conversation history.

The current code is safe because thread_id is derived server-side from the authenticated user_id. But the defense is implicit (construction-based) rather than explicit (verification-based). The verify_thread_ownership function was clearly written for this purpose but was never wired in.

**Impact:** Currently low risk since thread_id is constructed server-side. However, the orphaned verification method indicates a defense-in-depth layer was planned but not implemented, creating a latent IDOR risk if future endpoints accept user-supplied thread_ids.

**Recommendation:** Call `ConversationService.verify_thread_ownership(thread_id, user.user_id)` in `get_conversation_history_endpoint` after constructing the thread_id. This makes the authorization check explicit rather than implicit.

---

### SE-05: LangFuse observation pagination unbounded -- potential DoS via memory exhaustion

**Category:** OWASP A04 -- Insecure Design
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/services/langfuse_client.py:100-117`
**CWE:** CWE-770 (Allocation of Resources Without Limits)

**Description:** The `fetch_observations` function paginates through all LangFuse observations in the time range with no upper bound on total pages or total records. The `while True` loop on line 101 fetches page after page, appending all results to `all_observations` in memory. For a busy deployment with many LLM calls, requesting `hours=2160` (90 days, the maximum allowed) could return millions of observations, causing OOM.

The in-memory TTL cache (`_cache`) also stores all fetched observations, so a single large query remains in memory for 60 seconds after the request completes, compounding the impact.

**Impact:** A CEO or admin user requesting model monitoring over a long time range could exhaust API server memory, causing denial of service for all users.

**Recommendation:** Add a `max_records` parameter (e.g., 10000) to `fetch_observations` that stops pagination once the limit is reached. Also consider adding a `max_pages` guard (e.g., 50) to the pagination loop.

---

## Suggestion

### SE-06: CEO application lookup borrower_name search lacks input length limit

**Category:** OWASP A03 -- Injection
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/ceo_tools.py:228`
**CWE:** CWE-20 (Improper Input Validation)

**Description:** The `ceo_application_lookup` tool passes `borrower_name` directly into an `ilike()` pattern: `.where((Borrower.first_name + " " + Borrower.last_name).ilike(f"%{borrower_name}%"))`. While SQLAlchemy's `ilike()` uses parameterized queries (so SQL injection is not possible), the `borrower_name` value comes from LLM tool call arguments, which originate from user chat input. There is no length limit or character validation on this parameter.

A very long search string (thousands of characters) would produce a large LIKE pattern that could be expensive for PostgreSQL to evaluate, especially with the leading `%` wildcard that prevents index usage.

**Impact:** Potential for slow queries if the LLM passes through an unusually long search term. Low risk in practice since the LLM typically normalizes input, but no server-side guard exists.

**Recommendation:** Truncate `borrower_name` to a reasonable length (e.g., 200 characters) and strip SQL wildcard characters (`%`, `_`) from the input before passing to `ilike()`.

---

### SE-07: Keycloak realm has `sslRequired: "none"`

**Category:** OWASP A02 -- Cryptographic Failures
**Location:** `/home/jary/redhat/git/mortgage-ai/config/keycloak/summit-cap-realm.json:3`
**CWE:** CWE-319 (Cleartext Transmission of Sensitive Information)

**Description:** The Keycloak realm configuration sets `"sslRequired": "none"`, which allows authentication traffic over plain HTTP. While this is appropriate for local development, this configuration file would be imported as-is into any Keycloak instance (including staging or production). Credentials and tokens would be transmitted in cleartext.

**Impact:** If this realm export is used beyond local dev, authentication credentials and JWT tokens would be transmitted without encryption.

**Recommendation:** Add a comment documenting that this is dev-only. For production, provide a separate realm config or document that `sslRequired` must be changed to `"external"` or `"all"` before deployment.

---

### SE-08: Audit search endpoint `event_type` parameter accepts arbitrary strings

**Category:** OWASP A03 -- Injection (data quality)
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/audit.py:133`
**CWE:** CWE-20 (Improper Input Validation)

**Description:** The `audit_search` endpoint accepts an `event_type` query parameter as a free-form string. While this is used safely in a parameterized SQLAlchemy `where()` clause (no injection risk), there is no validation against known event types. An attacker could probe for event types by sending arbitrary strings and observing response counts, potentially revealing information about system internals (which event types exist).

**Impact:** Minor information disclosure about the audit event type taxonomy. No data integrity or injection risk.

**Recommendation:** Consider validating `event_type` against a known set of event type strings (e.g., from an enum or constant list), returning 422 for unrecognized types.

---

### SE-09: `Strict-Transport-Security` (HSTS) not set for production readiness

**Category:** OWASP A02 -- Cryptographic Failures
**Location:** `/home/jary/redhat/git/mortgage-ai/packages/api/src/main.py`
**CWE:** CWE-319 (Cleartext Transmission of Sensitive Information)

**Description:** No HSTS header is configured. While the project is MVP maturity and production security hardening is a non-goal, the `security.md` rule states "HTTPS only in production -- enforce via HSTS headers." Adding a note or placeholder for HSTS in the security headers middleware (from SE-03) would ensure this is not forgotten during production hardening.

**Impact:** Without HSTS, browsers could be tricked into making HTTP requests even after initially connecting over HTTPS, enabling man-in-the-middle attacks.

**Recommendation:** When implementing SE-03 (security headers), include a conditional HSTS header that activates when `DEBUG=false` or a `PRODUCTION=true` flag is set.

---

## OWASP Top 10 Coverage Summary

| # | Category | Status |
|---|----------|--------|
| A01 | Broken Access Control | SE-01 (PII bypass), SE-04 (thread ownership) -- new. Existing deferred items cover auth bypass, data scope. |
| A02 | Cryptographic Failures | SE-07, SE-09 -- new. SSN plaintext deferred. |
| A03 | Injection | SE-06 (input length) -- new. SQL injection not found (ORM + parameterized). |
| A04 | Insecure Design | SE-05 (unbounded pagination) -- new. Rate limiting deferred. |
| A05 | Security Misconfiguration | SE-03 (missing headers) -- new. AUTH_DISABLED, admin creds deferred. |
| A06 | Vulnerable Components | Not audited (dependency scan out of scope for this review). |
| A07 | Auth Failures | No new findings. Keycloak JWT validation is solid. |
| A08 | Data Integrity | No new findings. Audit hash chain in place. |
| A09 | Logging Failures | SE-02 (missing user identity on export audit) -- new. |
| A10 | SSRF | No findings. LangFuse URL is from server config, not user input. |

## Dependency Scan

Not performed in this review (dependencies unchanged since last audit). Recommend running `uv pip audit` before UI integration.

## Secrets Check

- No new hardcoded secrets found beyond known deferred items (admin/admin, MinIO keys in config).
- `AUDIT_LOCK_KEY` is a fixed integer (900001) -- acceptable, not a secret.
- LLM API keys default to `"not-needed"` -- acceptable for local dev.
