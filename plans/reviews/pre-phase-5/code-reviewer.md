# Code Quality Review -- Pre-Phase 5

**Reviewer:** code-reviewer
**Date:** 2026-02-27
**Scope:** Full codebase (`packages/api/src/`) -- 87 files, ~13,327 lines
**Focus:** Code added in Phases 3-4 with cross-cutting patterns from Phases 1-2

---

## Findings

### [CR-01] Severity: Warning
**File(s):** `packages/api/src/agents/underwriter_tools.py:34`, `condition_tools.py:38`, `compliance_check_tool.py:46`, `loan_officer_tools.py:66`, `borrower_tools.py:55`, `decision_tools.py:36`
**Finding:** `_user_context_from_state()` is copy-pasted identically across 6 tool modules. Each copy is 12 lines. The only difference is the default role string (`"underwriter"`, `"loan_officer"`, `"borrower"`), which is never actually used because the real role always comes from graph state. This is the most duplicated function in the codebase (flagged in pre-Phase 3 review as a growing pattern -- now at 6 copies).
**Recommendation:** Extract to a shared module (e.g., `agents/_state_utils.py`) with a single `user_context_from_state(state: dict, default_role: str = "borrower") -> UserContext` function. All 6 modules import from there.

### [CR-02] Severity: Warning
**File(s):** `packages/api/src/agents/decision_tools.py:309-322`, `decision_tools.py:429-442`, `decision_tools.py:584-597`
**Finding:** The "get primary borrower name" pattern is copy-pasted 3 times within `decision_tools.py` (in `uw_draft_adverse_action`, `uw_generate_le`, `uw_generate_cd`). Each instance is 13 lines: query `ApplicationBorrower` where `is_primary`, then query `Borrower` by ID. This is also structurally identical to code in `services/document.py:192`, `services/intake.py:151`, and `services/compliance/hmda.py:250`.
**Recommendation:** Extract a `get_primary_borrower_name(session, application_id) -> str` helper. The 3 copies in `decision_tools.py` become one-liners. The service-layer copies can adopt the same helper later.

### [CR-03] Severity: Warning
**File(s):** `packages/api/src/agents/decision_tools.py:447-466`, `decision_tools.py:602-621`
**Finding:** The mortgage payment calculation (amortization formula + rate/term extraction from loan type) is duplicated between `uw_generate_le` and `uw_generate_cd`. Both compute `monthly_rate`, `num_payments`, and `monthly_payment` identically. The closing cost structure is also nearly identical (LE uses `recording_fees=150`, CD uses `recording_fees=175` plus `transfer_tax`).
**Recommendation:** Extract a `_compute_loan_terms(app, rate_lock) -> LoanTerms` helper that returns rate, term, monthly payment, and optionally closing costs with a `final=True` flag for the CD variant.

### [CR-04] Severity: Warning
**File(s):** `packages/api/src/agents/decision_tools.py:633-634`
**Finding:** `closing_date` is set to `datetime.now(UTC).strftime(...)` -- i.e., today's date. This means the "Closing Date" on the CD is always the current date, which is misleading. In practice, the closing date should come from `app.closing_date` (which the TRID compliance check already references), not be fabricated as today.
**Recommendation:** Use `app.closing_date` if available, falling back to a "TBD" label. This also makes the generated CD consistent with TRID check expectations.

### [CR-05] Severity: Warning
**File(s):** `packages/api/src/agents/decision_tools.py:569-576`, `services/decision.py:121-126`, `agents/condition_tools.py:282-287`
**Finding:** The "count outstanding conditions" calculation -- summing `counts.get("open", 0) + counts.get("responded", 0) + counts.get("under_review", 0) + counts.get("escalated", 0)` -- is repeated in 3 locations. If a new condition status is added, all 3 must be updated in sync, which is fragile.
**Recommendation:** Add an `outstanding_count` computed property or helper to the condition summary dict (or return it from `get_condition_summary` directly). Callers check one field instead of recomputing.

### [CR-06] Severity: Warning
**File(s):** `packages/api/src/agents/underwriter_tools.py:148-155`, `underwriter_tools.py:471-478`, `underwriter_tools.py:631-638`, `agents/compliance_check_tool.py:124-130`
**Finding:** `from db import ApplicationFinancials` and `from sqlalchemy import select` are imported inside tool function bodies rather than at module top level. These deferred imports appear in 4 tool functions across 2 files. There is no circular dependency justification for deferring them -- `db` and `sqlalchemy` are already imported at module level in these files for other symbols.
**Recommendation:** Move these imports to the module top level alongside the existing `from db.database import SessionLocal` and `from sqlalchemy import select` imports. Deferred imports should only be used when there is a genuine circular import risk.

### [CR-07] Severity: Warning
**File(s):** `packages/api/src/agents/underwriter_tools.py` (756 lines), `borrower_tools.py` (728 lines), `decision_tools.py` (701 lines)
**Finding:** Three tool files exceed 700 lines each. `underwriter_tools.py` is the largest at 756 lines. The pre-Phase 3 review flagged `borrower_tools.py` at 715 lines as needing splitting. Instead of shrinking, it stayed roughly the same, and two new files (`underwriter_tools.py`, `decision_tools.py`) joined it in the 700+ line range. Phase 5 will add executive dashboard tools, further increasing this pressure.
**Recommendation:** Split by domain concern. For `decision_tools.py`: the LE/CD generation tools (~300 lines) are document generators, not decision logic -- move to `disclosure_tools.py`. For `underwriter_tools.py`: risk assessment + preliminary recommendation (~350 lines) are analysis tools that could live in `risk_tools.py`. This keeps each module under 400 lines.

### [CR-08] Severity: Warning
**File(s):** `packages/api/src/agents/underwriter_tools.py:129-280` (`uw_application_detail`)
**Finding:** `uw_application_detail` is a 152-line tool function that queries 5 different data sources (application, financials, documents, conditions, rate lock), then formats all results into a single text output. This is a "god function" -- it does too much in one place and is hard to test.
**Recommendation:** Extract the formatting into a separate pure function `_format_application_detail(app, financials, documents, conditions, rate_lock) -> str`. The tool function handles only DB queries and calls the formatter. This enables unit testing the output format without mocking DB sessions.

### [CR-09] Severity: Suggestion
**File(s):** `packages/api/src/services/compliance/knowledge_base/search.py:21`, `agents/compliance_tools.py:27`
**Finding:** `_TIER_LABELS = {1: "Federal Regulation", 2: "Agency Guideline", 3: "Internal Policy"}` is defined identically in two files. Minor duplication, but the labels are a domain concept that should have a single source of truth.
**Recommendation:** Define once in `services/compliance/knowledge_base/search.py` (where the data model lives) and import in `compliance_tools.py`.

### [CR-10] Severity: Suggestion
**File(s):** `packages/api/src/agents/loan_officer_tools.py:160-168`, `loan_officer_tools.py:209-218`, `services/completeness.py:255-259`
**Finding:** `quality_flags` JSON parsing logic (try `json.loads`, check if list, fallback) is repeated in 3 places with slight variations. The `condition.py:32-42` module already has a `_parse_quality_flags()` helper that handles this correctly.
**Recommendation:** Use the existing `_parse_quality_flags()` from `condition.py`, or better, promote it to a shared utility (e.g., `services/_utils.py`) since it is needed by completeness, loan officer tools, and condition service.

### [CR-11] Severity: Warning
**File(s):** `packages/api/src/routes/_chat_handler.py:119-132`
**Finding:** The `_audit` inner function uses `async for db_session in get_db()` to manually iterate the DB session generator. This was flagged in the Phase 1 review and the pre-Phase 3 review as an inconsistent session pattern. Every other service and route uses `Depends(get_db)` or `SessionLocal()` context manager. The manual generator iteration is error-prone (doesn't guarantee cleanup on exception within the loop body) and inconsistent with the codebase pattern.
**Recommendation:** Replace with `async with SessionLocal() as session:` which is the established pattern in all tool modules. This is the 3rd review flagging this pattern -- it should be promoted to a project rule per review-governance.md repeat pattern detection.

### [CR-12] Severity: Warning
**File(s):** `packages/api/src/routes/borrower_chat.py`, `loan_officer_chat.py`, `underwriter_chat.py`
**Finding:** The three authenticated chat route files (`borrower_chat.py`, `loan_officer_chat.py`, `underwriter_chat.py`) are nearly identical -- ~60 lines each with only the agent name, role, and route path differing. This is textbook boilerplate duplication. Each new persona chat endpoint in Phase 5 (CEO) will add yet another copy.
**Recommendation:** Create a factory function in `_chat_handler.py`:
```python
def create_chat_router(agent_name: str, required_role: UserRole, path_prefix: str) -> APIRouter:
```
Each persona file reduces to a one-liner. This was implicitly predicted in the pre-Phase 3 review when `build_graph()` duplication was flagged.

### [CR-13] Severity: Suggestion
**File(s):** `packages/api/src/services/decision.py:375-402` (`get_latest_decision`)
**Finding:** The docstring for `get_latest_decision` is confusing:
```python
"""...Returns None if application not found / out of scope, or if
no decisions exist (returns empty dict is NOT correct -- we return None
for not-found, and a dict or None-when-empty)."""
```
But the actual code returns `{"no_decisions": True}` when no decisions exist (line 400), not `None`. The docstring contradicts itself and the implementation. The `{"no_decisions": True}` sentinel is also unusual -- callers have to check for a magic key rather than a clean None vs dict distinction.
**Recommendation:** Clarify the API: return `None` for "application not found" and `{"no_decisions": True}` for "no decisions exist" (current behavior), but update the docstring to accurately describe this. Alternatively, use a more explicit return type (e.g., a discriminated union or separate function).

### [CR-14] Severity: Warning
**File(s):** `packages/api/src/services/compliance/checks.py:52-68` (`_business_days_between`)
**Finding:** `_business_days_between` iterates day-by-day from start to end. For large date ranges (e.g., checking TRID compliance on an application that has been open for months), this creates unnecessary iterations. More importantly, the function imports `timedelta` inside the function body rather than at module level.
**Recommendation:** Use a mathematical approach: compute total days, subtract weekends algebraically. Also move the `from datetime import timedelta` import to the module top (line 3 already imports `datetime`).

### [CR-15] Severity: Warning
**File(s):** `packages/api/src/agents/decision_tools.py:398` (`uw_draft_adverse_action audit`)
**Finding:** The audit event for adverse action notice stores `"decision_id": decision_id` where `decision_id` is the parameter passed to the tool -- which may be `None` (if auto-finding the latest denial). But the actual decision used is `dec` (queried from DB). The audit should store `dec.id` to accurately record which decision was used.
**Recommendation:** Change line 398 from `"decision_id": decision_id` to `"decision_id": dec.id`.

### [CR-16] Severity: Suggestion
**File(s):** `packages/api/src/agents/decision_tools.py:15`, `agents/compliance_check_tool.py:17`
**Finding:** Both files import `DocumentType` from `db.enums` but `decision_tools.py` never uses it. In `compliance_check_tool.py`, `DocumentType` is used. `decision_tools.py` also imports `UTC` and `datetime` from `datetime` at the top level but then re-uses them in functions that also do inline imports of `select` -- the inconsistency is jarring.
**Recommendation:** Remove unused imports. Run `ruff check --select F401` to catch all unused imports across the codebase.

### [CR-17] Severity: Suggestion
**File(s):** `packages/api/src/agents/underwriter_tools.py:292-405` (`_compute_risk_factors`)
**Finding:** `_compute_risk_factors` is a 113-line pure function that computes 5 risk factors plus compensating factors. It returns a deeply nested dict with inconsistent structure -- each factor has `{"value": ..., "rating": ...}` but `compensating_factors` is a `list[str]` and `warnings` is a `list[str]`. The function is testable (pure), but the return type is untyped and hard to reason about.
**Recommendation:** Define a `RiskAssessment` dataclass or TypedDict for the return value. This documents the shape and enables IDE autocomplete for callers. Since this is pure logic, the type is especially valuable.

### [CR-18] Severity: Suggestion
**File(s):** `packages/api/src/services/urgency.py:237`, `urgency.py:257`
**Finding:** In `_batch_open_condition_counts` and `_batch_oldest_pending_docs`, the enum values are converted via list comprehension `[s.value for s in _RESOLVED_STATUSES]` and `[s.value for s in _PENDING_DOC_STATUSES]`. If the DB column stores enum instances rather than raw strings, these `.value` calls are correct. But this pattern is fragile -- it depends on knowing whether SQLAlchemy stores the enum as its value or instance. The urgency module and condition module use different conventions for this.
**Recommendation:** Verify and document whether `.value` is needed for `status.in_()` / `status.notin_()` clauses in this codebase's SQLAlchemy configuration. If it is always needed, add a comment; if it is sometimes not needed, standardize.

### [CR-19] Severity: Suggestion
**File(s):** `packages/api/src/agents/borrower_tools.py:349-363` (`disclosure_status`)
**Finding:** `from ..services.disclosure import _DISCLOSURE_BY_ID` appears twice inside a loop (lines 351 and 361). The underscore prefix conventionally denotes a private symbol, and importing it from within a loop body is both wasteful and inconsistent with the `acknowledge_disclosure` tool (line 293) which imports it at function top.
**Recommendation:** Move the import to the function top (or module top) and import once. If `_DISCLOSURE_BY_ID` is needed by multiple callers, consider dropping the underscore prefix and making it part of the module's public API.

### [CR-20] Severity: Warning
**File(s):** `packages/api/src/agents/condition_tools.py:58`, `condition_tools.py:111`, `condition_tools.py:141`, `condition_tools.py:183`, `condition_tools.py:221`, `condition_tools.py:257`
**Finding:** All 6 condition tools use `state: Annotated[dict, InjectedState] = None` with a default of `None`. This default is misleading -- `InjectedState` means LangGraph will always inject the state dict; `None` should never be reached at runtime. Using `= None` suggests the parameter is optional, which contradicts the `InjectedState` annotation and could mask bugs if the tool is called outside a graph context.
**Recommendation:** Remove the `= None` defaults. If a tool is called without state injection, it should fail loudly rather than silently produce a `_user_context_from_state(None)` which would crash at `None.get("user_id")` anyway. The same pattern exists in `decision_tools.py` (4 occurrences).

### [CR-21] Severity: Warning
**File(s):** `packages/api/src/services/application.py:187-193` (`transition_stage`)
**Finding:** `transition_stage` raises `HTTPException` directly from the service layer. Service functions should be framework-agnostic -- they return error indicators (None, error dicts, custom exceptions) and let the route layer translate to HTTP responses. This is the only service function that raises `HTTPException`; all others return `None` or `{"error": ...}`.
**Recommendation:** Raise a domain exception (e.g., `ValueError` or a custom `InvalidTransitionError`) and catch it in the route handler to raise `HTTPException`. This keeps the service layer testable without importing FastAPI.

### [CR-22] Severity: Suggestion
**File(s):** `packages/api/src/routes/applications.py:274-282` (`list_conditions`)
**Finding:** The conditions endpoint builds a `Pagination` object with `total=len(result)`, `offset=0`, `limit=len(result)`, `has_more=False`. This means conditions are always returned as a single unpaginated page, making the `Pagination` wrapper misleading. Real pagination parameters (`offset`, `limit` query params) are not accepted by the endpoint.
**Recommendation:** Either add real pagination support (consistent with other list endpoints) or return a simpler response without the `Pagination` wrapper to avoid suggesting pagination is supported.

### [CR-23] Severity: Suggestion
**File(s):** across 15 files in `packages/api/src/`
**Finding:** The `.replace('_', ' ').title()` pattern for formatting enum values into display labels appears ~15 times across the codebase (agents and services). This is a presentation concern scattered throughout business logic.
**Recommendation:** Create a `format_enum_label(value: str) -> str` utility. While each occurrence is small, centralizing it would make format changes (e.g., custom labels for specific values) easier to apply consistently.

### [CR-24] Severity: Critical
**File(s):** `packages/api/src/agents/decision_tools.py:527`, `decision_tools.py:683`
**Finding:** In `uw_generate_le` (line 527) and `uw_generate_cd` (line 683), the tool mutates the ORM application object directly (`app.le_delivery_date = datetime.now(UTC)`, `app.cd_delivery_date = datetime.now(UTC)`) then calls `session.commit()`. However, the `app` object was loaded via `get_application()` which applies `selectinload` for borrowers. After `session.commit()`, the session's identity map is cleared and the `app` object enters the "expired" state. Because the mutation + commit happens inside the `async with SessionLocal() as session:` block, the commit does persist the date. But the format output section (lines after commit) references `app.property_address` and other fields -- if those attributes were not accessed before the commit, accessing them after commit on an expired object would trigger `MissingGreenlet` in async SQLAlchemy. Currently this works because `app.property_address` is accessed in the line-building before the commit, but the pattern is fragile: any reordering of the format output to after the commit would break. The `uw_application_detail` tool (line 161-162) explicitly calls out this risk with a `# Format output before commit` comment, but `uw_generate_le` and `uw_generate_cd` do not follow this discipline.
**Recommendation:** Move the date mutation + commit to after all attribute reads, or capture all needed app fields into local variables before committing. Add the same defensive comment that `uw_application_detail` uses.

### [CR-25] Severity: Suggestion
**File(s):** `packages/api/src/agents/registry.py:56-94` (`get_agent`)
**Finding:** The `get_agent` function rebuilds graphs based on YAML config mtime, but it does not incorporate the `checkpointer` argument into the cache key. If the same agent is requested first with `checkpointer=None` and then with a real checkpointer, the cached graph (without checkpointer) is returned. The current code works because each chat endpoint always passes the same checkpointer state, but this is an implicit assumption.
**Recommendation:** Either incorporate the checkpointer identity into the cache key, or document the assumption that the checkpointer for a given agent name is stable within a process lifetime.

### [CR-26] Severity: Suggestion
**File(s):** `packages/api/src/services/condition.py:1-86` (`get_conditions`)
**Finding:** `get_conditions` returns `list[dict]` (a list of hand-built dicts), while the Pydantic schema `ConditionItem` exists in `schemas/condition.py`. The route layer (`applications.py:310`) has to manually convert: `ConditionItem(**result)`. Service functions for decisions (`_decision_to_dict`) follow the same dict-based pattern. This creates a parallel schema -- one in Pydantic, one in manual dict construction -- that must be kept in sync.
**Recommendation:** Have service functions return Pydantic model instances directly (or ORM objects that the route layer serializes). This is a codebase-wide pattern issue (not just conditions), but conditions are the clearest example since the schema already exists.

### [CR-27] Severity: Suggestion
**File(s):** `packages/api/src/services/completeness.py:37-168` (`DOCUMENT_REQUIREMENTS`)
**Finding:** The `DOCUMENT_REQUIREMENTS` dict spans 130 lines with significant redundancy. Multiple loan types have identical requirement lists for the same employment status (e.g., `self_employed` requirements for `fha`, `va`, `jumbo`, `usda` are all `[TAX_RETURN, BANK_STATEMENT, ID]`). This makes adding a new document type or employment status error-prone.
**Recommendation:** Factor out common requirement sets as named constants (e.g., `_SELF_EMPLOYED_BASE = [TAX_RETURN, BANK_STATEMENT, ID]`) and compose the dict from those. Reduces 130 lines to ~40 and makes the overlaps explicit.

### [CR-28] Severity: Warning
**File(s):** `packages/api/src/agents/underwriter_tools.py:80-85` (`uw_queue_view` sort)
**Finding:** `uw_queue_view` sorts applications by urgency using `applications.sort(key=sort_key)` which mutates the list returned from `list_applications`. This is safe currently because the list is local, but it depends on `list_applications` returning a mutable list (not a tuple or generator). More importantly, the `sort_key` lambda returns `99` as a fallback when no urgency indicator exists, but `UrgencyLevel` enum values are strings (`"critical"`, `"high"`, etc.), not integers. The sort is comparing `UrgencyLevel.value` (which is a string from `StrEnum`) with the integer `99`. This works in CPython because string < int comparisons fail silently in `min()`/sort, but it is semantically wrong.
**Recommendation:** Use consistent types in the sort key. Since `UrgencyLevel` values are strings, use the `_URGENCY_ORDER` mapping pattern from `routes/applications.py:78-83` instead: `_URGENCY_ORDER.get(indicator.level, 99)`.

### [CR-29] Severity: Suggestion
**File(s):** `packages/api/src/agents/underwriter_tools.py:81-83`
**Finding:** The `sort_key` function is defined as a `def` inside the `async` tool function body. Python closures in async contexts are fine, but naming it `sort_key` is generic. More importantly, the sort sorts by `indicator.level.value` which is a `StrEnum` value -- the `.value` attribute of `UrgencyLevel.CRITICAL` is `"critical"`. Sorting strings alphabetically gives: `"critical" < "high" < "medium" < "normal"` which happens to be the correct urgency order by coincidence (alphabetical order matches severity). This will break if any urgency level is renamed.
**Recommendation:** Use an explicit integer mapping as described in CR-28. Do not rely on alphabetical ordering of enum values matching semantic ordering.

### [CR-30] Severity: Warning
**File(s):** `packages/api/src/agents/decision_tools.py:15` (unused import)
**Finding:** `decision_tools.py` imports `from datetime import UTC, datetime` at the top level, which is correct. However, it also has an unused import `from db.enums import DecisionType, UserRole` where `DecisionType` is used but this module also conditionally constructs SQL queries that could benefit from the imports being organized. More critically, the file imports `from db import ApplicationBorrower, AuditEvent, Borrower, Decision` (line 18) -- `AuditEvent` is used only in `_compliance_gate`, and `ApplicationBorrower` + `Borrower` are used only in the LE/CD borrower name lookup. These are legitimate imports but the file's import section suggests it knows too much about the DB layer for a "tools" module.
**Recommendation:** This finding reinforces CR-07 (file too large). When LE/CD generation is extracted to its own module, the DB imports will naturally separate. No immediate action needed beyond the split recommended in CR-07.
