# Tech Lead Review -- Pre-Phase 5

**Reviewer:** tech-lead
**Date:** 2026-02-27
**Scope:** Full codebase (`packages/api/src/`) -- 91 source files, 739 tests passing
**Focus:** Pattern consistency, reuse opportunities, scaling risks for Phase 5 (CEO/executive features)

---

## Findings

### [TL-01] Severity: Warning
**File(s):**
- `packages/api/src/agents/borrower_tools.py:55-66`
- `packages/api/src/agents/loan_officer_tools.py:66-77`
- `packages/api/src/agents/underwriter_tools.py:34-45`
- `packages/api/src/agents/condition_tools.py:38-49`
- `packages/api/src/agents/decision_tools.py:36-47`
- `packages/api/src/agents/compliance_check_tool.py:46-57`

**Finding:** `_user_context_from_state()` is copy-pasted identically across 6 tool modules. Each copy builds a `UserContext` from the LangGraph agent state dict using the same logic: extract `user_id`, `user_role`, `user_email`, `user_name` from state, call `build_data_scope()`, return `UserContext`. The only difference is the default role string (`"borrower"`, `"loan_officer"`, `"underwriter"`), which is irrelevant because the actual role always comes from the state dict at runtime.

**Recommendation:** Extract to a shared function in `agents/__init__.py` or a new `agents/_shared.py` module. Accept an optional `default_role` parameter for the edge case, but in practice the state always carries the real role. Phase 5 will add at least one more tool module (CEO tools) that would become copy #7.

```python
# agents/_shared.py
def user_context_from_state(state: dict, default_role: str = "borrower") -> UserContext:
    ...
```

---

### [TL-02] Severity: Warning
**File(s):**
- `packages/api/src/services/condition.py` (returns `dict | None`, uses `"error"` key)
- `packages/api/src/services/decision.py` (returns `dict | None`, uses `"error"` key)
- `packages/api/src/services/application.py` (returns ORM objects)
- `packages/api/src/services/document.py` (returns ORM objects)
- `packages/api/src/services/rate_lock.py` (returns `dict | None`)
- `packages/api/src/services/status.py` (returns Pydantic model)

**Finding:** Service return type conventions are inconsistent across three patterns:

1. **ORM objects** (`application.py`, `document.py`): Return `Application | None`, `Document | None`.
2. **Raw dicts with "error" key** (`condition.py`, `decision.py`): Return `dict | None` where `None` means not-found and `{"error": "..."}` means business rule violation.
3. **Pydantic models** (`status.py`): Return `ApplicationStatusResponse | None`.

The dict-with-error-key pattern in condition.py and decision.py is particularly problematic. Callers must check `result is None` (not found), then `"error" in result` (business rule), then use the data. This is a stringly-typed error channel that bypasses Python's type system. Every consumer (7 tool functions in `condition_tools.py` and `decision_tools.py`) repeats the same `if result is None` / `if "error" in result` guard.

**Recommendation:** Standardize on one of two patterns for services that have business rule validation:

- **Option A (recommended for MVP):** Define a lightweight result type:
  ```python
  @dataclass
  class ServiceResult:
      data: dict | None = None
      error: str | None = None
  ```
  Services return `ServiceResult | None` (None = not found). This makes the error channel typed and explicit.

- **Option B:** Raise a custom `BusinessRuleError` exception for business rule violations (similar to how `document.py` raises `DocumentUploadError`), letting the tool layer catch it.

Either approach eliminates the stringly-typed `"error" in result` pattern before Phase 5 adds more decision/condition flows.

---

### [TL-03] Severity: Warning
**File(s):**
- `packages/api/src/agents/underwriter_tools.py:148-155` (`uw_application_detail`)
- `packages/api/src/agents/underwriter_tools.py:471-478` (`uw_risk_assessment`)
- `packages/api/src/agents/underwriter_tools.py:631-638` (`uw_preliminary_recommendation`)
- `packages/api/src/agents/compliance_check_tool.py:124-130` (`compliance_check`)

**Finding:** The `ApplicationFinancials` query (`select(ApplicationFinancials).where(ApplicationFinancials.application_id == ...)`) is duplicated 4 times across tool functions, each time with an inline `from db import ApplicationFinancials` inside the function body. This is both a reuse problem and an import style inconsistency -- every other import in the codebase is at module level.

**Recommendation:** Add a `get_financials(session, application_id)` function to the service layer (either in `application.py` or a new `financials.py`). Move the import to module level. This query will be needed by Phase 5's executive dashboard tools as well.

---

### [TL-04] Severity: Warning
**File(s):**
- `packages/api/src/agents/decision_tools.py:310-322` (`uw_draft_adverse_action`)
- `packages/api/src/agents/decision_tools.py:430-442` (`uw_generate_le`)
- `packages/api/src/agents/decision_tools.py:585-597` (`uw_generate_cd`)

**Finding:** The primary borrower lookup pattern is duplicated 3 times in `decision_tools.py`:

```python
ab_stmt = select(ApplicationBorrower).where(
    ApplicationBorrower.application_id == application_id,
    ApplicationBorrower.is_primary.is_(True),
)
ab_result = await session.execute(ab_stmt)
ab = ab_result.scalar_one_or_none()
if ab:
    b_stmt = select(Borrower).where(Borrower.id == ab.borrower_id)
    b_result = await session.execute(b_stmt)
    borrower = b_result.scalar_one_or_none()
    if borrower:
        borrower_name = f"{borrower.first_name} {borrower.last_name}"
```

This is 12 lines copied verbatim 3 times. The CEO dashboard in Phase 5 will likely need the same lookup for portfolio summaries.

**Recommendation:** Extract `get_primary_borrower_name(session, application_id) -> str` to the service layer. This is a one-query-two-join pattern that belongs in `application.py` or a new helper module.

---

### [TL-05] Severity: Warning
**File(s):**
- `packages/api/src/agents/decision_tools.py:446-467` (`uw_generate_le`)
- `packages/api/src/agents/decision_tools.py:600-631` (`uw_generate_cd`)

**Finding:** The monthly mortgage payment calculation (amortization formula) is duplicated between `uw_generate_le` and `uw_generate_cd`:

```python
monthly_rate = rate / 100 / 12
num_payments = term_years * 12
if monthly_rate > 0 and loan_amount > 0:
    monthly_payment = (
        loan_amount
        * (monthly_rate * (1 + monthly_rate) ** num_payments)
        / ((1 + monthly_rate) ** num_payments - 1)
    )
```

A similar calculation exists in `services/calculator.py` for the affordability tool. Three places compute the same formula.

**Recommendation:** Extract `compute_monthly_payment(principal, annual_rate, term_years) -> float` to a shared utility (e.g., `services/calculator.py` where the affordability logic already lives). This prevents divergence if the calculation ever needs refinement.

---

### [TL-06] Severity: Warning
**File(s):**
- `packages/api/src/agents/decision_tools.py:565-577` (`uw_generate_cd`)
- `packages/api/src/services/decision.py:119-126` (`_resolve_decision`)

**Finding:** The "outstanding conditions" calculation is duplicated between the CD generation tool and the decision service. Both sum `open + responded + under_review + escalated` from `get_condition_summary()["counts"]`:

```python
outstanding = (
    cond_summary["counts"].get("open", 0)
    + cond_summary["counts"].get("responded", 0)
    + cond_summary["counts"].get("under_review", 0)
    + cond_summary["counts"].get("escalated", 0)
)
```

**Recommendation:** Add `get_outstanding_count(summary: dict) -> int` to `services/condition.py` as a pure function. Both call sites import and use it. Phase 5 may need this count for executive reporting.

---

### [TL-07] Severity: Warning
**File(s):**
- `packages/api/src/agents/loan_officer_tools.py:160-168` (quality_flags parsing in `lo_document_review`)
- `packages/api/src/agents/loan_officer_tools.py:208-218` (quality_flags parsing in `lo_document_quality`)
- `packages/api/src/services/condition.py:32-42` (`_parse_quality_flags`)

**Finding:** The `quality_flags` field is stored as either a JSON array string or a plain CSV string. The parsing logic for this is implemented 3 different ways:

1. `condition.py:_parse_quality_flags()` -- handles JSON array and CSV fallback (most robust).
2. `loan_officer_tools.py:160-168` -- inline try/except `json.loads()` with raw fallback.
3. `loan_officer_tools.py:208-218` -- same pattern but slightly different output formatting.

The UW detail tool (`underwriter_tools.py:231`) doesn't parse at all -- it dumps `doc.quality_flags` raw into the output string.

**Recommendation:** Make `_parse_quality_flags` a public function (`parse_quality_flags`) in a shared location (e.g., `services/document.py` since it operates on document data). All consumers should use the same parsing logic. The inconsistency will grow as Phase 5 adds executive views that surface document quality.

---

### [TL-08] Severity: Warning
**File(s):**
- `packages/api/src/agents/underwriter_tools.py` (756 lines)
- `packages/api/src/agents/borrower_tools.py` (728 lines)
- `packages/api/src/agents/decision_tools.py` (701 lines)

**Finding:** Three tool modules exceed 700 lines. `underwriter_tools.py` contains 5 tools (queue view, application detail, risk assessment, preliminary recommendation, and helper functions), `decision_tools.py` contains 4 tools plus 2 format helpers and a compliance gate, and `borrower_tools.py` contains 14 tools. Phase 5 will add CEO tools, and if any existing agent gains new capabilities, these files will push past 800+ lines.

The existing split for the underwriter agent is already well-structured: core tools in `underwriter_tools.py`, conditions in `condition_tools.py`, decisions in `decision_tools.py`, compliance in `compliance_check_tool.py` and `compliance_tools.py`. However, `borrower_tools.py` has no split despite having 14 tools spanning intake, documents, conditions, disclosures, and rate locks.

**Recommendation:** Split `borrower_tools.py` along the same domain boundaries used for the underwriter:
- `borrower_tools.py` -- intake tools (start_application, update_application_data, get_application_summary)
- `borrower_document_tools.py` -- document tools (document_completeness, document_processing_status)
- `borrower_condition_tools.py` -- condition tools (list_conditions, respond_to_condition_tool, check_condition_satisfaction)

The remaining tools (application_status, regulatory_deadlines, disclosure tools, rate_lock_status) can stay in the main file as they're lightweight. This keeps each file in the 200-400 line range.

---

### [TL-09] Severity: Warning
**File(s):**
- `packages/api/src/routes/borrower_chat.py`
- `packages/api/src/routes/loan_officer_chat.py`
- `packages/api/src/routes/underwriter_chat.py`

**Finding:** The three authenticated chat route files are nearly identical (structurally isomorphic). Each one:
1. Accepts WebSocket, calls `authenticate_websocket` with a specific role
2. Gets conversation service, resolves checkpointer
3. Gets the agent by name
4. Builds thread_id and session_id
5. Calls `run_agent_stream`
6. Has a `/conversations/history` GET endpoint

The differences are only: role enum, agent name string, and route path prefix. Adding the CEO chat in Phase 5 means copy-pasting this a 4th time.

**Recommendation:** Extract a factory function in `_chat_handler.py`:

```python
def create_chat_routes(
    role: UserRole,
    agent_name: str,
    path_prefix: str,
) -> APIRouter:
    ...
```

Each persona module becomes 3-5 lines calling the factory. The `_chat_handler.py` already centralizes the streaming logic; this extends the pattern to route registration.

---

### [TL-10] Severity: Suggestion
**File(s):**
- `packages/api/src/services/condition.py` (returns `list[dict]`)
- `packages/api/src/services/decision.py` (returns `list[dict]`, `dict`)
- `packages/api/src/services/rate_lock.py` (returns `dict`)
- `packages/api/src/services/application.py` (returns ORM `Application`)

**Finding:** The condition and decision services manually serialize ORM objects to dicts (e.g., `condition.py:71-86` builds a dict with `"id"`, `"description"`, `"severity"`, etc.; `decision.py:405-428` `_decision_to_dict()` does the same for decisions). Meanwhile, `application.py` returns raw ORM objects and lets the route layer handle serialization via `_build_app_response()`.

This means:
- The route layer does `ConditionItem(**result)` to convert the dict back into a Pydantic schema.
- Tool functions consume the dicts directly.
- There are no Pydantic response models for conditions or decisions at the service layer.

**Recommendation:** Create Pydantic response schemas for Condition and Decision that services return directly (like `ApplicationStatusResponse` in `status.py`). This eliminates the dict-building boilerplate, adds validation, and makes the service layer type-safe. For the tool layer (which needs strings, not Pydantic models), add a `.to_display_string()` method or keep the existing format functions.

---

### [TL-11] Severity: Suggestion
**File(s):**
- `packages/api/src/services/application.py:187-193` (`transition_stage` raises `HTTPException`)
- `packages/api/src/services/condition.py` (returns `{"error": "..."}`)
- `packages/api/src/services/decision.py` (returns `{"error": "..."}`)
- `packages/api/src/services/document.py:136-139` (raises `ValueError`)

**Finding:** Services use 3 different patterns to signal business rule violations:

1. `application.py:transition_stage` raises `HTTPException` directly from the service layer (line 187). This couples the service to HTTP semantics.
2. `condition.py` and `decision.py` return `{"error": "..."}` dicts (see TL-02).
3. `document.py:update_document_status` raises `ValueError`, which the tool layer catches.

The `HTTPException` in `application.py` is the most concerning because it means the service layer cannot be reused by non-HTTP callers (agent tools, background jobs, CLI scripts) without catching HTTP exceptions -- a layer violation.

**Recommendation:** Adopt a single pattern for service-layer business rule violations. The cleanest option:
- Define `class BusinessRuleError(Exception)` in a shared location.
- Services raise `BusinessRuleError("message")` for invalid transitions, missing prerequisites, etc.
- Route handlers catch `BusinessRuleError` and convert to `HTTPException(422)`.
- Tool functions catch `BusinessRuleError` and return the message string.
- Remove the `HTTPException` import from `services/application.py`.

---

### [TL-12] Severity: Suggestion
**File(s):**
- `packages/api/src/services/condition.py:624` (returns `{"counts": ..., "total": ...}`)
- `packages/api/src/services/decision.py:334-348` (returns inline dict)
- `packages/api/src/services/rate_lock.py:48-76` (returns inline dict)

**Finding:** Several service functions return ad-hoc dicts with no type definition. For example, `get_condition_summary` returns `{"counts": dict, "total": int}`, `render_decision` returns a 13-key dict, and `get_rate_lock_status` returns a 7-key dict. These shapes are consumed by multiple callers but aren't defined anywhere -- the contract is implicit.

**Recommendation:** Define `TypedDict` or `dataclass` types for these return shapes. This doesn't require a full Pydantic schema -- a `TypedDict` is lightweight and provides IDE autocompletion and type checking without runtime cost:

```python
class ConditionSummary(TypedDict):
    counts: dict[str, int]
    total: int
```

---

### [TL-13] Severity: Suggestion
**File(s):**
- `packages/api/src/services/condition.py` (624 lines)
- `packages/api/src/services/decision.py` (428 lines)

**Finding:** `condition.py` at 624 lines contains 10 public functions spanning borrower operations (respond, link document, check documents) and underwriter operations (issue, review, clear, waive, return, summary). `decision.py` at 428 lines mixes resolution logic, AI comparison, and CRUD. Both are manageable now but are growing candidates.

**Recommendation:** No split needed now, but flag for Phase 5 monitoring. If Phase 5 adds any condition or decision features, consider splitting `condition.py` into `condition_borrower.py` (borrower-facing ops) and `condition_underwriter.py` (UW lifecycle ops), mirroring the tool-layer split that already exists.

---

### [TL-14] Severity: Suggestion
**File(s):**
- `packages/api/src/agents/borrower_tools.py:301-316` (`acknowledge_disclosure`)
- `packages/api/src/agents/borrower_tools.py:612-659` (`update_application_data`)
- `packages/api/src/agents/loan_officer_tools.py:298-314` (`lo_mark_resubmission`)

**Finding:** Several tool functions call `write_audit_event` and then `session.commit()` inside the tool's own `SessionLocal()` context. This is the correct pattern. However, a few tools write audit events without being aware that the service function they called already committed the session. For example:

- `borrower_tools.py:589-597` (`start_application`) calls `start_application_service` (which commits internally via `application.py:create_application`), then writes an audit event and commits again. This works but is fragile -- if the service function ever changed to not commit, the second commit would be necessary.
- `loan_officer_tools.py:394-425` (`lo_submit_to_underwriting`) calls `transition_stage` twice (each of which commits), then writes audit events and commits again.

**Recommendation:** Adopt an explicit convention: service functions should NOT commit (they flush to get IDs); tool functions commit once at the end after all writes (including audit). Currently `create_application` commits internally (line 153), which is inconsistent with the condition/decision services that let the caller commit. Standardize to caller-commits for new code, and refactor `create_application` when convenient.

---

### [TL-15] Severity: Suggestion
**File(s):**
- `packages/api/src/services/application.py:34-74` (`list_applications`)
- `packages/api/src/services/document.py:39-75` (`list_documents`)

**Finding:** The list/pagination pattern is consistent between `list_applications` and `list_documents` (count query + data query + tuple return). However, `condition.py:get_conditions` returns a flat list without pagination, and `decision.py:get_decisions` also returns a flat list. The routes for conditions (`applications.py:274-282`) wraps the list in a `ConditionListResponse` with a pagination object where `offset=0, limit=len(result), has_more=False` -- a fake pagination envelope.

This will not scale for the CEO dashboard in Phase 5, which may need to query conditions or decisions across many applications with real pagination.

**Recommendation:** Add optional `offset`/`limit` parameters to `get_conditions` and `get_decisions` and return `tuple[list, int]` like the other list services. This is a low-risk enhancement that aligns all list operations before Phase 5 needs them.

---

### [TL-16] Severity: Suggestion
**File(s):**
- `packages/api/src/routes/applications.py:86-146` (list endpoint with urgency enrichment)
- `packages/api/src/routes/applications.py:179-214` (status endpoint with urgency enrichment)

**Finding:** The urgency enrichment pattern (check role, call `compute_urgency`, merge into response) is duplicated between the list and status endpoints. Phase 5's CEO dashboard will need urgency data on portfolio views, adding a third copy.

**Recommendation:** Extract urgency enrichment into a reusable helper in the routes module or the service layer. For example, a decorator or a `enrich_with_urgency(items, session, user)` function.

---

### [TL-17] Severity: Critical
**File(s):**
- `packages/api/src/services/audit.py:60` (advisory lock)
- `packages/api/src/agents/borrower_tools.py:589-602` (`start_application`)
- `packages/api/src/agents/loan_officer_tools.py:394-425` (`lo_submit_to_underwriting`)

**Finding:** Agent tools open their own `SessionLocal()` for each tool call (correct -- see design notes in each file). When a tool writes an audit event, that audit event is written within the tool's session and takes a PostgreSQL advisory lock (`pg_advisory_xact_lock(900001)`) for hash chain serialization. This lock is held until the tool's transaction commits.

The problem: `lo_submit_to_underwriting` makes two `transition_stage` calls, each of which commits independently (lines 390, 408), then writes two audit events (lines 394, 412), then commits again (line 424). Because `transition_stage` calls `session.commit()` internally, the advisory lock from the audit event write inside `transition_stage` is released, then a new lock is acquired for the tool's own audit writes. This creates a window where another concurrent audit writer could interleave, potentially breaking the hash chain ordering assumption.

In practice at MVP scale (single user testing), this is harmless. But the pattern is structurally wrong and will cause hash chain verification failures under concurrent load.

**Recommendation:** The immediate fix is to ensure all audit writes within a single logical operation share the same transaction. The tool-level `SessionLocal()` pattern is correct for isolation, but the services called within that session must not commit independently when audit writes follow. Options:
1. Make `transition_stage` accept a `commit=False` parameter so the tool can batch all writes.
2. Move the audit writes into the service functions (some already do this, e.g., `condition.py`), so the audit event and the state change share one transaction.

This should be addressed before any production hardening, but Phase 5 is a reasonable gate since the CEO dashboard will be read-heavy and won't exacerbate this.

---

### [TL-18] Severity: Suggestion
**File(s):**
- `packages/api/src/agents/__init__.py`
- `packages/api/src/services/__init__.py`

**Finding:** The `agents/` directory contains 14 files for 4 agents. The naming convention is clear (`{persona}_assistant.py` for graph builders, `{persona}_tools.py` for tool functions, plus shared modules), and the underwriter tooling is well-split across 4 files by domain. This organization will accommodate the CEO agent cleanly.

The `services/` directory has 16 files at the top level plus a `compliance/` subdirectory (4 files) and a `seed/` subdirectory (2 files). Phase 5 will add executive reporting services. The flat structure is fine for now but should be monitored.

**Recommendation:** No action needed now. The current structure can absorb Phase 5 without reorganization. But if Phase 5 adds 3+ new service files, consider grouping services by domain (e.g., `services/underwriting/`, `services/intake/`) similar to the existing `services/compliance/` split.

---

## Summary

| Severity | Count | Key Themes |
|----------|-------|------------|
| Critical | 1 | Audit hash chain integrity under concurrent tool operations (TL-17) |
| Warning | 8 | Duplicated utility functions across tool modules (TL-01, TL-03, TL-04, TL-05, TL-06, TL-07), inconsistent service error patterns (TL-02), file size growth (TL-08), chat route duplication (TL-09) |
| Suggestion | 8 | Service return type standardization (TL-10, TL-12), error signaling consistency (TL-11), commit convention (TL-14), pagination gaps (TL-15), urgency enrichment (TL-16), condition file size (TL-13), directory organization (TL-18) |

### Priority for Pre-Phase 5 Cleanup

**Must-fix before Phase 5:**
- TL-01 (extract `_user_context_from_state`) -- Phase 5 adds CEO tools, this becomes copy #7
- TL-09 (chat route factory) -- Phase 5 adds CEO chat, this becomes copy #4

**Should-fix before Phase 5:**
- TL-03 (extract financials query) -- Phase 5 executive dashboard needs the same query
- TL-04 (extract borrower name lookup) -- same rationale
- TL-05 (extract monthly payment calc) -- same rationale
- TL-07 (unify quality_flags parsing) -- CEO dashboard will display document quality
- TL-08 (split borrower_tools.py) -- prevents the file from exceeding 800 lines

**Track for production hardening:**
- TL-17 (audit hash chain under concurrency) -- structural issue, not urgent at MVP
- TL-02, TL-11 (error pattern standardization) -- valuable but large refactor
- TL-10, TL-12 (typed service returns) -- incremental improvement

**Defer to need:**
- TL-06, TL-13, TL-14, TL-15, TL-16, TL-18 -- address when Phase 5 implementation hits these areas
