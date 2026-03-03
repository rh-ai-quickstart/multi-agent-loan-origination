# Pre-Phase 3 Product Review

Reviewer: Product Manager
Date: 2026-02-26
Scope: Phase 1 + Phase 2 completeness, Phase 3 prerequisites, demo readiness

---

## PROD-01: No LO Assistant agent exists -- Phase 3 has no agent foundation

**Severity:** Critical
**Description:** The agent registry (`packages/api/src/agents/registry.py`) recognizes only two agents: `public-assistant` and `borrower-assistant`. There is no `lo-assistant` (or `loan-officer-assistant`) agent, no YAML config in `config/agents/`, no WebSocket endpoint for LO chat (only `/ws/chat` for public and `/ws/borrower/chat` for borrower), and no LO-specific tool set. Phase 3 requires all three features (F7, F8, F24) to operate through an AI assistant with tools like `application_detail`, `completeness_check`, `draft_communication`, and `submit_to_underwriting`. This is not a gap in Phase 1/2 deliverables (they are correct for their scope), but it means Phase 3 starts from zero on the agent layer -- the most complex part of the LO experience.
**Reference:** Product plan F7 ("AI assistant helps with reviewing application completeness"), F8 ("LO reviews application detail in chat interface"), F24 ("LO AI assistant can draft communications"). Requirements chunk 3 S-3-F8-01 through S-3-F24-03.
**Recommendation:** Phase 3 work breakdown must explicitly include creating the LO assistant agent, its YAML config, its tool set, and a new WebSocket endpoint (e.g., `/ws/loan-officer/chat`). This is foundational work that blocks all three Phase 3 features. Estimate this as a separate story before F7/F8/F24 implementation begins.

---

## PROD-02: No application state machine enforcement

**Severity:** Critical
**Description:** The application model has a `stage` field (`ApplicationStage` enum with 10 values), but there is no state machine validation anywhere in the codebase. The `update_application` service method (`packages/api/src/services/application.py:132-150`) accepts any `stage` value in the `_UPDATABLE_FIELDS` set without validating that the transition is legal. For example, nothing prevents changing an application from `closed` back to `inquiry`, or from `application` directly to `closed`. The requirements explicitly define valid transitions: "application -> underwriting", "application -> withdrawn", "underwriting -> conditional_approval", etc. (S-3-F8-04). Phase 3's core workflow -- LO submitting to underwriting -- depends on state transition enforcement to prevent invalid transitions and to audit them correctly.
**Reference:** Requirements hub application state machine. S-3-F8-03 ("invalid state transition rejected"), S-3-F8-04 ("State transitions follow the application state machine"). Product plan F8 ("workflow transitions are functional with human-in-the-loop confirmation").
**Recommendation:** Implement a state machine validator before Phase 3 begins. This is a Phase 2 gap that was acceptable because borrower features did not exercise state transitions directly, but Phase 3 makes it critical. The validator should live in `services/application.py`, define a `VALID_TRANSITIONS` map, reject invalid transitions with a clear error, and write an audit event for every transition.

---

## PROD-03: Audit trail query endpoints are admin-only and session-based only

**Severity:** Warning
**Description:** The product plan (F15) specifies three audit query patterns: (1) application-centric -- all events for a specific application, (2) decision-centric -- all factors contributing to a specific decision, (3) pattern-centric -- aggregate queries like "all denials in past 90 days." The current implementation (`packages/api/src/routes/admin.py`) provides only session-based querying (`GET /admin/audit?session_id=...`) restricted to admin role. There is no application-centric query (`GET /audit?application_id=...`), no decision-centric query, and no pattern queries. The underwriter and CEO roles should have audit trail access per F14 but currently cannot.

The `audit.py` service has `get_events_by_session()` but no `get_events_by_application()` or similar methods. The `AuditEvent` model has `application_id` indexed, so the data model supports it, but the query endpoints do not exist.

This is Phase 4a scope (audit trail UI), but the missing query endpoints may affect Phase 3 testing if LO state transitions need to be verified through audit events.
**Reference:** Product plan F15 (three query patterns). F14 (CEO and Underwriter have audit trail access; LO/Borrower/Prospect do not).
**Recommendation:** Add at minimum an application-centric audit query endpoint before Phase 3, restricted to `underwriter`, `ceo`, and `admin` roles. Decision-centric and pattern-centric queries can wait for Phase 4a, but application-centric queries are essential for verifying Phase 3 state transitions are properly audited.

---

## PROD-04: LO data scope filtering exists but has no pipeline-specific API

**Severity:** Warning
**Description:** The RBAC data scope filtering for loan officers is correctly implemented in `middleware/auth.py` (`assigned_to=user_id`) and enforced in `services/scope.py`. The `GET /api/applications/` endpoint with LO role correctly filters to `WHERE assigned_to = <user_id>`. However, there is no pipeline-specific API that provides urgency indicators, sorting by urgency, stage-based filtering, or stalled-file detection.

Phase 3 F7 (S-3-F7-01) requires the pipeline to display urgency indicators derived from: rate lock expiration, stage timing, overdue document requests, outstanding conditions, and borrower responsiveness. This urgency calculation logic does not exist. The API returns raw application data; the urgency computation must be added.

Similarly, S-3-F7-03 requires urgency levels (Critical/High/Medium/Normal) computed from multiple factors. S-3-F7-04 requires an application detail view with document status, extraction results, and available actions.
**Reference:** Requirements chunk 3 S-3-F7-01 (urgency indicators), S-3-F7-03 (urgency based on rate lock expiration and stage timing), S-3-F7-04 (application detail view).
**Recommendation:** This is squarely Phase 3 scope, not a gap. Flagging it because the urgency calculation is a non-trivial service-layer feature that should be designed before implementation begins. It needs inputs from rate_locks, conditions, documents, and stage timing -- a cross-cutting query that Phase 3 TD should address carefully.

---

## PROD-05: Condition response currently limited to borrower role

**Severity:** Warning
**Description:** The `respond_condition` endpoint (`POST /api/applications/{id}/conditions/{condition_id}/respond`) is restricted to `UserRole.BORROWER` and `UserRole.ADMIN`. In Phase 3, loan officers need to respond to conditions on behalf of borrowers (S-3-F8-02: "LO reviews document quality flags and extraction results", S-3-F24-01: draft communications about conditions). The LO also needs to be able to mark documents for resubmission and prepare condition responses for underwriting re-review.

The current condition service supports `respond_to_condition()` but the route restricts it. The LO assistant agent will need tools that can interact with conditions (view, respond, prepare for submission back to underwriting).
**Reference:** Requirements chunk 3 S-3-F8-02 ("LO marks document for resubmission"), S-3-F8-03 ("submit to underwriting includes conditions response"). Demo walkthrough Flow 4 ("James reviews Sarah's conditions response... prepares the conditions response for underwriting re-review").
**Recommendation:** Phase 3 implementation must extend the condition response endpoint to accept `UserRole.LOAN_OFFICER`, with appropriate audit trail entries. This is a Phase 3 deliverable, but the existing endpoint restriction should be noted in the Phase 3 TD so it is not missed.

---

## PROD-06: No communication delivery mechanism

**Severity:** Warning
**Description:** Product plan F24 (Loan Officer Communication Drafting) specifies that the LO reviews AI-drafted communications and sends them to borrowers. S-3-F24-03 describes a "Send" action that delivers the message "via the configured channel (email, SMS, in-app notification)." However, there is no communication infrastructure. No email service, no in-app notification system, no message queue.

The requirements note (S-3-F24-03): "Communication delivery mechanism (email, SMS, in-app) is outside the scope of this chunk -- the 'Send' action is modeled as a tool or manual LO action." This is acceptable at MVP, but the question is: what does "send" mean in practice?

At minimum, there should be a `communications` table that stores sent messages (from, to, subject, body, timestamp) so the borrower can see that they received a message, and the audit trail captures it. Without this, the communication drafting feature is incomplete -- the LO can draft but the draft goes nowhere.
**Reference:** Product plan F24 ("The loan officer reviews and sends -- the AI drafts, the human approves"). S-3-F24-03 ("sent message is logged to the audit trail").
**Recommendation:** For MVP, implement a simple `communications` table and a `POST /api/applications/{id}/communications` endpoint that stores the message and writes an audit event. The borrower assistant can then have a tool to check for messages. This avoids needing real email/SMS infrastructure while still making the feature functional in the demo.

---

## PROD-07: Demo walkthrough Flow 4 requires pre-seeded LO-assigned applications

**Severity:** Warning
**Description:** The demo walkthrough (Flow 4) shows James Torres seeing "2 rate locks expiring within 5 days, 1 application with a closing date in 10 days that still has outstanding conditions, 3 applications waiting on borrower documents." This requires that the seed data includes applications specifically assigned to James Torres with appropriate urgency factors.

The current seed data system (`services/seed/seeder.py`) creates applications, borrowers, conditions, rate locks, and documents. However, it is unclear whether the seeded data includes applications assigned to specific loan officers with urgency-triggering conditions (expiring rate locks, stalled documents, outstanding conditions). If the seed data does not create this LO-assignment linkage with urgency triggers, the Phase 3 demo path will require manual data setup.
**Reference:** Demo walkthrough Flow 4. Product plan F20 (pre-seeded demo data). S-1-F20-02 ("I see 3-5 applications assigned to my user").
**Recommendation:** Verify the seed data creates LO-assigned applications with urgency triggers (expiring rate locks within 3-7 days, documents older than 7 days, outstanding conditions). If not, add LO-assignment fixtures to the seeder before Phase 3 demo testing begins. This may be best done as part of Phase 3 implementation since the urgency logic is Phase 3 scope.

---

## PROD-08: ARM product type missing from LoanType enum

**Severity:** Info
**Description:** The product plan lists six mortgage products: "30-year fixed-rate, 15-year fixed-rate, adjustable-rate (ARM), jumbo loans, FHA loans, and VA loans." The `LoanType` enum in `packages/db/src/db/enums.py` has: `CONVENTIONAL_30`, `CONVENTIONAL_15`, `FHA`, `VA`, `JUMBO`, and `USDA`. ARM is missing and USDA is present but not in the product plan. This is a minor discrepancy, but it affects the public assistant's product information responses and the demo narrative (the assistant describes ARM as one of the six products).
**Reference:** Product plan F1 (six mortgage products), product plan Proposed Solution ("Six mortgage products: 30-year fixed-rate, 15-year fixed-rate, adjustable-rate (ARM), jumbo, FHA, VA").
**Recommendation:** Replace `USDA` with `ARM` in the `LoanType` enum, or add `ARM` alongside `USDA` if USDA was an intentional addition. This requires a database migration.

---

## PROD-09: WebSocket rate limits flagged as pre-Phase 3 technical debt

**Severity:** Info
**Description:** The technical debt tracker (`plans/technical-debt.md`) lists three items under "Pre-Phase 3 (address before loan officer features)": (D2) no WebSocket rate limits, (D7) unbounded conversation history, and (D16) agent registry stats filesystem on every message. The LO chat will add a third high-use WebSocket endpoint. If these are not addressed, the LO assistant could inherit the same unbounded behavior.

Additionally, (D8) `verify_aud` disabled in JWT validation means the LO WebSocket endpoint would accept tokens from any Keycloak client, not just the summit-cap-ui client.
**Reference:** `plans/technical-debt.md` Pre-Phase 3 section.
**Recommendation:** Address D2, D7, D16, and D8 before or during Phase 3 implementation. D2 (rate limits) and D7 (message cap) are the highest priority -- they affect the LO chat endpoint directly.

---

## PROD-10: Borrower conversational intake lacks correction UX clarity

**Severity:** Info
**Description:** The product plan (F4) and demo walkthrough (Flow 2, step 6) describe a correction flow: "Sarah realizes she entered her income incorrectly. She says 'Actually, my salary is $85,000, not $82,000.' The assistant corrects the previously captured value." The implementation (`borrower_tools.py:update_application_data`) supports field updates and logs corrections in the audit trail. However, the tool accepts any field update at any time -- there is no distinction between "initial entry" and "correction" from a UX perspective.

This works functionally but may confuse the demo narrative. The audit event logs `corrections` as a separate key only when a field already had a non-null value. This is correct behavior but the borrower assistant's system prompt should be reviewed to ensure it acknowledges corrections naturally (e.g., "I've updated your salary from $82,000 to $85,000").
**Reference:** Product plan F4 ("conversational path allows borrowers to correct previously provided information"). Demo walkthrough Flow 2 step 6.
**Recommendation:** This is a prompt engineering issue, not a code issue. Review the borrower-assistant YAML config system prompt to ensure it handles corrections gracefully. Low priority -- the underlying functionality works.

---

## PROD-11: No F6 (Application Status and Timeline Tracking) dedicated endpoint

**Severity:** Info
**Description:** Product plan F6 ("Borrowers can see the current status of their application at any time, including pending conditions") is partially implemented. The `GET /api/applications/{id}/status` endpoint exists and returns stage info, document progress, and open condition counts. The borrower assistant has `application_status` and `regulatory_deadlines` tools. However, the product plan mentions "estimated timelines" and "awareness of regulatory timing requirements" -- the status response includes `typical_timeline` as a static string per stage but does not compute estimated completion dates or track actual vs. expected timing.

This is acceptable at MVP. Phase 3 urgency indicators (F7) will need the stage timing logic anyway, so this gap will be addressed as a byproduct of Phase 3 work.
**Reference:** Product plan F6 ("estimated timelines", "regulatory timing requirements"). S-2-F6-01 through S-2-F6-05 from chunk 2.
**Recommendation:** No action needed before Phase 3. The stage timing computation required for F7 urgency indicators will also improve F6. Flag this for the Phase 3 TD to ensure the timing logic is shared between the borrower status view and the LO pipeline urgency view.

---

## PROD-12: Interface contract drift items remain unresolved

**Severity:** Info
**Description:** The technical debt tracker lists several interface contract drifts (D13a-d): Compose versions differ (Keycloak 24 vs. 26, LangFuse v2 vs. v3, MinIO added), ID types differ (contract says UUID, implementation uses int), `models.yaml` provider differs (contract says "llamastack", implementation uses "openai_compatible"), and HealthResponse shape differs. These are documentation-level issues that do not affect functionality but could confuse a developer comparing the interface contracts document to the actual implementation.
**Reference:** `plans/technical-debt.md` "Interface contract drift (D13a-d)".
**Recommendation:** Update `plans/interface-contracts-phase-1.md` to match reality, or create a Phase 3 interface contracts document that supersedes the Phase 1 version. This is a documentation task, not a code task.

---

## PROD-13: Phase 2 features F4 (Application Workflow) lacks form fallback

**Severity:** Info
**Description:** The product plan includes a fallback contingency for F4: "If conversational-only data collection proves too brittle during implementation, a structured form fallback may be introduced." Currently, the application intake is fully conversational (via `start_application` and `update_application_data` borrower tools). There is no form-based alternative. This was an acknowledged risk in the product plan.

The conversational intake appears to work (the tools accept field updates, validate them, and track progress). Whether it is "too brittle" in practice depends on the LLM's reliability in extracting structured data from natural language. This should be validated during Phase 3 demo testing.
**Reference:** Product plan F4 fallback contingency. Product plan Risks ("Conversational-only application workflow depends on AI quality for data collection").
**Recommendation:** No action before Phase 3. Monitor conversational intake quality during Phase 3 development. If field capture reliability is poor (>10% error rate in testing), elevate the form fallback contingency.

---

## Summary

| Severity | Count | IDs |
|----------|-------|-----|
| Critical | 2 | PROD-01, PROD-02 |
| Warning | 4 | PROD-03, PROD-04, PROD-05, PROD-06 |
| Info | 7 | PROD-07, PROD-08, PROD-09, PROD-10, PROD-11, PROD-12, PROD-13 |

### Critical items that must be resolved before/during Phase 3

1. **PROD-01**: The LO assistant agent is entirely absent. Phase 3 TD must include agent creation as foundational work.
2. **PROD-02**: No state machine enforcement exists. State transitions (the core of the LO -> underwriting workflow) cannot be validated or audited correctly without this.

### Phase 3 prerequisites from this review

- LO assistant agent + WebSocket endpoint + tool set (PROD-01)
- Application state machine validator (PROD-02)
- Application-centric audit query endpoint (PROD-03)
- Extend condition response endpoint to LO role (PROD-05)
- Communication storage mechanism (PROD-06)
- Seed data with LO-assigned applications (PROD-07)
- Address pre-Phase 3 technical debt items D2, D7, D8, D16 (PROD-09)
