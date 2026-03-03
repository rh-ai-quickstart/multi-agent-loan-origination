# Pre-UI Code Review

**Reviewer:** Code Reviewer
**Scope:** `packages/api/src/`, `packages/db/src/`
**Date:** 2026-03-02

## Review Summary

The codebase is generally well-structured with consistent patterns across modules. The main issues are: an inefficient route that fetches all decisions to find one by ID, a redundant `ALLOWED_CONTENT_TYPES` definition in storage.py, incorrect log level usage in observability, a double-initialization pattern in PII middleware, and several missing type annotations. No critical bugs found; the findings are primarily Warning-level efficiency and correctness issues with Suggestion-level style and type safety items.

## Findings

### Critical

(none)

### Warning

**CR-01: `get_decision` route fetches all decisions then filters in Python**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/routes/decisions.py:76-84`

The `get_decision` endpoint calls `get_decisions(session, user, application_id)` which returns ALL decisions for the application, then iterates the list in Python to find the matching `decision_id`. This is an O(n) scan that should be a single SQL query with a WHERE clause on the decision ID.

**Suggestion:** Add a `get_decision_by_id(session, user, application_id, decision_id)` function to the decision service that queries for the specific decision directly, or modify `get_decisions` to accept an optional `decision_id` filter parameter.

---

**CR-02: `ALLOWED_CONTENT_TYPES` defined redundantly in storage.py**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/services/storage.py:22-26`

`ALLOWED_CONTENT_TYPES` is defined identically in both `services/document.py:24-28` and `services/storage.py:22-26`. The `storage.py` copy is never imported or used by any other module -- the route and document service both reference the one in `document.py`. This is dead code that could drift out of sync.

**Suggestion:** Remove the `ALLOWED_CONTENT_TYPES` definition from `storage.py`. The canonical set lives in `document.py` and is imported where needed.

---

**CR-03: `log_observability_status` uses `logger.warning` for informational messages**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/observability.py:84-89`

Both the "ACTIVE" and "DISABLED" branches of `log_observability_status` emit at WARNING level. These are startup status messages, not warnings. Using the wrong log level makes it harder to filter real warnings and adds noise to monitoring dashboards.

**Suggestion:** Change both calls to `logger.info(...)`. The "DISABLED" branch could arguably stay at WARNING if the project considers it an operational concern, but "ACTIVE" is purely informational.

---

**CR-04: `_PII_FIELD_MASKERS` initialized as empty dict then reassigned**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/middleware/pii.py:25,61`

Line 25 initializes `_PII_FIELD_MASKERS` as an empty dict (`{}`), then line 61 reassigns it to the actual masker mapping. Between lines 25 and 61, any code that imported the name would get the empty dict. While there is no code path that exercises this gap today, this pattern is fragile and misleading -- it looks like the dict is populated incrementally when it is actually replaced wholesale.

**Suggestion:** Remove the empty initialization on line 25. Define `_PII_FIELD_MASKERS` once on line 61. If forward declaration is needed for type checkers, use a type annotation without assignment: `_PII_FIELD_MASKERS: dict[str, Any]`.

---

**CR-05: `_percentile` re-sorts the input list on every call**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/services/model_monitoring.py:78-89`

The function docstring says "Compute a percentile from a sorted list of values" but it calls `sorted(values)` on line 82 regardless. The callers pass pre-sorted lists, making this an unnecessary O(n log n) operation per call. When computing multiple percentiles (p50, p95, p99) on the same dataset, the list is re-sorted 3 times.

**Suggestion:** Either (a) remove the `sorted()` call and trust the caller to pass a sorted list as the docstring states, or (b) update the docstring to say the input need not be sorted and keep the `sorted()` call for safety. Option (a) is preferred since the callers already sort.

---

**CR-06: `get_lo_performance` executes 7 queries per loan officer in a loop**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/services/analytics.py:422-518`

For each loan officer, the function executes separate queries for: active count, closed count, initiated count, total decided, total denied, avg turn time, and avg condition clearance time. With N loan officers, this is 7N+1 queries total. For a demo with ~5 LOs this is acceptable, but the pattern will degrade linearly with scale.

**Suggestion:** Consolidate into batch queries using `GROUP BY assigned_to` similar to how `compute_urgency` in `services/urgency.py` batch-queries across applications. This would reduce 7N+1 queries to ~7 total queries regardless of LO count.

---

**CR-07: `condition_tools.py` imports `datetime` from stdlib but only uses it for type annotation**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/condition_tools.py:14`

`from datetime import datetime` is imported on line 14, but `datetime` is only used as a type annotation for the `parsed_due` variable on line 68 (`parsed_due: datetime | None = None`) and in the `fromisoformat` call on line 71. The `logging` import on line 13 instantiates a logger on line 32 but `logger` is never used anywhere in the file.

**Suggestion:** Remove the unused `import logging` and `logger = logging.getLogger(__name__)` lines (13, 32). Keep the `datetime` import since it is used.

---

**CR-08: `disclosure_status` tool has repeated deferred import inside loop body**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:339,348`

Lines 339 and 348 both have `from ..services.disclosure import DISCLOSURE_BY_ID` inside the loop body -- the same import is executed on every iteration of both the "acknowledged" and "pending" loops. While Python caches module imports, the repeated `from ... import` inside loops is an anti-pattern that clutters the function body.

**Suggestion:** Move the import to the top of the function (after the `user = ...` line, before the `async with` block), or ideally to the module-level imports alongside the existing `from ..services.disclosure import get_disclosure_status` on line 34.

---

### Suggestion

**CR-09: `_apply_filters` helper in application service lacks type annotations**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/services/application.py:82`

The `_apply_filters` function has no type annotations on its parameters or return type. The function signature is `def _apply_filters(stmt, ...)` with no indication of what `stmt` is (it is a SQLAlchemy `Select` statement) or what the filter parameters accept. This is the only service-layer helper function in the file without type hints.

**Suggestion:** Add type annotations: `def _apply_filters(stmt: Select, *, filter_stage: ApplicationStage | None = None, ...) -> Select:`.

---

**CR-10: `ceo_tools.py` has a `_user_context_from_state` wrapper that is functionally identical to the shared version**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/ceo_tools.py`

Every tool module defines a local `_user_context_from_state(state)` that delegates to `user_context_from_state(state, default_role="<role>")` from `shared.py`. This is a conscious design pattern (already tracked in known-deferred W-1). However, `ceo_tools.py` additionally imports from `shared.py` and defines its own wrapper without any differentiation beyond the default role string. All 6 tool modules follow this exact same pattern.

This is noted as Suggestion-level context for the record. The pattern itself is tracked in W-1.

---

**CR-11: `_business_days_between` imports `timedelta` inside the function body**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/services/compliance/checks.py:62`

Line 62 has `from datetime import timedelta` inside the function body of `_business_days_between`. The `datetime` module is already imported at the module level on line 11. The `timedelta` import should be alongside it at the top of the file for consistency and to avoid repeated import resolution on each call.

**Suggestion:** Move `timedelta` to the module-level import on line 11: `from datetime import datetime, timedelta`.

---

**CR-12: `risk_tools.py` functions accept untyped `app` and `financials_rows` parameters**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/risk_tools.py:31,147`

Both `compute_risk_factors(app, financials_rows, borrowers)` and `extract_borrower_info(app)` accept their primary arguments without type annotations. These are public functions imported by `underwriter_tools.py`. The `app` parameter is an `Application` ORM model and `financials_rows` is a list of `Borrower` objects with financial fields, but this is not evident from the signatures.

**Suggestion:** Add type annotations: `def compute_risk_factors(app: Application, financials_rows: list[Borrower], borrowers: list[dict]) -> RiskAssessment:` and `def extract_borrower_info(app: Application) -> list[dict]:`.

---

**CR-13: `disclosure_tools.py` helper functions have incomplete parameter type annotations**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/disclosure_tools.py:39,128`

`generate_le_text(session, user, app, application_id)` and `generate_cd_text(session, user, app, application_id)` have parameter annotations only in docstrings, not in the function signature. These are async functions that accept an `AsyncSession`, `UserContext`, and `Application` ORM model, but the type checker and IDE cannot infer this.

**Suggestion:** Add proper type annotations to the function signatures:
```python
async def generate_le_text(
    session: AsyncSession, user: UserContext, app: Application, application_id: int
) -> str:
```

---

**CR-14: `upload_document` returns `None` on access denied instead of raising an exception**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/services/document.py:187`

The `upload_document` function returns `None` when the application is not found or the user lacks access (line 187), but raises `DocumentUploadError` for validation failures (lines 169, 178). The return type annotation declares `-> Document` without `| None`, and the function docstring does not mention the `None` return case. This inconsistency means callers could miss the access-denied case.

**Suggestion:** Either (a) update the return type to `-> Document | None` and document it, or (b) raise `DocumentAccessDenied` or `HTTPException(404)` instead of returning `None`, consistent with how other validation failures in the same function raise exceptions.

---

**CR-15: `_SEVERITY_LABELS` dict defined in `loan_officer_tools.py` is a subset of condition severity labels**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/loan_officer_tools.py:50-55`

This mapping duplicates what could be derived from `ConditionSeverity` enum values using the existing `format_enum_label()` helper from `shared.py`. The same pattern appears in the condition_tools module with `_SEVERITY_MAP`. Having hardcoded label dicts that shadow enum values creates a maintenance risk if new severity levels are added to the enum.

**Suggestion:** Use `format_enum_label(severity_value)` from `shared.py` instead of maintaining a separate label dict, or derive the dict from the enum: `{s.value: format_enum_label(s.value) for s in ConditionSeverity}`.

---

**CR-16: `_STATUS_LABELS` dict in `borrower_tools.py` duplicates document status formatting**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/agents/borrower_tools.py:95-104`

Similar to CR-15, this is a hardcoded mapping of document status values to human-readable labels. The `DocumentStatus` enum already has values that could be formatted with `format_enum_label()`. This dict would need updating if new document statuses are added.

**Suggestion:** Use `format_enum_label(status_val)` instead of maintaining a separate lookup dict.

---

**CR-17: `run_all_checks` return type is `dict` instead of a typed structure**
`/home/jary/redhat/git/mortgage-ai/packages/api/src/services/compliance/checks.py:272-291`

`run_all_checks` returns a plain `dict` with keys `overall_status`, `checks`, and `can_proceed`. Given that the individual check functions return typed `ComplianceCheckResult` dataclasses, the combined result should also be typed for consistency and IDE support.

**Suggestion:** Define a `ComplianceReport` dataclass:
```python
@dataclass
class ComplianceReport:
    overall_status: ComplianceStatus
    checks: list[ComplianceCheckResult]
    can_proceed: bool
```

---

## Verdict

**APPROVE** -- No critical issues found. The Warning-level items (CR-01 through CR-08) should be addressed before the UI phase if time permits. CR-01 (N+1 decision fetch in route) is the highest-priority fix as it represents an unnecessary performance regression for a frequently used endpoint. The Suggestion-level items are quality improvements that can be batched.
