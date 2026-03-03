# Orchestrator Review -- Pre-Phase 5

**Reviewer:** orchestrator (main session)
**Date:** 2026-02-27
**Scope:** Cross-cutting concerns across Phases 1-4

## Findings

### [OR-01] Severity: Warning
**Component(s):** `agents/decision_tools.py`, `agents/condition_tools.py`, `agents/underwriter_tools.py`, `agents/loan_officer_tools.py`, `agents/borrower_tools.py`, `agents/compliance_check_tool.py`
**Finding:** `_user_context_from_state()` is duplicated identically in 7 separate tool modules (decision_tools, condition_tools, underwriter_tools, loan_officer_tools, borrower_tools, compliance_check_tool). Each copy builds a `UserContext` from `state` dict with the same logic. This is the most replicated function in the codebase.
**Recommendation:** Extract to a shared `agents/tools.py` or `agents/_tool_utils.py` module and import across all tool files. Single point of change if the state schema evolves.

### [OR-02] Severity: Warning
**Component(s):** `agents/decision_tools.py:310,430,585`
**Finding:** Borrower name lookup pattern (query `ApplicationBorrower` -> `Borrower` -> format name) is repeated 3 times within `decision_tools.py` alone (in `uw_draft_adverse_action`, `uw_generate_le`, `uw_generate_cd`). Similar patterns exist in other tool modules.
**Recommendation:** Extract a `_get_primary_borrower_name(session, application_id)` helper function within the module or in a shared utility.

### [OR-03] Severity: Warning
**Component(s):** `agents/decision_tools.py:448-465,603-620`
**Finding:** Monthly payment calculation (amortization formula) is duplicated between `uw_generate_le` and `uw_generate_cd`. Both tools compute `monthly_rate`, `num_payments`, and the standard amortization formula identically.
**Recommendation:** Extract to a shared `_calculate_monthly_payment(loan_amount, rate, term_years)` helper.

### [OR-04] Severity: Suggestion
**Component(s):** `services/decision.py`, `services/condition.py`
**Finding:** Decision and condition services return plain `dict` objects instead of typed Pydantic response models. This is inconsistent with the rest of the codebase where schemas define the contract. The `_decision_to_dict()` and condition dict construction in `get_conditions()` manually build dictionaries that mirror what a Pydantic `model_dump()` would produce.
**Recommendation:** Low priority for MVP, but noting for Phase 5 -- when CEO dashboard aggregates these, typed response objects will prevent shape drift.

### [OR-05] Severity: Warning
**Component(s):** `plans/technical-debt.md` (Pre-Phase 3 section)
**Finding:** Several pre-Phase 3 tech debt items remain unaddressed despite Phase 3 being complete:
- D2: WebSocket rate limits (still none)
- D7: Unbounded conversation history (still no cap)
- D16: Agent registry stats filesystem on every message (still stats every call)
- D17: Fragile `Path(__file__).parents[4]` resolution (still hardcoded)
- D18: DB package reads `os.environ` directly vs pydantic-settings (still divergent)

These were explicitly gated as "pre-Phase 3" but were not addressed. The technical debt document should be updated to re-gate these items appropriately (pre-Phase 5 or pre-production).
**Recommendation:** Re-classify D2, D7, D16, D17, D18 in technical-debt.md. D2/D7 are pre-production concerns. D16/D17 are minor cleanup. D18 is architectural consistency.

### [OR-06] Severity: Warning
**Component(s):** `plans/technical-debt.md` (D8)
**Finding:** D8 states "`verify_aud` disabled in JWT validation" but `middleware/auth.py:107` now has `"verify_aud": True` with `audience=settings.KEYCLOAK_CLIENT_ID`. This item has been resolved but is not listed in the Resolved table at the bottom of the tech debt file.
**Recommendation:** Move D8 to the Resolved table. Similarly, verify whether D10 (audit event_data Text vs JSONB) is resolved -- the model now uses `Column(JSON)` which maps to JSONB in PostgreSQL.

### [OR-07] Severity: Suggestion
**Component(s):** `routes/underwriter_chat.py`, `routes/loan_officer_chat.py`, `routes/borrower_chat.py`, `routes/chat.py`
**Finding:** All 4 chat endpoints follow an identical pattern: accept WS -> authenticate -> get conversation service -> get agent -> build thread_id -> call run_agent_stream. The boilerplate is consistent but could be reduced. Each file is ~60-80 lines with only the agent name and required role varying.
**Recommendation:** Consider a factory function that generates chat WebSocket handlers given an agent name and required role. Low priority -- the current pattern is readable and consistent.

### [OR-08] Severity: Warning
**Component(s):** `services/decision.py:37-53`, `agents/decision_tools.py:50-81`
**Finding:** AI recommendation lookup queries audit events by `event_type == "tool_call"` and looks for `tool == "uw_preliminary_recommendation"` in event_data. This creates a hidden coupling between the decision service and the specific audit event format written by underwriter_tools. If the tool name or audit event structure changes, the recommendation lookup silently returns None.
**Recommendation:** Either: (a) store the AI recommendation in a dedicated column on the Application model when the tool runs, or (b) use a constant for the tool name and document the coupling.

### [OR-09] Severity: Warning
**Component(s):** `services/audit.py:60`, `services/audit.py:63-65`
**Finding:** The audit hash chain uses `pg_advisory_xact_lock` for serialization and queries the last event by `id DESC`. Under high concurrent write load, this serializes all audit writes across the entire system (not just per-application). While acceptable for MVP demo load, this becomes a bottleneck as usage scales.
**Recommendation:** Document as a known scaling limitation. For Phase 5, if CEO dashboards trigger many audit reads alongside writes, monitor for lock contention. Long-term: partition hash chain per-application.

### [OR-10] Severity: Suggestion
**Component(s):** Agent architecture (all 4 agents)
**Finding:** Phase 5 will add a CEO agent. The current 4 agents (public, borrower, LO, UW) all follow the same pattern: YAML config + Python module with `build_graph()` + tools module. The registry supports this cleanly. However, the CEO agent will likely need read-only aggregate queries (pipeline metrics, decision stats, compliance summaries) that don't exist yet. None of the current services provide aggregate/analytics query patterns.
**Recommendation:** Plan Phase 5 service layer additions early -- the CEO persona needs aggregate query patterns (counts, averages, distributions) that differ from the CRUD+action patterns used by current services.

### [OR-11] Severity: Suggestion
**Component(s):** `middleware/auth.py:137-150` (build_data_scope)
**Finding:** CEO data scope already defined: `DataScope(pii_mask=True, document_metadata_only=True, full_pipeline=True)`. This means the CEO agent infrastructure is partially pre-built. However, no service functions currently respect `document_metadata_only` -- the flag exists but isn't checked anywhere.
**Recommendation:** Verify that `document_metadata_only` is enforced in the document service before Phase 5 CEO agent implementation. If it's not enforced, the CEO could see full document contents despite the flag.

### [OR-12] Severity: Warning
**Component(s):** `agents/decision_tools.py:50-81` (`_compliance_gate`)
**Finding:** The compliance gate in decision_tools queries audit events to check for a passing compliance check. This duplicates compliance state checking -- the compliance_check_tool already writes this audit event, and the decision service could check for it. But the gate lives in the tool layer, not the service layer, meaning any non-agent path to render a decision (e.g., a future REST endpoint) would bypass the compliance gate.
**Recommendation:** Move the compliance gate check into `services/decision.py:_resolve_decision()` so it's enforced regardless of entry point. The tool can still format the error message, but the business rule should be in the service.

### [OR-13] Severity: Suggestion
**Component(s):** HMDA isolation
**Finding:** HMDA schema isolation remains intact after Phase 4. The `hmda.py` route, `seed_hmda.py`, and HMDA service all use the separate `hmda` schema. No Phase 3-4 code introduces new paths to demographic data. The `check_ecoa()` compliance function correctly operates on a boolean flag rather than accessing demographic data directly. The architectural boundary is sound.
**Recommendation:** No action needed. Confirming the isolation is maintained.

### [OR-14] Severity: Warning
**Component(s):** `services/decision.py:283` (`denial_reasons`)
**Finding:** `denial_reasons` is stored as a JSON-encoded string via `json.dumps()` in the Decision model column, then parsed back via `json.loads()` in `_decision_to_dict()`. This is a fragile serialization pattern -- a proper JSON/JSONB column would be more appropriate. If someone stores a malformed string, the fallback `[d.denial_reasons]` wraps it in a list silently.
**Recommendation:** Change the `denial_reasons` column to JSON/JSONB type (like `event_data` on AuditEvent). This avoids the manual json.dumps/loads dance and the fragile fallback.
