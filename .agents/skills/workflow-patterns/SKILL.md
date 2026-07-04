---
description: Reference templates for common multi-agent workflows. Provides sequencing patterns, parallel execution groups, and review gates for orchestrating specialist agents.
user_invocable: false
---

# Workflow Patterns

These templates define standard multi-agent orchestration sequences. Use these as starting points, adapting them to the specific request.

## New Feature (Full-Stack)

A complete feature implementation from product definition through documentation.

```
Phase 1: Product Definition
  → @product-manager: PRD with scope, success metrics, and prioritized features

Phase 2: Requirements
  → @requirements-analyst: Detailed user stories and acceptance criteria from PRD

Phase 3: Design
  → @architect: System design and technology decisions

Phase 4: Work Breakdown
  → @project-manager: Epics, stories, and tasks with dependency mapping

Phase 5: Work Breakdown Review
  → @tech-lead: Validate dependencies, exit conditions, and scope compliance

Phase 6: Contracts (parallel)
  → @api-designer: API contract and OpenAPI spec
  → @database-engineer: Schema design and migrations

Phase 7: Implementation (parallel)
  → @backend-developer: API handlers and business logic
  → @frontend-developer: UI components and integration

Phase 8: Testing
  → @test-engineer: Unit, integration, and e2e tests

Phase 9: Review (parallel)
  → @code-reviewer: Code quality review
  → @security-engineer: Security audit

Phase 10: Documentation
  → @technical-writer: User docs, API docs, changelog
```

## Bug Fix

Systematic diagnosis, fix, and verification.

```
Phase 1: Diagnosis
  → @debug-specialist: Root cause analysis and fix

Phase 2: Testing
  → @test-engineer: Regression test + verify existing tests pass

Phase 3: Review
  → @code-reviewer: Verify fix quality and no regressions
```

## Performance Optimization

Measure-driven optimization cycle.

```
Phase 1: Profile
  → @performance-engineer: Baseline metrics and bottleneck identification

Phase 2: Optimize
  → [appropriate implementer based on bottleneck location]

Phase 3: Verify
  → @performance-engineer: Measure improvement, compare to baseline

Phase 4: Review
  → @code-reviewer: Verify optimization quality
```

Repeat phases 2-3 if targets not met.

## API Evolution

Contract-first API changes with backward compatibility.

```
Phase 1: Contract
  → @api-designer: Updated API spec with versioning strategy

Phase 2: Implementation
  → @backend-developer: Implement API changes

Phase 3: Contract Testing
  → @test-engineer: Contract tests and integration tests

Phase 4: Documentation
  → @technical-writer: API docs and migration guide
```

## Infrastructure Change

Infrastructure modifications with operational readiness, security, and documentation gates.

```
Phase 1: Implementation
  → @devops-engineer: Infrastructure changes

Phase 2: Operational Readiness
  → @sre-engineer: SLOs, alerting rules, and runbooks for new infrastructure

Phase 3: Review (parallel)
  → @security-engineer: Security review of infrastructure
  → @technical-writer: Runbook and documentation updates
```

## Security Hardening

Security-focused review and remediation cycle.

```
Phase 1: Audit
  → @security-engineer: Full security audit

Phase 2: Remediation (parallel, based on findings)
  → @backend-developer: Fix server-side vulnerabilities
  → @frontend-developer: Fix client-side vulnerabilities
  → @devops-engineer: Fix infrastructure issues

Phase 3: Verification
  → @security-engineer: Verify remediations

Phase 4: Documentation
  → @technical-writer: Security documentation updates
```

## Refactoring

Structured improvement of existing code quality and architecture.

```
Phase 1: Identify
  → @code-reviewer: Audit codebase for code smells, complexity, and improvement targets

Phase 2: Design
  → @architect: Design improved structure, component boundaries, or patterns

Phase 3: Implement (parallel, based on scope)
  → @backend-developer: Refactor server-side code
  → @frontend-developer: Refactor client-side code
  → @database-engineer: Refactor schema or queries

Phase 4: Verify
  → @test-engineer: Verify no regressions, update tests for new structure

Phase 5: Review
  → @code-reviewer: Verify improvement meets design goals
```

## Database Migration (Schema Evolution)

Schema changes that propagate through the application code.

```
Phase 1: Schema
  → @database-engineer: Design migration (up + down), indexes, constraints

Phase 2: Application Code
  → @backend-developer: Update ORM models, queries, and service logic

Phase 3: Testing
  → @test-engineer: Test migration up/down, verify queries, integration tests

Phase 4: Review
  → @code-reviewer: Review migration safety and code changes
```

## Incident Response (Production Bug)

Extends the Bug Fix workflow through triage, deployment, and post-incident review.

```
Phase 1: Triage
  → @sre-engineer: Severity assessment, impact analysis, initial response coordination

Phase 2: Diagnose
  → @debug-specialist: Root cause analysis and hotfix implementation

Phase 3: Verify
  → @test-engineer: Regression test and existing test verification

Phase 4: Deploy
  → @devops-engineer: Deploy hotfix to production

Phase 5: Post-Incident (parallel)
  → @sre-engineer: Post-incident review (timeline, root cause, action items)
  → @code-reviewer: Review hotfix quality
  → @technical-writer: Document incident and remediation
```

## Greenfield Project Setup

Initial project scaffolding from product vision through operational readiness.

```
Phase 1: Product Definition
  → @product-manager: PRD with vision, personas, success metrics, and phased roadmap

Phase 2: Requirements
  → @requirements-analyst: Detailed user stories and acceptance criteria

Phase 3: Architecture
  → @architect: Technology selection, project structure, ADRs

Phase 4: Work Breakdown
  → @project-manager: Epics, stories, tasks with dependency mapping

Phase 5: Work Breakdown Review
  → @tech-lead: Validate dependencies, exit conditions, and scope compliance

Phase 6: Foundation (parallel)
  → @devops-engineer: CI/CD pipeline, Docker setup, development environment
  → @database-engineer: Initial schema and migration framework
  → @api-designer: API contract foundation

Phase 7: Scaffold (parallel)
  → @backend-developer: Project skeleton, middleware, error handling
  → @frontend-developer: Project skeleton, routing, layout

Phase 8: Quality Gates
  → @test-engineer: Testing framework setup and example tests

Phase 9: Operational Readiness
  → @sre-engineer: SLOs, alerting, runbooks, incident response process

Phase 10: Documentation
  → @technical-writer: README, contributing guide, architecture docs
```

## Production Readiness

Prepare an existing application for production deployment.

```
Phase 1: SLO Definition
  → @sre-engineer: Define SLOs/SLIs, error budgets, and capacity plan

Phase 2: Infrastructure (parallel)
  → @devops-engineer: Production deployment, monitoring infrastructure, alerting integration
  → @sre-engineer: Alerting rules, runbooks, and incident response process

Phase 3: Security Audit
  → @security-engineer: Full OWASP audit and dependency scanning

Phase 4: Documentation
  → @technical-writer: Runbooks, operational docs, architecture guide
```

## Spec-Driven Development (SDD)

The default workflow for non-trivial features. The defining principle is **scope discipline** — each phase stays strictly within its responsibility and does not do work that belongs to downstream agents. This prevents premature solutioning and ensures each agent gets to do their job with fresh perspective rather than rubber-stamping decisions already baked into an upstream artifact.

Use SDD when a feature is complex enough that getting the spec wrong would waste more time than writing the spec takes. For simple, single-concern tasks (1–2 files, one implementer), use the simpler Bug Fix or direct single-agent routing instead.

### Scope Discipline

This is the most important principle in the workflow. Each phase must stay within its lane:

| Phase | IN Scope | OUT of Scope |
|-------|----------|-------------|
| **Product Plan** | Problem, users, success metrics, feature scope (MoSCoW), user flows, phasing, risks | Architecture, technology choices, epic/story breakout, database design, API design |
| **Architecture** | System design, component boundaries, technology decisions, ADRs, integration patterns | Product scope changes, detailed API contracts, task breakdown, implementation details |
| **Requirements** | User stories, acceptance criteria (Given/When/Then), edge cases, non-functional requirements | Architecture decisions, task sizing, implementation approach |
| **Technical Design** | Interface contracts, data flow, error strategies, file structure, exit conditions | Product scope changes, architecture overrides, work breakdown, estimation |
| **Work Breakdown** | Epics, stories, tasks, dependencies, agent assignments, parallelization maps | Product decisions, architecture changes, interface contract changes, effort estimates, sprint planning |

**Why this matters:** When a product plan includes architecture decisions, the Architect is reduced to rubber-stamping rather than designing. When a technical design includes work breakdown, the Project Manager has no room to apply sizing constraints. Each agent's value comes from doing their analysis fresh — not from inheriting premature decisions from upstream.

### Conditional Re-Review

After resolving review feedback on any artifact, the user decides whether re-review is necessary:

> **Re-review an updated artifact only if the update involved new design decisions not already triaged by the stakeholder.** If the update is purely incorporating already-triaged decisions, trust the validating agent and proceed — the next downstream phase serves as implicit verification.

This prevents unnecessary review cycles while still catching problems. Each downstream agent naturally verifies the upstream artifact because they must build on it:

| Artifact Updated After | Downstream Verifier | Implicit Verification |
|---|---|---|
| Product Plan Validation (Phase 3) | Architect (Phase 4) | Flags product plan inconsistencies while designing |
| Architecture Validation (Phase 6) | Requirements Analyst (Phase 7) | Flags architecture inconsistencies while writing requirements |
| Requirements Review (Phase 8) | Tech Lead (Phase 9) | Flags requirements inconsistencies while designing |
| TD Review (Phase 10) | Project Manager (Phase 11) | Flags TD inconsistencies while breaking down work |

If a downstream agent discovers an inconsistency, pause and resolve it before continuing — don't work around it. This is cheaper than discovering the problem during implementation.

### SDD State Tracking

The SDD workflow is stateful — each phase depends on prior phases. To survive session boundaries and context compaction, the orchestrator maintains a persistent state file at `plans/sdd-state.md`.

**Create this file when starting Phase 1.** Update it at each phase transition (completion, review gate pass, consensus gate). Read it at the start of any new or continued session to resume state.

Template:

```markdown
# SDD Progress

**Current Phase:** 1 — Product Plan
**Delivery Phase:** —
**Status:** In progress

## Completed Phases

| Phase | Label | Artifact | Status |
|-------|-------|----------|--------|

## Consensus Gates

- [ ] Post-Phase 8: Product plan, architecture, and requirements agreed

## Notes

```

Phase transition updates should be minimal — one line change to Current Phase/Status, one row added to Completed Phases. This keeps the file under 2KB even for long workflows.

### Lifecycle

```
Phase 1: Product Plan
  → @product-manager: Product plan (plans/product-plan.md)
    - Problem statement, target users, success metrics
    - Feature scope with MoSCoW prioritization
    - User flows, phasing, risks
    SCOPE: No architecture, no technology choices, no epic/story breakout.
      Anything better decided by downstream agents is left out to avoid
      premature solutioning.

Phase 2: Product Plan Review (parallel)
  → @architect: Review from architecture feasibility perspective
  → @api-designer: Review from API design perspective
  → @security-engineer: Review from security/compliance perspective
  → Orchestrator: Cross-cutting review (see review-governance.md § Orchestrator Review)
  → Reviews written to plans/reviews/product-plan-review-[agent-name].md
  SCOPE CHECK: All reviewers also check for scope violations per the
    Product Plan Review Checklist in review-governance.md (technology
    names in features, epic breakout, architecture decisions, etc.).
    The Architect reviewer is the primary scope checker.
  REVIEW GATE: User steps through each review's recommendations with
    Codex and makes decisions on how to handle them.
  ORCHESTRATOR ASSESSMENT: While agent reviews run, the main session
    reads the artifact independently and prepares its own assessment.
    Use /consolidate-reviews to merge all review files into a
    de-duplicated triage table (see review-governance.md § Review
    Resolution Process).

Phase 3: Product Plan Validation
  → @product-manager: Re-reviews the product plan after changes from
    review feedback. Checks for internal consistency, completeness,
    AND scope compliance (run scope compliance checklist — scope
    violations are commonly introduced during review resolution).
  CONDITIONAL RE-REVIEW: Only re-engage reviewing agents if changes
    involved new design decisions not already triaged by the stakeholder.
    If purely incorporating triaged decisions, proceed — Phase 4 serves
    as implicit verification.

Phase 4: Architecture
  → @architect: Architecture design (plans/architecture.md)
    - System design, component boundaries, data flow
    - Technology decisions with trade-off analysis, ADRs
    - Integration patterns, deployment model
    SCOPE: No product scope changes, no detailed API contracts,
      no implementation details, no task breakdown.
    DOWNSTREAM VERIFICATION: Flag any product plan inconsistencies
      discovered while designing. This serves as implicit verification
      of the post-review product plan.

Phase 5: Architecture Review (parallel)
  → Relevant agents review from their perspectives
    (e.g., @security-engineer, @api-designer, @backend-developer, @sre-engineer)
  → Orchestrator: Cross-cutting review (see review-governance.md § Orchestrator Review)
  → Reviews written to plans/reviews/architecture-review-[agent-name].md
  REVIEW GATE: User steps through review recommendations with Codex.
  ORCHESTRATOR ASSESSMENT: While agent reviews run, the main session
    reads the artifact independently and prepares its own assessment.
    Use /consolidate-reviews to merge all review files into a
    de-duplicated triage table (see review-governance.md § Review
    Resolution Process).

Phase 6: Architecture Validation
  → @architect: Final review of architecture document after changes.
  CONDITIONAL RE-REVIEW: Same rule as Phase 3. Only re-engage
    reviewers if changes involved new design decisions.

Phase 7: Requirements
  → @requirements-analyst: Requirements document (plans/requirements.md)
    - Built from product plan AND architecture
    - Detailed user stories with Given/When/Then acceptance criteria
    - Edge cases, non-functional requirements
    SCOPE: No architecture decisions, no task breakdown,
      no implementation approach.
    DOWNSTREAM VERIFICATION: Flag any architecture inconsistencies
      discovered while writing requirements.
    LARGE PROJECTS: If upstream documents are thorough (5+ Must-Have
      features, or 3-4 with complex architecture), use the hub/index
      pattern: (1) master document (plans/requirements.md, ~300-600 lines)
      with story map, cross-cutting concerns, and dependency map, then
      (2) chunk files (plans/requirements-chunk-{N}-{area}.md, ~800-1300
      lines each) with full Given/When/Then criteria. A single monolithic
      document will exceed output limits at ~2000 lines. See the
      requirements-analyst agent's Large Document Strategy for details.

Phase 8: Requirements Review (parallel)
  → @product-manager: Review for completeness against product plan
  → @architect: Review for alignment with architecture
  → Orchestrator: Cross-cutting review (see review-governance.md § Orchestrator Review)
  → Reviews written to plans/reviews/requirements-review-[agent-name].md
  REVIEW GATE: User steps through review recommendations with Codex.
  CONDITIONAL RE-REVIEW: Same rule — only re-engage reviewers if
    changes involved new design decisions.
  ORCHESTRATOR ASSESSMENT: While agent reviews run, the main session
    reads the artifact independently and prepares its own assessment.
    Use /consolidate-reviews to merge all review files into a
    de-duplicated triage table (see review-governance.md § Review
    Resolution Process).

  ** CONSENSUS GATE: Pause here. Product plan, architecture, and
     requirements must be thorough, well-documented, accurate, and
     agreed upon by all parties (including the user) before proceeding.

--- Per-Phase Design Boundary ---

  Phases 9 onward execute ONE DELIVERY PHASE AT A TIME. Do not design
  multiple delivery phases in a single document. Each delivery phase gets
  its own TD and WB files:
    - plans/technical-design-phase-1.md, plans/technical-design-phase-2.md, etc.
    - plans/work-breakdown-phase-1.md, plans/work-breakdown-phase-2.md, etc.

  After a phase's WB is reviewed and approved, the user decides:
    (a) Implement this phase (recommended -- real implementation informs
        better design for the next phase)
    (b) Continue to the next phase's TD before implementing

  There is no option to design all phases at once. Even if the user
  wants full design approval before implementation, they proceed through
  the per-phase cycle for each phase sequentially. This ensures:
    - Reviewable artifact sizes (~700 lines per TD, not 2,800)
    - Context-window-friendly sessions (one phase per session)
    - Implementation-informed design (Phase 2 TD benefits from Phase 1
      implementation learnings)
    - Natural file naming (phase-N suffix, no ambiguity)

Phase 9: Technical Design (per phase)
  → @tech-lead: Technical Design Document (plans/technical-design-phase-N.md)
    - Concrete interface contracts (actual JSON shapes, actual type definitions)
    - Data flow covering happy path AND error paths
    - Machine-verifiable exit conditions per task (see agent-workflow.md)
    - File structure mapped to actual codebase layout
    - No TBDs in binding contracts
    SCOPE: No product scope changes, no architecture overrides,
      no work breakdown, no estimation.
    DOWNSTREAM VERIFICATION: Flag any requirements inconsistencies
      discovered while designing.

Phase 10: Technical Design Review (parallel)
  → Relevant agents review the TD
  → Orchestrator: Cross-cutting review (see review-governance.md § Orchestrator Review)
  → Reviews written to plans/reviews/technical-design-phase-N-review-[agent-name].md
  REVIEW GATE: Plan review per review-governance.md checklist:
    (1) Contracts concrete, (2) Error paths covered, (3) Exit conditions verifiable,
    (4) File structure maps to codebase, (5) No TBDs in binding contracts
  CONDITIONAL RE-REVIEW: Same rule — only re-engage reviewers if
    changes involved new design decisions.
  ORCHESTRATOR ASSESSMENT: While agent reviews run, the main session
    reads the artifact independently and prepares its own assessment.
    Use /consolidate-reviews to merge all review files into a
    de-duplicated triage table (see review-governance.md § Review
    Resolution Process).

Phase 11: Work Breakdown (per phase)
  → @project-manager: Epics, stories, Work Units, and tasks with:
    - Work Units grouping 2–4 related tasks that share context
    - Tasks written as agent prompts (files to read, steps to execute, commands to verify)
    - 3–5 file scope per task (agent-workflow.md constraint)
    - Machine-verifiable verification commands per task
    - Self-contained — all relevant context inlined, no "see document X"
    - Dependency mapping
    The TD's Context Package maps directly into WU shared context.
    SCOPE: No product decisions, no architecture changes,
      no interface contract changes.
    DOWNSTREAM VERIFICATION: Flag any TD inconsistencies
      discovered while breaking down work.
    METHODOLOGY: Work breakdowns organize by dependency order and
      parallelism opportunities, NOT by time-boxed containers (sprints,
      iterations) or effort estimates (hours, person-days). Sprint
      planning requires a defined team with known capacity. Effort
      estimation requires knowledge of who is doing the work. Agents
      must never fabricate team structure, velocity, or effort/time
      estimates. Use phases, dependency-driven execution order, and
      parallelization maps instead.
      COMPLEXITY SIZING IS ALLOWED: Relative complexity sizing (story
      points, T-shirt sizes) measures difficulty, not duration. This is
      permitted because it does not require team knowledge. Effort/time
      estimates (hours, person-days, sprint velocity) are prohibited.

Phase 12: Work Breakdown Review (per phase)
  → @tech-lead: Review work breakdown against TD
  → Review written to plans/reviews/work-breakdown-phase-N-review-tech-lead.md
  REVIEW GATE: Tech lead validates:
    (1) Story-to-WU mapping is 1:1 and faithful to TD intent
    (2) Dependency chains match actual technical dependencies, not phase ordering
    (3) All exit conditions are machine-verifiable commands
    (4) Stories comply with chunking heuristics (3-5 files, single concern)
    (5) No methodology assumptions (no sprints, no velocity, no effort/time estimates — complexity sizing via story points and T-shirt sizes is allowed)
  CONDITIONAL RE-REVIEW: Same rule as other phases — only re-engage
    if changes involved new design decisions not already triaged.
  ORCHESTRATOR ASSESSMENT: While the tech lead reviews, the main session
    reads the work breakdown independently and prepares its own assessment.
    All findings (tech lead review + orchestrator assessment) are
    consolidated into a single triage table per the Review Resolution
    Process in review-governance.md.

Phase 13: Implementation (per phase, parallel where possible)
  → Assigned implementers (@backend-developer, @frontend-developer, etc.)
  → Each task verified against its exit condition before marking complete
  → If a spec problem is discovered: STOP → revise TD → unblock
    (tech-lead's spec revision protocol)

Phase 14: Review (per phase, parallel)
  → @code-reviewer: Code quality review with anti-rubber-stamping (review-governance.md):
    - At least one finding per review (mandatory findings rule)
    - Test review is not optional — happy-path-only tests are a Warning
    - Scope matching — out-of-scope changes are themselves a finding
  → @security-engineer: Security audit (required for auth, crypto, data deletion code)

Phase 15: Documentation
  → @technical-writer: User docs, API docs, changelog
```

**STATE TRACKING:** Update `plans/sdd-state.md` at every phase transition — when completing a phase, passing a review gate, or reaching a consensus gate. This is the authoritative record of SDD progress that survives session boundaries.

The per-phase cycle (TD -> TD Review -> WB -> WB Review -> Implementation -> Code Review -> Documentation) repeats for each delivery phase defined in the product plan. Always complete one phase's full cycle before starting the next phase's TD. This ensures each phase's design benefits from the previous phase's implementation learnings.

### Artifact Map

| Phase | Output | Path |
|-------|--------|------|
| Product Plan | Product plan | `plans/product-plan.md` |
| Product Plan Review | Agent + orchestrator reviews | `plans/reviews/product-plan-review-[agent-name\|orchestrator].md` |
| Architecture | Architecture design | `plans/architecture.md` |
| Architecture Review | Agent + orchestrator reviews | `plans/reviews/architecture-review-[agent-name\|orchestrator].md` |
| Requirements | Requirements document | `plans/requirements.md` |
| Requirements Review | Agent + orchestrator reviews | `plans/reviews/requirements-review-[agent-name\|orchestrator].md` |
| Technical Design | TD per phase | `plans/technical-design-phase-N.md` |
| TD Review | Agent + orchestrator reviews | `plans/reviews/technical-design-phase-N-review-[agent-name\|orchestrator].md` |
| Work Breakdown | Task plan per phase | `plans/work-breakdown-phase-N.md` |
| Work Breakdown Review | Tech lead review | `plans/reviews/work-breakdown-phase-N-review-tech-lead.md` |
| Review Consolidation | De-duplicated triage table | `plans/reviews/<artifact>-review-consolidated.md` |
| SDD State | Phase progress tracker | `plans/sdd-state.md` |

### When to Use SDD vs. Simpler Workflows

**Only the signals in this table determine whether to use SDD.** Project maturity level (PoC, MVP, Production) is **not** a valid reason to skip SDD phases. Maturity affects the depth of artifacts (e.g., lighter documentation at PoC), not whether phases are executed. If any "Use SDD" signal is present, follow the full phase sequence regardless of maturity.

| Signal | Use SDD | Use Simpler Workflow |
|--------|---------|---------------------|
| New API endpoints or data shapes | Yes | — |
| 3+ implementation tasks | Yes | — |
| Multiple agents need to produce integrating code | Yes | — |
| Cross-cutting concern (auth, logging, error handling) | Yes | — |
| Single file change | — | Direct single-agent routing |
| Bug fix with known root cause | — | Bug Fix workflow |
| Performance optimization | — | Performance Optimization workflow |
| Documentation-only change | — | Direct @technical-writer |
