# Project Management Review -- Pre-Phase 5

**Reviewer:** project-manager
**Date:** 2026-02-27
**Scope:** Story coverage, deferred items, dependencies, test tracking

## Summary

Phase 3 (LO Experience) and Phase 4 (Underwriting) are complete. 72 PRs have been merged to main. The test suite has grown to 850 collected tests (up from the 739 recorded in memory -- likely reflecting continued additions during Phase 4 Sub-Chunk B finalization). Two Phase 4 features (F26 Agent Adversarial Defenses, F38 TrustyAI Fairness Metrics) were explicitly deferred with documented rationale. Phase 5 has significant scope: 5 features across 25 stories including the CEO dashboard (F12), conversational analytics (F13), audit export (F15-07), Helm deployment (F23), and model monitoring (F39).

## Findings

### [PJ-01] Severity: Warning
**Area:** Story coverage -- Phase 4 deferred features
**Finding:** F26 (Agent Adversarial Defenses, 4 stories) and F38 (TrustyAI Fairness Metrics, 4 stories) are documented as deferred in `plans/technical-debt.md`, but the master requirements table in `plans/requirements.md` still lists all 8 stories as P0 with no indication they were deferred. Someone reading the requirements hub would expect these features to have been implemented in Phase 4.
**Recommendation:** Update `plans/requirements.md` story map to add a "Status" column or annotation marking S-4-F26-01 through S-4-F26-04 and S-4-F38-01 through S-4-F38-04 as "Deferred" with a cross-reference to `plans/technical-debt.md`. This keeps the hub as the single source of truth for story status.

### [PJ-02] Severity: Warning
**Area:** Dependencies -- Phase 5 depends on deferred F38
**Finding:** Phase 5 stories S-5-F12-03 (CEO views fair lending metrics SPD/DIR) and S-5-F13-09 (CEO asks fair lending questions) explicitly depend on F38 (TrustyAI fairness metrics). The chunk-5 requirements document states: "F12, F13, F39 depend on F17 (decisions exist to aggregate), F25 (HMDA aggregates for fair lending), F38 (TrustyAI fairness metrics)." F38 was deferred from Phase 4, so these Phase 5 stories cannot be implemented as specified without first implementing F38 or a substitute.
**Recommendation:** F38 must be scheduled as a prerequisite before the fair-lending-dependent Phase 5 stories. The implementation plan in `plans/deferred/f38-trustyai-fairness-metrics.md` is well-specified and ready to execute. Options: (a) implement F38 as a Phase 5 precursor PR before the CEO dashboard work begins, or (b) stub the fair lending metrics endpoint and defer the real computation, which would leave S-5-F12-03 and S-5-F13-09 partially implemented.

### [PJ-03] Severity: Warning
**Area:** Dependencies -- Phase 5 analytics service does not exist
**Finding:** Phase 5 requirements (F12, F13) reference an "Analytics Service" that computes aggregates across applications, decisions, state transitions, and LO performance. No analytics service, route, or schema exists in the codebase. The current API has no `/api/analytics` or `/api/dashboard` endpoints. The entire CEO dashboard backend (pipeline summary, denial rates, LO performance, turn times, time range filtering) is net-new work that the requirements assume exists as infrastructure.
**Recommendation:** The Phase 5 technical design must treat the Analytics Service as a significant new component requiring its own stories/work units. Expect 8-12 stories worth of backend work before the CEO dashboard frontend can be built. Plan for: (1) analytics query functions that aggregate state transition history, (2) denial reason extraction from decision records, (3) LO performance metrics computation, (4) time-range-filtered endpoint(s), (5) PII masking at the query layer for CEO access. This is the largest single piece of Phase 5 work and should be on the critical path.

### [PJ-04] Severity: Warning
**Area:** Technical debt -- D10 audit event_data column still not JSONB
**Finding:** Technical debt item D10 states: "`audit_events.event_data` is Text, contract says JSONB." It is categorized as "Pre-Phase 4 (address before audit trail queries)." The column currently uses `Column(JSON)`, which is SQLAlchemy's generic JSON type -- on PostgreSQL this maps to the `json` type (not `jsonb`). Phase 5 stories S-5-F13-01 through S-5-F13-05 require filtering audit events by `event_data` sub-fields (e.g., `event_data.decision_outcome`, `event_data.disclosure_id`). The `json` type supports basic containment queries but not GIN indexing, which means audit trail queries that filter on event_data fields will perform full table scans. At MVP scale this is tolerable, but the tech debt note suggested addressing it before Phase 4 audit queries.
**Recommendation:** Migrate `event_data` from `JSON` to `JSONB` before Phase 5 CEO audit trail queries (F13). This is a single Alembic migration (column type change, no data migration needed since JSON is valid JSONB). Add a GIN index on `event_data` to support the sub-field filtering Phase 5 requires. This was supposed to be done pre-Phase 4 per the tech debt plan and should not slip further.

### [PJ-05] Severity: Suggestion
**Area:** Story coverage -- F17-06 and F17-07 implementation scope
**Finding:** S-4-F17-06 (Loan Estimate generation) and S-4-F17-07 (Closing Disclosure generation) are implemented as agent tools (`uw_generate_le`, `uw_generate_cd`) on the underwriter assistant. The requirements specify LE generation should trigger automatically on state transition to `application` and CD should trigger on transition to `closing`. The current implementation requires the underwriter to invoke these tools manually through chat. This is acceptable for MVP (the tools exist and produce the correct output), but the automatic-trigger behavior described in the acceptance criteria is not implemented.
**Recommendation:** Document this as a known gap. For the demo walkthrough, the underwriter can be prompted to generate LE/CD manually. If automatic generation is desired, it would require adding post-transition hooks to the state machine service. This could be a Phase 5 polish item or deferred to post-MVP.

### [PJ-06] Severity: Suggestion
**Area:** Story coverage -- Phase 5 audit export (S-5-F15-07)
**Finding:** S-5-F15-07 (audit trail export in CSV/JSON) is the only Phase 5 story for F15. No audit export endpoint or service exists in the codebase. This is straightforward to implement (query audit events, serialize to CSV/JSON, return as file download) but should not be overlooked in Phase 5 planning since it is listed separately from the F13 conversational analytics stories.
**Recommendation:** Include S-5-F15-07 in the Phase 5 work breakdown as a standalone story. It depends on the audit query infrastructure being built for F13, so sequence it after the F13 backend work. Estimated complexity: S (2-3 story points).

### [PJ-07] Severity: Suggestion
**Area:** Deferred item tracking -- Pre-Phase 3 items still open
**Finding:** The `plans/technical-debt.md` file has 6 items in the "Pre-Phase 3" section: D2 (WebSocket rate limits), D7 (unbounded conversation history), D8 (verify_aud disabled), D16 (agent registry stat on every message), D17 (fragile Path parents resolution), D18 (DB config divergence). These were categorized as "address before loan officer features." Phase 3 is complete and these items remain unaddressed. The phase gate label is now stale.
**Recommendation:** Re-categorize the Pre-Phase 3 items. D2 and D7 (WebSocket limits) become increasingly important as more personas use chat (Phase 5 adds CEO chat). D8 (JWT audience validation) is a security gap that should be addressed before demo. Either move them to "Pre-Production" with updated context or address them in a pre-Phase 5 cleanup pass. The items are low effort individually (each under 1 story point).

### [PJ-08] Severity: Suggestion
**Area:** Test coverage distribution
**Finding:** Test distribution across phases: Phase 1 foundation ~79 tests, Phase 2 borrower ~384 tests, Phase 3 LO ~66 tests, Phase 4 UW ~266 tests, cross-cutting/functional ~55 tests. Phase 3 has proportionally fewer tests relative to its feature complexity (11 stories, 3 features including urgency calculation, pipeline RBAC, 7 LO agent tools, communication drafting). The urgency calculation (17 tests) and LO tools (11 tests) are reasonably covered, but LO services have only a few tests, and the LO chat endpoint tests are minimal.
**Recommendation:** During Phase 5, consider adding integration tests that exercise the LO-to-underwriter handoff flow end-to-end (LO submits -> UW receives in queue -> conditions -> decision). This cross-phase integration is the most complex workflow in the system and currently relies on individual feature tests without a full-chain verification. This is not blocking but would strengthen confidence in the demo flow.

### [PJ-09] Severity: Suggestion
**Area:** PR organization and sequencing
**Finding:** The 72 PRs on main follow a clean sequential pattern: Phase 1 (PRs 1-17), Phase 1 review (PR 18), Phase 2 (PRs 19-46), pre-Phase 3 cleanup (PRs 48-56), Phase 3 (PRs 57-62), Phase 4 (PRs 63-72). There are no out-of-sequence merges or conflicting feature branches. The pre-Phase 3 cleanup (13 specialist agents, 9 PRs) was a good practice that resolved accumulated tech debt before the next feature phase. The refactor PR #65 (rule-based routing replacing LLM classifier) was correctly merged between Phase 4 sub-chunks rather than mid-feature.
**Recommendation:** Continue this pattern for Phase 5. Consider a pre-Phase 5 cleanup pass similar to the pre-Phase 3 effort, focused on: (a) the D10 JSONB migration, (b) re-categorizing stale Pre-Phase 3 tech debt items, and (c) any Phase 4 integration gaps discovered during review.

### [PJ-10] Severity: Warning
**Area:** Dependencies -- Phase 5 LangFuse API assumption
**Finding:** Requirement assumption REQ-C5-A-02 states: "LangFuse exposes an API or SQL access to ClickHouse for querying trace metrics (latency, token usage, error rates)" and rates it as "High" risk. F39 (Model Monitoring Overlay) depends entirely on this assumption. If LangFuse does not expose a suitable API for aggregating trace metrics, the entire F39 feature (4 stories) cannot be implemented as specified. The assumption document suggests verifying "during Phase 1" but there is no evidence this verification occurred.
**Recommendation:** Verify the LangFuse API capabilities before beginning Phase 5 technical design. Check whether the self-hosted LangFuse instance (currently in compose.yml) exposes trace aggregation endpoints. If not, determine whether direct ClickHouse queries are feasible. This is a blocking dependency for F39 and should be resolved during Phase 5 planning, not during implementation.

### [PJ-11] Severity: Suggestion
**Area:** Story coverage -- F23 Helm chart status
**Finding:** F23 (Container Platform Deployment, 5 stories) is categorized as Phase 4b in the requirements hub. A basic Helm chart already exists at `deploy/helm/summit-cap-financial/` from earlier work, but the 5 specific stories (S-5-F23-01 through S-5-F23-05) covering init containers, InferenceService configuration, and S3 backend configuration have not been implemented. These stories are infrastructure-focused and independent of the CEO dashboard features.
**Recommendation:** F23 can be parallelized with the CEO dashboard work (F12/F13) since they have no technical dependencies on each other. Assign F23 to a separate work stream to avoid it becoming a bottleneck. The Helm chart stories are well-defined and can be sized at M complexity each.

### [PJ-12] Severity: Warning
**Area:** Phase 5 scope -- 25 stories is the largest phase yet
**Finding:** Phase 5 contains 25 stories across 5 features (F12: 5, F13: 9, F15: 1, F23: 5, F39: 5). This is the most stories in a single phase. Phases 1-4 ranged from 11-34 stories but were subdivided into sub-chunks (e.g., Phase 4 was split into Sub-Chunk A: F10, Sub-Chunk B: F9/F11, and a final chunk: F16/F17). Phase 5 introduces entirely new UI components (CEO dashboard charts, conversational analytics), a new analytics backend, and infrastructure work (Helm), none of which build on existing code the way Phase 4 UW features built on Phase 2 borrower infrastructure.
**Recommendation:** Sub-chunk Phase 5 into at least 3 delivery milestones: (a) **Analytics backend + F38 prerequisite** (fairness metrics, analytics query service, dashboard data endpoints) -- enables F12 and F13 frontend work; (b) **CEO Experience** (F12 dashboard UI, F13 conversational agent + tools, F15-07 audit export) -- the demo-facing deliverable; (c) **Infrastructure** (F23 Helm stories, F39 model monitoring) -- can be parallelized. This prevents a single large Phase 5 from becoming unmanageable.
