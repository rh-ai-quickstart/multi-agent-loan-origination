# Project Manager Pre-UI Review

**Reviewer:** Project Manager
**Date:** 2026-03-02
**Scope:** Phase 5 story implementation status, planning doc accuracy, API contract
stability, and frontend readiness gaps

---

## Methodology

Reviewed `plans/requirements.md`, `plans/requirements-chunk-5-executive.md`,
`plans/technical-debt.md`, and `plans/deferred/f38-trustyai-fairness-metrics.md`
against actual implementation in `packages/api/src/routes/`, `packages/api/src/agents/`,
and `packages/api/src/services/`. Checked the known-deferred list first and skipped all
items listed there.

---

## Critical

### PJ-01: requirements.md Feature Coverage table marks F38 and F26 as complete despite both being deferred

**Location:** `plans/requirements.md` lines 511 and 514

The Feature Coverage table at the bottom of `requirements.md` shows:

```
| F26 | Agent adversarial defenses | ... | ✓ |
| F38 | TrustyAI fairness metrics | ... | ✓ |
```

Both F26 and F38 are explicitly deferred and documented as such in
`plans/technical-debt.md` and `plans/deferred/f38-trustyai-fairness-metrics.md`. Marking
them ✓ as complete creates a false picture of project status for anyone reading the
requirements hub without also reading the technical debt doc.

**Why this is critical:** Any team onboarding (including a frontend team) that reads
`requirements.md` to understand project status will conclude the full feature set is
implemented. The fair lending dashboard section specifically (F12-03, F13-09) has no
backend implementation and no endpoint -- a frontend team building that UI panel will hit
a dead end immediately.

**Fix:** Update the Feature Coverage table to reflect actual implementation status.
Change the ✓ for F26 and F38 to a "Deferred" marker. Add a note column or footnote
explaining the deferral rationale and pointing to the deferred plan files.

---

### PJ-02: S-5-F12-03 and S-5-F13-09 have no backend implementation (fairness dependency gap)

**Location:** `packages/api/src/routes/analytics.py`, `packages/api/src/agents/ceo_tools.py`

S-5-F12-03 (CEO views fair lending metrics: SPD, DIR) and S-5-F13-09 (CEO asks fair
lending questions conversationally) both depend on F38 (TrustyAI fairness metrics).
F38 is deferred. As a result:

- There is no `/api/analytics/fairness` or equivalent endpoint in `analytics.py`
- There is no fairness tool (e.g., `ceo_fairness_metrics`) in `ceo_tools.py` or
  `ceo_assistant.py`
- The CEO chat agent has no mechanism to answer fair lending questions conversationally
- The CEO dashboard API has no data source for SPD/DIR metrics

The requirements hub lists both stories as P0 and marks F12 and F13 as ✓ complete,
creating a direct contradiction with the deferral.

**Why this is critical:** A frontend team implementing the CEO dashboard will find no API
endpoint to power the fair lending metrics panel. If this panel is included in the UI
design, it will break on first render. If it is excluded, that exclusion needs to be
explicitly communicated and reflected in updated planning docs.

**Fix:** Either implement a stub fairness endpoint that returns "Insufficient data"
(keeping the UI panel renderable with a deferred-feature notice), or explicitly mark
S-5-F12-03 and S-5-F13-09 as deferred in the requirements map and communicate this to
the frontend team before they begin the CEO dashboard. The deferred stub approach is
preferable because it prevents the frontend from having to handle a missing endpoint vs.
an empty response.

---

## Warning

### PJ-03: S-5-F13-07 (comparative analytics) has no dedicated tool; LLM-only implementation may be unreliable

**Location:** `packages/api/src/agents/ceo_tools.py`, `packages/api/src/agents/ceo_assistant.py`

S-5-F13-07 requires: when the CEO asks "What is our pull-through rate this quarter vs.
last?", the agent "calculates pull-through rate for the current quarter and the previous
quarter and presents both with the delta." The acceptance criteria specifies a structured
response format including percentage, counts, and delta.

The current tool set only includes `ceo_pipeline_summary(days: int)` which returns data
for a single time window. To answer a comparative question, the LLM would need to make
two sequential tool calls with different `days` parameters and then compute the delta
itself. This pattern is:

1. Not guaranteed -- LLMs may answer from one period's data only
2. Not tested -- `test_ceo_tools.py` has no comparative query test
3. Dependent on the LLM correctly identifying and computing calendar quarter boundaries
   from a `days` integer parameter

The `get_pipeline_summary` service function also does not accept a `start_date` /
`end_date` range, only a trailing `days` window, making precise quarter-aligned
comparisons structurally impossible (Q1 2025 vs Q4 2024 cannot be expressed as two
trailing-days windows without calendar math the LLM must perform correctly).

**Fix:** Add a `ceo_comparative_summary(period_a_days: int, period_b_days: int)` tool,
or extend `get_pipeline_summary` to accept an explicit date range, with a corresponding
tool wrapper. Without a structured comparative tool, this story's acceptance criteria
cannot be reliably met.

---

### PJ-04: Audit event_data PII masking (S-5-F13-04) is middleware-only -- Audit Service layer masking is absent

**Location:** `packages/api/src/middleware/pii.py`, `packages/api/src/services/audit.py`

S-5-F13-04 specifies: "masking is applied at the **Audit Service layer** (not in the
agent layer), ensuring defense in depth." The current implementation applies PII masking
only via `PIIMaskingMiddleware` at the HTTP response layer -- there is no Audit Service
layer masking for event_data JSONB content.

The middleware's `_mask_pii_recursive` walks the JSON response body and masks keys named
`ssn`, `dob`, `account_number`. This works for top-level fields in structured response
schemas, but audit `event_data` is an unstructured JSONB blob that may contain sensitive
data under arbitrary keys (e.g., `{"parameters": {"ssn": "...", "applicant_ssn": "..."},
"result": {...}}`). The middleware will catch `ssn` but not `applicant_ssn` or similar
non-standard keys written by tool implementations.

The acceptance criterion "the event_data JSONB field in audit events is filtered to
remove or mask sensitive fields before being returned to the CEO" implies service-layer
filtering of the JSONB payload, not just response-body field masking.

**Fix:** Add a pass in `get_events_by_application`, `search_events`, etc. that sanitizes
`event_data` for CEO role responses -- at minimum normalizing known-sensitive keys before
they are serialized into the API response. Alternatively, document the accepted scope of
the middleware approach and update S-5-F13-04 acceptance criteria to reflect what is
actually enforced.

---

### PJ-05: requirements.md Story Map includes F26 stories as P0 with no deferral marker

**Location:** `plans/requirements.md` lines 126-129

The Story Map table lists S-4-F26-01 through S-4-F26-04 as P0 stories with no
indication they are deferred. The deferral rationale (Llama Guard already provides
stronger protection than regex-based detection) is documented only in
`plans/technical-debt.md`. A reader of the requirements hub sees four P0 stories with no
implementation status information.

**Fix:** Add a "Status" column to the Story Map table, or add a note row after the F26
stories indicating they are deferred (with a pointer to technical-debt.md). Same
treatment for F38 stories (lines 130-133).

---

## Suggestion

### PJ-06: Demo seed data demographic distribution should be confirmed before F38 is picked up

**Location:** `plans/requirements.md` REQ-OQ-06, `packages/api/src/services/seed/fixtures.py`

REQ-OQ-06 flags the demo data demographic distribution as an open question for F38:
"Demo data must include sufficient demographic diversity to compute meaningful SPD/DIR.
Suggested: 30% protected class representation in historical data." The open question is
marked as unresolved (no resolution documented).

F38 is deferred, but when it is picked up, the fairness metrics require a minimum of 30
decisions with HMDA demographic data before SPD/DIR are computable. If the seed data
does not meet this threshold, the CEO dashboard will display "Insufficient data" on first
demo and the fairness metrics panel will be inoperable during Summit demos.

**Fix:** Before implementing F38, verify that the seed data in
`packages/api/src/services/seed/fixtures.py` includes at least 30 historical decisions
with correlated HMDA demographic data, with sufficient demographic group diversity (at
least 5 decisions per protected group per the k-anonymity threshold). Document the
resolution to REQ-OQ-06.
