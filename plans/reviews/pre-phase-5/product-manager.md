# Product Alignment Review -- Pre-Phase 5

**Reviewer:** product-manager
**Date:** 2026-02-27
**Scope:** Feature completeness, scope drift, MVP alignment, demo readiness, deferred item tracking

## Executive Summary

Phases 1-4 have delivered a substantial backend covering 4 of 5 personas (Prospect, Borrower, Loan Officer, Underwriter). The codebase includes 739+ tests (now reported as 1012), 4 agent assistants with 40+ tools, a compliance knowledge base with vector search, underwriting decisions with AI comparison, a conditions lifecycle, and a hash-chained audit trail. Two features were deferred from Phase 4 (F26 Agent Adversarial Defenses, F38 TrustyAI Fairness Metrics) with documented rationale.

Phase 5 (CEO dashboard + conversational analytics + deployment) is the remaining P0 work. Below are findings organized by severity, covering completeness gaps, scope drift, demo readiness blockers, and deferred item status.

---

## Findings

### [PM-01] Severity: Critical
**Requirement:** F12 (CEO Executive Dashboard), F13 (CEO Conversational Analytics) -- all of Chunk 5
**Finding:** No CEO persona implementation exists. There is no `ceo-assistant.yaml` agent config, no CEO chat route, no analytics service, no dashboard endpoints, and no CEO agent tools. The `main.py` router list includes routes for public, borrower, loan_officer, and underwriter chat -- but no CEO/executive route. The only CEO-related code is defensive: PII masking middleware, CEO document content restriction (403 on `/documents/{id}/content`), and CEO role in the RBAC enum. The entire Chunk 5 requirements (25 stories across F12, F13, F15-export, F23, F39) are unimplemented.
**Recommendation:** This is expected -- Phase 5 is the next phase. No action needed, but the scope of remaining work is significant: analytics service, CEO agent + tools, dashboard API endpoints, fair lending metrics integration (if F38 is un-deferred), audit export, model monitoring overlay, and container deployment. Prioritize the dependency chain: analytics service -> dashboard endpoints -> CEO agent/tools -> chat route.

---

### [PM-02] Severity: Critical
**Requirement:** F20 (Pre-Seeded Demo Data), S-1-F20-02/03
**Finding:** The seeder infrastructure exists and seeds borrowers, applications, documents, conditions, decisions, rate locks, HMDA demographics, and KB content. However, the demo data was designed for Phase 1-4 validation. For the CEO dashboard (Phase 5) to be meaningful, the seeded data must include: (a) sufficient historical closed loans (15-25) with decision records spanning 6+ months, (b) HMDA demographic data for historical loans to support fair lending analysis, (c) denial decisions with structured denial_reasons for top-reasons distribution, (d) LO performance variation across 2-3 loan officers for comparative metrics. The existing `fixtures.py` needs to be audited against these Phase 5 requirements before CEO dashboard development begins.
**Recommendation:** Before implementing F12/F13, audit the seed data fixtures against the CEO dashboard story acceptance criteria (S-5-F12-01 through S-5-F12-05). Ensure the demo data volume and variety supports all dashboard panels. This is a prerequisite -- if the seed data is insufficient, the CEO dashboard will show empty or misleading metrics during the demo.

---

### [PM-03] Severity: Critical
**Requirement:** F23 (Container Platform Deployment), product plan Phase 4b
**Finding:** F23 is listed in the product plan as Phase 4b but has not been implemented. The `deploy/helm/` directory exists (per project structure) but this is from the template -- no Summit Cap-specific Helm charts or OpenShift deployment manifests have been created for the full application stack. The `compose.yml` works for local development but is not equivalent to production-grade container deployment. With the Summit demo deadline, container deployment work needs to be prioritized alongside or immediately after the CEO persona work.
**Recommendation:** Evaluate whether F23 is blocking for the Summit demo or whether the demo can run on compose. If the demo runs locally, defer F23 to post-demo polish. If the demo must run on OpenShift, F23 needs parallel-track implementation alongside CEO features.

---

### [PM-04] Severity: Warning
**Requirement:** F38 (TrustyAI Fairness Metrics) -- stakeholder mandate
**Finding:** F38 was deferred with stakeholder approval due to timeline pressure. A detailed implementation plan exists at `plans/deferred/f38-trustyai-fairness-metrics.md`. However, F38 is a stakeholder-mandated feature (TrustyAI is explicitly listed in the Stakeholder-Mandated Constraints table) and the CEO dashboard stories (S-5-F12-03) directly depend on SPD/DIR metrics. Without F38, the fair lending section of the CEO dashboard cannot show quantitative fairness metrics -- it would be limited to simple approval/denial rate breakdowns. This is a significant demo gap because the HMDA collection + fair lending monitoring tension is described in the product plan as "one of the most compelling and differentiated aspects of this demo."
**Recommendation:** Re-evaluate F38 for Phase 5. The deferred plan outlines a pure-Python fallback that avoids JPype/JVM complexity. If the pure-Python fallback is feasible within the Phase 5 timeline, un-defer F38 and include it alongside F12/F13 development. If not, implement simple approval-rate-by-demographic breakdowns as a minimal substitute and note that TrustyAI integration is deferred to post-MVP.

---

### [PM-05] Severity: Warning
**Requirement:** F26 (Adverse Action Notices) -- product plan P0 feature
**Finding:** The product plan lists F26 as a P0 feature for adverse action notices. The requirements chunk 4 reassigned the "F26" label to "Agent Adversarial Defenses" (4 stories: S-4-F26-01 through S-4-F26-04), and the adverse action notice functionality was folded into F17 (S-4-F17-03, S-4-F17-04). The implementation includes `uw_draft_adverse_action` and `uw_render_decision` tools in `decision_tools.py`, and the Decision model has `denial_reasons` fields. So the adverse action notice capability exists under F17, but the naming divergence between the product plan and the requirements creates confusion. The deferred F26 (adversarial defenses) is a different capability than the product plan's F26 (adverse action notices).
**Recommendation:** No implementation gap -- the adverse action notice capability is implemented under F17. However, update the product plan or requirements to reconcile the F26 naming conflict. The product plan's "F26: Adverse Action Notices" capability is delivered; the requirements' "F26: Agent Adversarial Defenses" is deferred with documented rationale. This should be noted explicitly to avoid confusion in Phase 5 planning.

---

### [PM-06] Severity: Warning
**Requirement:** Product plan LoanType enum -- six products
**Finding:** The product plan specifies six mortgage products: 30-year fixed-rate, 15-year fixed-rate, adjustable-rate (ARM), jumbo, FHA, and VA. The `LoanType` enum in `packages/db/src/db/enums.py` includes: `CONVENTIONAL_30`, `CONVENTIONAL_15`, `FHA`, `VA`, `JUMBO`, and `USDA`. Two discrepancies: (1) ARM (adjustable-rate mortgage) is missing from the enum -- it was replaced by USDA. (2) USDA was never mentioned in the product plan. The product info tool in the public assistant, the affordability calculator, and the demo walkthrough all reference ARM as a core product. This drift means the public assistant's product_info tool and the pre-seeded data may reference products that don't match the data model, or the ARM product type is absent from the system.
**Recommendation:** Either add ARM to the LoanType enum (and decide whether USDA stays as a 7th product or replaces ARM), or update the product plan to reflect the actual 6 products. This affects demo credibility -- the public assistant flow (Flow 1) specifically discusses "six mortgage products" including ARM.

---

### [PM-07] Severity: Warning
**Requirement:** F11 (Compliance Checks), S-4-F11-05 -- compliance guard
**Finding:** The compliance check service (`services/compliance/checks.py`) and compliance check tool (`agents/compliance_check_tool.py`) are implemented with ECOA, ATR/QM, and TRID checks. However, S-4-F11-05 specifies that the agent should refuse to assist with an approval decision if a critical compliance failure exists, and should require compliance checks to be run before rendering a decision. The current `uw_render_decision` tool in `decision_tools.py` needs to be verified for whether it enforces this compliance gate -- i.e., does it check that compliance checks have been run and passed before allowing an approval? If this guard is missing, an underwriter could approve a non-compliant application through the chat interface without triggering compliance checks.
**Recommendation:** Verify that `uw_render_decision` includes a compliance gate (either by checking that compliance_check results exist for the application, or by running compliance checks inline before rendering). If missing, this is a demo integrity issue -- the underwriter flow (Flow 5) explicitly shows the compliance check step before decision rendering.

---

### [PM-08] Severity: Warning
**Requirement:** F15 (Audit Trail) -- audit trail export capability
**Finding:** The product plan F15 specifies "Export capability: Audit data can be exported for external analysis." The requirements chunk 5 includes a dedicated feature for this (F15 export). The current implementation has audit query endpoints (`/api/admin/audit` by session, `/api/admin/audit/application/{id}` by application, `/api/admin/audit/verify` for chain verification) but no export endpoint (CSV/JSON download). The audit trail is queryable but not exportable. This is a Phase 5 requirement (S-5-F15-01 audit export) that has not been implemented.
**Recommendation:** Include audit export in Phase 5 scope. This is lower priority than F12/F13 but important for the audit trail demo flow (Flow 7). A simple JSON/CSV download endpoint would satisfy the requirement.

---

### [PM-09] Severity: Warning
**Requirement:** F17 (Regulatory Awareness and TRID Disclosures)
**Finding:** The product plan's F17 covers "Regulatory Awareness and TRID Disclosures" including Loan Estimate generation and Closing Disclosure generation. The requirements chunk 4 includes S-4-F17-06 (LE generation at application submission) and S-4-F17-07 (CD generation at final approval). The implementation includes `uw_generate_le` and `uw_generate_cd` tools in `decision_tools.py`, and the Application model has `le_delivery_date` and `cd_delivery_date` columns. However, these are agent tools that must be explicitly invoked by the underwriter -- the requirements specify automatic generation on state transition. Additionally, S-4-F17-06 specifies LE generation when transitioning to `application` state (borrower action), not underwriter action. The tools are correctly implemented as underwriter tools, but the auto-generation on state transition is not implemented.
**Recommendation:** Decide whether LE/CD generation should remain manual (underwriter invokes tool) or become automatic on state transition per the requirements. For demo purposes, manual invocation may be sufficient since the demo walkthrough can script the action. If auto-generation is desired, add state transition hooks to the application service.

---

### [PM-10] Severity: Warning
**Requirement:** F16 condition severity -- requirements vs implementation
**Finding:** The requirements (S-4-F16-01) specify three condition severity levels: Critical, Standard, and Optional. Critical blocks final approval; Optional can be waived. The implementation's `ConditionSeverity` enum in `enums.py` uses mortgage industry-standard terms: `prior_to_approval`, `prior_to_docs`, `prior_to_closing`, `prior_to_funding`. The schema (`schemas/condition.py`) defines severity as `str | None`, not a constrained enum. This is a deliberate and defensible design choice (industry-standard terminology is more realistic for the demo), but it diverges from the requirements specification. The product plan's condition lifecycle (F11) references "Critical" severity blocking approval, which maps to `prior_to_approval` in the implementation.
**Recommendation:** No code change needed -- the implementation uses more realistic terminology. However, update the demo script to use the implemented terms. Verify that the condition-blocking logic (can't proceed to final approval if `prior_to_approval` conditions are uncleared) is enforced in the state transition code.

---

### [PM-11] Severity: Warning
**Requirement:** Demo walkthrough -- Flow 1 through Flow 8
**Finding:** The demo walkthrough (`plans/demo-walkthrough.md`) describes flows for all 5 personas plus audit trail and HMDA tension. With Phase 4 complete, Flows 1-5 (Prospect, Borrower, LO, Underwriter, and partial audit) should be executable against the backend. Flow 6 (CEO dashboard + analytics) and Flow 7 (audit trail UI for CEO/UW) require Phase 5 implementation. Flow 8 (HMDA tension) is partially demonstrable -- HMDA collection via borrower intake exists, HMDA isolation from underwriter tools exists, but the CEO aggregate view (the payoff of the tension demo) requires F12/F13. The "Live Extensibility Option" (hot-reload config change) is demonstrable now since agent configs are YAML-based with mtime detection.
**Recommendation:** Before Phase 5 implementation, do a smoke test of Flows 1-5 against the current backend via WebSocket to verify the demo path works end-to-end. Any gaps found during this test should be fixed before or during early Phase 5.

---

### [PM-12] Severity: Warning
**Requirement:** F39 (Model Monitoring Overlay)
**Finding:** F39 is listed as P0 in the product plan and assigned to Phase 4a. It has not been implemented. The requirements chunk 5 includes stories for F39. The feature depends on LangFuse metrics data (which is being collected via the callback handler). F39 is a lightweight overlay showing inference latency, token usage, error rates, and routing distribution. It is the lowest-priority P0 feature (RICE score 1.5, lowest in the P0 list).
**Recommendation:** F39 should be included in Phase 5 scope but as the lowest priority P0 item. If time runs short, F39 can be cut -- the LangFuse dashboard itself provides similar information for developers/operators, and F39 is described as "a read-only dashboard panel, not an alerting system."

---

### [PM-13] Severity: Warning
**Requirement:** F18 (AI Observability Dashboard) -- LangFuse integration completeness
**Finding:** LangFuse callback integration exists (`observability.py`, `_chat_handler.py`). The callback handler is attached to agent invocations per S-1-F18-01. However, S-1-F18-03 (trace-to-audit correlation via session_id) requires that both LangFuse traces and audit events share the same session_id. The audit service accepts `session_id` as a parameter and the chat handler passes it. This appears to be implemented, but the correlation has not been verified end-to-end in a live test with LangFuse running. If the session_id values don't match between LangFuse and the audit trail, the audit Flow 7 demo breaks.
**Recommendation:** Include a LangFuse integration verification step early in Phase 5. Spin up the full stack with LangFuse, execute an agent conversation, and verify that the LangFuse trace session_id matches the audit event session_id for the same conversation.

---

### [PM-14] Severity: Suggestion
**Requirement:** F22 (Single-Command Local Setup), S-1-F22-03
**Finding:** The product plan requires setup in under 10 minutes with images pre-pulled. The compose.yml exists with profiles support. However, as features have been added across Phases 2-4, new services (MinIO for document storage) have been added to the stack. The 10-minute setup target should be re-validated now that the stack is more complex. Additionally, the demo data seeding (which now includes KB content ingestion with embedding generation) may add significant time if an embedding model must be invoked during seeding.
**Recommendation:** Time a fresh setup from compose pull to "all services healthy" with demo data seeded. If it exceeds 10 minutes, identify bottlenecks. KB ingestion with embeddings may need pre-computed embeddings rather than live generation during seeding.

---

### [PM-15] Severity: Suggestion
**Requirement:** Technical debt tracking
**Finding:** `plans/technical-debt.md` is well-maintained with items categorized by phase gate (Pre-Phase 3, Pre-Phase 4, Pre-Production, Deferred Features, Resolved). Several Pre-Phase 3 items (D2 WebSocket rate limits, D7 unbounded conversation history, D8 verify_aud disabled, D16 agent registry stats, D17 fragile path resolution, D18 dual config paths) are still listed as unresolved. These were gated "Pre-Phase 3" but Phase 3 has been complete since the prior sprint. None of these are demo-blocking, but D8 (verify_aud disabled) is a security concern that could be flagged during a Summit security review.
**Recommendation:** During Phase 5 polish, address D8 (verify_aud) as a minimum. The other Pre-Phase 3 items are lower risk for an MVP demo but should be tracked. Update the phase gates in technical-debt.md to reflect current status (some "Pre-Phase 3" items should be re-categorized as "Pre-Production" or "Phase 5 Polish").

---

### [PM-16] Severity: Suggestion
**Requirement:** Product plan Phase 5 -- "No new features. This phase is dedicated to integration testing, demo rehearsal, performance tuning for the demo path, and fixing issues discovered during end-to-end testing."
**Finding:** The product plan describes Phase 5 as pure polish with no new features. However, the requirements chunk 5 includes 25 stories for F12, F13, F15-export, F23, and F39 -- all of which are new feature implementation. There is a disconnect between the product plan phasing (which puts all new features in Phase 4a) and reality (CEO features have not been implemented). The current state suggests Phase 5 is actually "Phase 4a completion + polish" rather than "polish only."
**Recommendation:** Acknowledge this phase rebalancing in the Phase 5 planning. The practical Phase 5 scope is: (1) CEO dashboard + analytics (F12, F13), (2) audit export (F15), (3) model monitoring overlay (F39), (4) optionally container deployment (F23), (5) optionally TrustyAI metrics (F38), and (6) demo polish and integration testing. This is substantially more work than the product plan's Phase 5 description. Consider whether all items fit in the remaining timeline, and which can be cut if needed.

---

### [PM-17] Severity: Suggestion
**Requirement:** F6 (Application Status and Timeline Tracking)
**Finding:** The borrower agent has an `application_status` tool and the status service exists. However, F6 requirements also specify that the assistant demonstrates "awareness of regulatory timing requirements" (S-2-F6-05). The implementation should include the agent noting TRID timing (e.g., "Your Loan Estimate was delivered on day 2 of 3 allowed business days"). This is a demo credibility detail that makes the regulatory awareness visible to the borrower persona.
**Recommendation:** Verify that the borrower assistant's system prompt or tool output includes TRID timing awareness when reporting application status. If not present, this is a quick system prompt enhancement.

---

### [PM-18] Severity: Suggestion
**Requirement:** Scope drift -- ConditionSeverity terms
**Finding:** Minor scope drift: the requirements specify condition severity as Critical/Standard/Optional (3 levels). The implementation uses 4 levels (prior_to_approval, prior_to_docs, prior_to_closing, prior_to_funding) which are mortgage industry standard terms. The implementation is arguably more realistic than the spec. This is positive scope drift -- more domain-accurate than what was specified.
**Recommendation:** No action needed. Note in the demo script that Summit Cap uses industry-standard condition categories.

---

## Scope Drift Summary

| Area | Direction | Severity | Notes |
|------|-----------|----------|-------|
| LoanType USDA vs ARM | Drift | Warning | USDA added, ARM missing from enum (PM-06) |
| Condition severity terms | Drift (positive) | Suggestion | Industry-standard terms used instead of spec terms (PM-10, PM-18) |
| F26 label conflict | Naming | Warning | Product plan F26 = adverse action; requirements F26 = adversarial defenses (PM-05) |
| Phase 5 scope | Expansion | Suggestion | Phase 5 is feature implementation, not just polish (PM-16) |

## Feature Completeness Matrix

| Feature | Phase | Status | Notes |
|---------|-------|--------|-------|
| F1 Public Assistant | 1 | Complete | Products endpoint, affordability calc, chat |
| F2 Authentication | 1 | Complete | Keycloak OIDC, JWT middleware |
| F3 Borrower Assistant | 2 | Complete | Intake via chat, 13 borrower tools |
| F4 Document Upload | 2 | Complete | Upload, MinIO storage, extraction pipeline |
| F5 Document Analysis | 2 | Complete | Extraction, quality assessment, HMDA exclusion |
| F6 Status Tracking | 2 | Complete | Status service, borrower tool |
| F7 LO Pipeline | 3 | Complete | Urgency calc, pipeline query, RBAC filtering |
| F8 LO Workflow | 3 | Complete | 7 LO tools, submit to underwriting |
| F9 UW Workspace | 4 | Complete | Queue view, risk assessment, recommendation |
| F10 Compliance KB | 4 | Complete | 3-tier KB, vector search, conflict detection |
| F11 Compliance Checks | 4 | Complete | ECOA, ATR/QM, TRID checks |
| F12 CEO Dashboard | 5 | Not started | Phase 5 scope |
| F13 CEO Analytics | 5 | Not started | Phase 5 scope |
| F14 RBAC | 1 | Complete | Multi-layer enforcement, PII masking |
| F15 Audit Trail | 2 | Complete (core) | Hash chain, append-only; export not yet |
| F16 Conditions Mgmt | 4 | Complete | Issue, review, clear, waive, return, summary |
| F17 Decisions | 4 | Complete | Approve, deny, adverse action, LE/CD gen |
| F18 Observability | 1 | Complete | LangFuse callback, trace correlation |
| F19 Conversation Memory | 2 | Complete | Checkpointer, user-scoped persistence |
| F20 Demo Data | 1 | Complete (core) | Seeder with fixtures; may need Phase 5 expansion |
| F21 Model Routing | 1 | Complete | Rule-based classification, YAML config |
| F22 Single-Command Setup | 1 | Complete | Compose profiles, health checks |
| F23 Container Deploy | 4b | Not started | Helm/OpenShift manifests needed |
| F24 Communication Draft | 3 | Complete | Draft + send tools with audit |
| F25 HMDA Collection | 1-2 | Complete | Isolated schema, demographic filter |
| F26 Adverse Action | 4 (via F17) | Complete | Implemented as S-4-F17-03/04 |
| F26 Adversarial Defenses | 4 | Deferred | Documented rationale in technical-debt.md |
| F27 Rate Lock Tracking | 2 | Complete | Rate lock model, status tool |
| F28 Doc Completeness | 2 | Complete | Contextual checklist, condition response |
| F38 TrustyAI Metrics | 4 | Deferred | Implementation plan at plans/deferred/ |
| F39 Model Monitoring | 4a | Not started | Phase 5 scope |

## Deferred Items Status

| Item | Tracked? | Blocking Phase 5? | Notes |
|------|----------|-------------------|-------|
| F26 Adversarial Defenses | Yes (technical-debt.md) | No | Existing Llama Guard + schema isolation sufficient for MVP |
| F38 TrustyAI Metrics | Yes (plans/deferred/) | Partially | F12 fair lending panel depends on this; pure-Python fallback may unblock |
| D2 WebSocket rate limits | Yes (technical-debt.md) | No | Pre-Production concern |
| D7 Unbounded conversation | Yes (technical-debt.md) | No | Memory concern for long sessions |
| D8 verify_aud disabled | Yes (technical-debt.md) | No | Security concern; low demo risk |
| D10 audit event_data Text vs JSONB | Yes (technical-debt.md) | Possibly | CEO audit queries may need JSONB filtering |
| D14 Application service untested | Yes (technical-debt.md) | No | Integration tests exist |

## Demo Readiness Assessment

| Demo Flow | Ready? | Blockers |
|-----------|--------|----------|
| Flow 1: Prospect | Yes | None |
| Flow 2: Borrower Application | Yes | Smoke test needed |
| Flow 3: Borrower Status Check | Yes | Smoke test needed |
| Flow 4: LO Pipeline + Conditions | Yes | Smoke test needed |
| Flow 5: Underwriter Review | Yes | Smoke test needed |
| Flow 5b: Underwriter Denial | Yes | Smoke test needed |
| Flow 6: CEO Dashboard | No | Requires F12/F13 implementation |
| Flow 7: Audit Trail Review | Partial | Backend queries exist; no CEO UI; no export |
| Flow 8: HMDA Tension | Partial | Collection + isolation work; CEO aggregate view requires F12 |
| Live Extensibility | Yes | Config hot-reload works |

## Phase 5 Priority Recommendation

Based on this review, recommended Phase 5 priority order:

1. **CEO agent + analytics service + dashboard endpoints** (F12/F13) -- this is the largest gap and the highest-impact demo segment
2. **Seed data expansion** for CEO dashboard -- ensure historical data supports all dashboard panels
3. **F38 TrustyAI metrics** (pure-Python fallback) -- enables the fair lending demo differentiator
4. **Audit trail export** (F15 export) -- completes the audit flow
5. **F39 Model Monitoring Overlay** -- lowest priority P0; cut if time is short
6. **F23 Container Deployment** -- evaluate whether demo requires OpenShift or can run locally
7. **Demo polish and integration testing** -- end-to-end smoke test of all flows
