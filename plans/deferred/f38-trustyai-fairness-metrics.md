# F38: TrustyAI Fairness Metrics

## Context

Phase 4 underwriting features (F9, F10, F11, F16, F17) are complete. F26 (Agent Adversarial Defenses) was deferred -- existing Llama Guard + HMDA schema isolation + tool RBAC are stronger than what F26 adds at PoC maturity.

F38 adds fair lending metrics: Statistical Parity Difference (SPD) and Disparate Impact Ratio (DIR) computed across protected classes (race, ethnicity, sex) by comparing HMDA demographic data against underwriting decisions. TrustyAI is a stakeholder mandate.

Stories: S-4-F38-01 (SPD), S-4-F38-02 (DIR), S-4-F38-03 (threshold alerts), S-4-F38-04 (dashboard endpoint).

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Adapter pattern for TrustyAI | `trustyai` requires JPype + JVM. Pure-Python fallback ensures tests/dev work without JVM. Adapter detects at import time. |
| Dual-session query, in-memory join | Decisions live in lending session, demographics in compliance session (hmda schema). Joining in-memory preserves HMDA schema isolation -- no cross-schema SQL joins. |
| Pre-aggregation only | API exposes only aggregate SPD/DIR values + per-group counts. Never returns individual demographic-decision pairs. |
| CEO + ADMIN role restriction | Fair lending metrics are executive-level; LO/UW don't see aggregate demographic outcomes. |
| `min_sample_size=30` default | Metrics are statistically unreliable below ~30 samples per group. Groups below threshold are flagged but excluded from computation. |
| Threshold classification | SPD: green <= 0.1, yellow <= 0.2, red > 0.2. DIR: green >= 0.8, yellow >= 0.7, red < 0.7. Based on EEOC 80% rule. |

## PR Plan

Single PR on branch `feat/trustyai-fairness-metrics` covering all 4 stories.

---

## Implementation

### 1. Add TrustyAI Optional Dependency

**File:** `packages/api/pyproject.toml`

Add to `[project.optional-dependencies]`:
```toml
fairness = [
    "trustyai>=0.5.0",
]
```

No change to core `dependencies` -- TrustyAI is optional. Tests use the pure-Python fallback.

### 2. Fairness Adapter

**File:** `packages/api/src/services/compliance/fairness_adapter.py` (new, ~50 lines)

Import-time detection of TrustyAI:

```python
try:
    from trustyai.metrics.fairness.group import (
        statistical_parity_difference,
        disparate_impact_ratio,
    )
    import pandas as pd
    _HAS_TRUSTYAI = True
except ImportError:
    _HAS_TRUSTYAI = False
```

Public API:
- `compute_spd(privileged_count, privileged_favorable, unprivileged_count, unprivileged_favorable) -> float`
- `compute_dir(privileged_count, privileged_favorable, unprivileged_count, unprivileged_favorable) -> float`
- `get_engine() -> str` -- returns `"trustyai"` or `"builtin"`

When `_HAS_TRUSTYAI=True`: build DataFrame with `outcome` column (1=favorable, 0=unfavorable) and `group` column (1=privileged, 0=unprivileged), call TrustyAI's `statistical_parity_difference(privileged_df, unprivileged_df, [1])`.

When `_HAS_TRUSTYAI=False`: pure-Python arithmetic:
- SPD = `(unprivileged_favorable / unprivileged_count) - (privileged_favorable / privileged_count)`
- DIR = `(unprivileged_favorable / unprivileged_count) / (privileged_favorable / privileged_count)` with zero-division guard.

### 3. Fairness Service

**File:** `packages/api/src/services/compliance/fairness.py` (new, ~130 lines)

**Constants:**
```python
SPD_GREEN_MAX = 0.1
SPD_YELLOW_MAX = 0.2
DIR_GREEN_MIN = 0.8
DIR_YELLOW_MIN = 0.7
DEFAULT_MIN_SAMPLE = 30
FAVORABLE_DECISIONS = frozenset({DecisionType.APPROVED, DecisionType.CONDITIONAL_APPROVAL})
```

**Functions:**

| Function | Signature | Behavior |
|----------|-----------|----------|
| `compute_fairness_metrics` | `(session, compliance_session, protected_class, min_sample_size=30)` | Main entry point. Queries decisions + demographics, joins in-memory, computes SPD/DIR per group. Returns dict. |
| `_fetch_outcomes` | `(session) -> dict[int, bool]` | Query all Decisions, return `{application_id: is_favorable}`. Only latest decision per app. |
| `_fetch_demographics` | `(compliance_session, protected_class) -> dict[int, str]` | Query HmdaDemographic, return `{application_id: group_value}`. Uses primary borrower only. |
| `_classify` | `(value: float, metric: str) -> str` | Return "green"/"yellow"/"red" based on threshold constants. |

**`compute_fairness_metrics` flow:**
1. Call `_fetch_outcomes(session)` -- gets `{app_id: True/False}` from Decision table (latest per app)
2. Call `_fetch_demographics(compliance_session, protected_class)` -- gets `{app_id: "White"}`, `{app_id: "Black"}` etc.
3. Inner-join in Python: only apps with both a decision and demographic data
4. Build group stats: for each group value, count total and favorable
5. Identify reference group (largest sample) as "privileged" baseline
6. For each non-reference group: compute SPD and DIR using adapter, classify thresholds
7. Flag groups below `min_sample_size` as `insufficient_data`
8. Return structured dict with per-group metrics, reference group info, overall stats, engine used

### 4. Fairness Schema

**File:** `packages/api/src/schemas/fairness.py` (new, ~45 lines)

```python
class GroupMetrics(BaseModel):
    group: str
    total: int
    favorable: int
    unfavorable: int
    favorable_rate: float
    spd: float | None = None         # null if insufficient data
    dir: float | None = None         # null if insufficient data
    spd_status: str | None = None    # green/yellow/red
    dir_status: str | None = None
    insufficient_data: bool = False

class FairnessMetrics(BaseModel):
    protected_class: str
    reference_group: str
    total_decisions: int
    total_with_demographics: int
    engine: str
    groups: list[GroupMetrics]
    computed_at: datetime

class FairnessResponse(BaseModel):
    data: FairnessMetrics
```

### 5. Fairness Route

**File:** `packages/api/src/routes/fairness.py` (new, ~40 lines)

```python
router = APIRouter()

ALLOWED_ROLES = frozenset({UserRole.CEO, UserRole.ADMIN})
VALID_CLASSES = frozenset({"race", "ethnicity", "sex"})

@router.get("/metrics", response_model=FairnessResponse)
async def get_fairness_metrics(
    protected_class: str = Query(..., description="Protected class: race, ethnicity, or sex"),
    session: AsyncSession = Depends(get_db),
    compliance_session: AsyncSession = Depends(get_compliance_db),
    user: UserContext = Depends(get_current_user),
):
```

- Validate `user.role in ALLOWED_ROLES`, else 403
- Validate `protected_class in VALID_CLASSES`, else 422
- Call `compute_fairness_metrics(session, compliance_session, protected_class)`
- Return `FairnessResponse`

### 6. Register Router

**File:** `packages/api/src/main.py`

Add import + `app.include_router(fairness.router, prefix="/api/fairness", tags=["fairness"])`.

### 7. Unit Tests

**File:** `packages/api/tests/test_fairness.py` (new, ~20 tests)

**Adapter tests (5):**
- builtin SPD computation: known inputs -> expected value
- builtin DIR computation: known inputs -> expected value
- builtin DIR zero-division returns 0.0
- `get_engine()` returns "builtin" (no JVM in test env)
- SPD/DIR symmetry: swapping privileged/unprivileged flips SPD sign

**Classification tests (6):**
- SPD green/yellow/red thresholds
- DIR green/yellow/red thresholds

**Service tests with mocked sessions (8):**
- No decisions -> empty result
- No demographics -> total_with_demographics=0
- Insufficient sample size flagged
- Reference group is largest group
- Favorable rate computed correctly
- SPD/DIR computed for each non-reference group
- Multiple protected classes produce different groupings
- Only latest decision per application used

### 8. Integration Tests

**File:** `packages/api/tests/integration/test_fairness.py` (new, ~10 tests)

Uses existing `db_session` + `compliance_session` fixtures from integration conftest.

**Setup helper:** Insert Decision rows into `db_session`, HmdaDemographic rows into `compliance_session` (same engine in tests, but different sessions preserving the pattern).

**Tests:**
- End-to-end: 3 groups, known favorable rates -> verify SPD/DIR values
- Below min_sample_size -> insufficient_data flag
- Apps without demographics excluded from computation
- Apps without decisions excluded from computation
- API endpoint returns 403 for non-CEO/ADMIN
- API endpoint returns 422 for invalid protected_class
- API endpoint returns correct JSON structure for CEO user

## Files Summary

| File | Action | Lines |
|------|--------|-------|
| `packages/api/pyproject.toml` | Edit | +3 |
| `packages/api/src/services/compliance/fairness_adapter.py` | New | ~50 |
| `packages/api/src/services/compliance/fairness.py` | New | ~130 |
| `packages/api/src/schemas/fairness.py` | New | ~45 |
| `packages/api/src/routes/fairness.py` | New | ~40 |
| `packages/api/src/main.py` | Edit | +3 |
| `packages/api/tests/test_fairness.py` | New | ~150 |
| `packages/api/tests/integration/test_fairness.py` | New | ~120 |

## Key Files Reference

| Existing File | Role |
|---|---|
| `packages/db/src/db/models.py:232-256` | Decision model (decision_type, application_id, created_at) |
| `packages/db/src/db/models.py:409-434` | HmdaDemographic model (hmda schema: race, ethnicity, sex, application_id) |
| `packages/db/src/db/enums.py:115-119` | DecisionType enum (APPROVED, CONDITIONAL_APPROVAL, SUSPENDED, DENIED) |
| `packages/db/src/db/database.py:95-100` | `get_compliance_db()` dependency |
| `packages/api/src/middleware/auth.py` | `get_current_user` dependency |
| `packages/api/tests/functional/personas.py` | ceo(), admin() persona factories |
| `packages/api/tests/integration/conftest.py:183-204` | `db_session` + `compliance_session` fixtures |
| `packages/api/src/schemas/condition.py` | Schema pattern reference |
| `packages/api/src/routes/hmda.py` | Dual-session route pattern |

## Exit Criteria

```bash
# Unit + integration tests pass
AUTH_DISABLED=true /packages/api/.venv/bin/pytest packages/api/tests/test_fairness.py packages/api/tests/integration/test_fairness.py -v

# Lint clean
cd packages/api && uv run ruff check src/services/compliance/fairness.py src/services/compliance/fairness_adapter.py src/schemas/fairness.py src/routes/fairness.py

# Full suite still passes
AUTH_DISABLED=true /packages/api/.venv/bin/pytest -v
```
