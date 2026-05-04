# Multi-Agent Loan Origination

A Red Hat AI Quickstart demonstrating agentic AI applied to the mortgage lending lifecycle. Part of the [rh-ai-quickstart](https://github.com/rh-ai-quickstart) catalog, this reference application showcases how to build multi-agent AI systems on Red Hat AI / OpenShift AI using a realistic, regulated-industry business use case.

The application uses a fictional mortgage lender (configurable via `COMPANY_NAME` env var, default: "Acme FinTech Company") and covers the process from prospect inquiry through pre-qualification, application, underwriting (including iterative conditions clearing), and approval -- with five distinct persona experiences (Prospect, Borrower, Loan Officer, Underwriter, CEO) sharing a common backend. The mortgage domain was chosen because regulated financial services demand the hardest AI patterns: role-scoped agents, compliance knowledge bases, fair lending guardrails, demographic data isolation, and comprehensive audit trails.

The architecture is MVP-maturity implementation with production structure: component boundaries, data models, and integration patterns are designed so adopters can harden toward production without rearchitecting.

## Project Context

| Attribute | Value |
|-----------|-------|
| **Type** | Red Hat AI Quickstart (reference application) |
| **Maturity** | MVP (architected for production growth) |
| **Domain** | Financial Services -- mortgage lending lifecycle |
| **Primary Users** | Red Hat Summit attendees, Quickstart adopters, AI BU stakeholders |
| **Compliance** | None (MVP) -- but the application demonstrates compliance patterns (HMDA, ECOA, TRID) as part of its purpose |
| **Timeline** | ~3 months targeting Red Hat Summit Spotlight |

Maturity level is **MVP**. See `.claude/rules/maturity-expectations.md` for what that means across testing, error handling, security, documentation, performance, code review, and infrastructure.

## Goals

1. Deliver a fully functional demo covering all 5 personas by mid-May 2025 for the Red Hat Summit Spotlight
2. Showcase Red Hat AI / OpenShift AI capabilities through a credible, domain-rich business use case that exercises advanced AI patterns (multi-agent orchestration, RBAC-scoped agents, compliance RAG, fair lending guardrails, HMDA data isolation, audit trails, model routing)
3. Enable single-command local setup (developer running full app in under 10 minutes)
4. Serve as a reusable Quickstart that developers can clone, deploy on OpenShift AI, explore the patterns, and adapt to their own domain -- with architecture that supports hardening toward production without rearchitecting

## Non-Goals

- Real external system integrations (credit bureaus, MLS, AUS, government databases)
- Real payment processing or financial transactions
- BSA/AML/KYC identity verification workflows
- Production security hardening -- this is an MVP
- Mobile-native applications -- web only
- Multi-tenant / multi-institution support
- Automated underwriting decisions -- all decisions require human confirmation
- Legally accurate regulatory compliance -- realistic but simulated

## Constraints

- **Python 3.11+** backend (stakeholder mandate)
- **LangGraph** for agent orchestration (stakeholder mandate)
- **MLflow** for observability -- integrated with RHOAI 3.4+ for production; self-hosted container for local dev (stakeholder mandate)
- **LlamaStack** for model serving abstraction (stakeholder mandate)
- **FastAPI** + **Pydantic 2.x** (stakeholder mandate)
- **uv** for Python package management, **Ruff** for linting, **pytest** for testing (stakeholder mandate)
- **OpenShift AI** for production model hosting; OpenAI API-compatible endpoints for dev (stakeholder mandate)
- **TrustyAI** Python library for fairness metrics (stakeholder mandate)
- **Keycloak** for identity management (stakeholder preference)
- **Frontend is replaceable** -- the AI BU may provide their own frontend. The backend API (REST + WebSocket), OpenAPI spec, and Keycloak OIDC flow are the contract. All auth, RBAC, business logic, and PII masking are enforced server-side. The `packages/ui/` React app is our default implementation but must not contain logic that a replacement frontend would need to duplicate. Pydantic schemas are the source of truth for data shapes; TypeScript types are derived, not authoritative.
- All regulatory content must carry a "simulated for demonstration purposes" disclaimer
- Compliance KB content must be domain-reviewed before coding -- incorrect regulatory statements are the highest credibility risk

## Key Decisions

- **Language (Backend):** Python 3.11+
- **Language (Frontend):** TypeScript 5.x
- **AI/Agent Framework:** LangGraph
- **Observability:** MLflow (RHOAI 3.4+ / self-hosted)
- **LLM Stack:** LlamaStack (model serving abstraction)
- **Model Hosting:** OpenShift AI (prod); local or OpenAI API-compatible (dev)
- **Web Framework:** FastAPI
- **Data Validation:** Pydantic 2.x
- **Database:** PostgreSQL 16 + pgvector
- **ORM:** SQLAlchemy 2.0 (async)
- **Migrations:** Alembic
- **Frontend Framework:** React 19 (Vite)
- **Frontend Routing:** TanStack Router
- **Frontend State:** TanStack Query
- **Frontend Styling:** Tailwind CSS + shadcn/ui (Radix primitives)
- **Identity:** Keycloak (OIDC)
- **Package Manager (Python):** uv
- **Package Manager (Frontend):** pnpm
- **Build System:** Turborepo
- **Linting/Formatting:** Ruff (Python), ESLint + Prettier (TypeScript)
- **Testing:** pytest (backend), Vitest + React Testing Library (frontend)
- **Container:** Podman / Docker
- **Platform:** OpenShift / Kubernetes
- **Fairness Metrics:** TrustyAI Python library (SPD, DIR)

## Project Commands

```bash
make setup              # Install all dependencies (pnpm install + per-package deps)
make dev                # Start dev servers (turbo dev)
make build              # Build all packages (turbo build)
make test               # Run tests across all packages (turbo test)
make lint               # Run linters for all packages (turbo lint)
make clean              # Remove build artifacts and dependencies

# Database
make db-start           # Start the database container
make db-stop            # Stop the database container
make db-upgrade         # Run database migrations

# Containers (local dev)
make containers-build   # Build all container images
make containers-up      # Start all containers (podman-compose up -d)
make containers-down    # Stop all containers (podman-compose down)
make containers-logs    # View logs for all containers

# OpenShift deployment
make deploy             # Deploy application using Helm
make undeploy           # Remove application deployment
make status             # Show deployment status
make debug              # Show detailed diagnostics for failed deployments

# Package-specific
pnpm --filter ui test           # UI tests (Vitest)
pnpm --filter api test          # API tests (pytest)
cd packages/api && uv run pytest  # API tests directly
cd packages/api && uv run ruff check src/  # Python lint
pnpm --filter ui lint           # UI lint (ESLint)
```

## Stakeholder Preferences

| Preference | Evidence |
|------------|----------|
| Frontend may be replaced by AI BU team | Stakeholder indicated the AI BU may want to build their own frontend. Backend API contract (OpenAPI + WebSocket protocol + OIDC auth) is the integration boundary. Build `packages/ui/` as a reference implementation, but never put business logic or authorization decisions in it. |

---

# Agent System -- Routing & Orchestration

## Routing Decision Matrix

When the user's request matches keywords below, route to the corresponding agent:

| Keywords / Signals | Primary Agent | Secondary |
|---|---|---|
| "product", "PRD", "vision", "roadmap", "feature priority", "discovery", "persona" | Product Manager | Requirements Analyst |
| "design", "architecture", "ADR", "trade-off", "tech stack" | Architect | Tech Lead |
| "technical design", "interface contract", "implementation approach", "how should we build" | Tech Lead | Architect |
| "API", "endpoint", "handler", "middleware", "server" | Backend Developer | API Designer |
| "component", "UI", "CSS", "accessibility", "responsive" | Frontend Developer | — |
| "schema", "migration", "query", "index", "database" | Database Engineer | — |
| "OpenAPI", "contract", "REST", "GraphQL", "versioning" | API Designer | Backend Developer |
| "review", "code quality", "standards", "best practices" | Code Reviewer | — |
| "test", "coverage", "fixture", "mock", "assertion" | Test Engineer | — |
| "security", "vulnerability", "OWASP", "CVE", "auth" | Security Engineer | — |
| "performance", "slow", "profiling", "optimize", "latency" | Performance Engineer | — |
| "deploy", "CI/CD", "Docker", "Kubernetes", "Terraform" | DevOps Engineer | — |
| "epic", "story", "Jira", "backlog", "work breakdown" | Project Manager | — |
| "SLO", "SLI", "runbook", "incident", "on-call", "error budget", "capacity" | SRE Engineer | DevOps Engineer |
| "bug", "error", "crash", "debug", "broken", "not working" | Debug Specialist | — |
| "docs", "README", "changelog", "documentation" | Technical Writer | — |
| "requirements", "user story", "acceptance criteria" | Requirements Analyst | Product Manager |
| Multi-step, cross-cutting, or ambiguous | **Main session** | Use workflow-patterns skill |

## Agent Capabilities Matrix

Mode is determined by the agent's tool set: agents without Write/Edit tools are effectively **read-only** (plan mode); agents with Write/Edit operate in **acceptEdits** mode where file changes are auto-accepted but Bash still requires approval.

| Agent | Model | Mode | Tools | Memory |
|---|---|---|---|---|
| Product Manager | opus | acceptEdits | Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch, AskUserQuestion | project |
| Architect | opus | acceptEdits | Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch | project |
| Backend Developer | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash | — |
| Frontend Developer | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash | — |
| Database Engineer | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash | — |
| API Designer | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash, WebSearch | — |
| Tech Lead | opus | acceptEdits | Read, Write, Edit, Glob, Grep, Bash | project |
| Code Reviewer | opus | plan | Read, Glob, Grep, Bash | project |
| Test Engineer | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash | — |
| Security Engineer | sonnet | plan | Read, Glob, Grep, Bash, WebSearch | project |
| Performance Engineer | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash | — |
| DevOps Engineer | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash | — |
| Project Manager | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash, WebSearch | project |
| SRE Engineer | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash | project |
| Debug Specialist | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash | — |
| Technical Writer | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash, WebSearch | project |
| Requirements Analyst | sonnet | acceptEdits | Read, Write, Edit, Glob, Grep, Bash, WebSearch, AskUserQuestion | project |

## Orchestration Patterns

### Sequential Chain
Tasks execute in strict order. Each task's output feeds the next.
```
A → B → C → D
```
Use `blockedBy` to enforce ordering.

### Parallel Fan-Out
Independent tasks run concurrently, followed by a synchronization point.
```
A → [B, C, D] (parallel) → E
```
B, C, D each have `blockedBy: [A]`. E has `blockedBy: [B, C, D]`.

### Review Gate
Implementation followed by mandatory review before proceeding.
```
implement → [code-reviewer, security-engineer] (parallel) → proceed only if pass
```
If reviewers flag Critical issues, loop back to implementation.

For SDD plan review gates (Phases 2, 5, 8, 10), the orchestrator also participates as a parallel reviewer for cross-cutting issues — see `review-governance.md` § Orchestrator Review.

### Iterative Loop
Profile → implement → verify cycle, repeated until targets are met.
```
performance-engineer (profile) → implementer (fix) → performance-engineer (verify)
```
Repeat if metrics not met.

## Planning Principles

When orchestrating multi-agent work, apply these principles:

- **When in doubt, include a review gate.** Code-reviewer and security-engineer are read-only and cheap.
- **Prefer parallel execution** when tasks are independent — don't create unnecessary sequential chains.
- **Right-size the plan** — a single file change doesn't need 7 agents. Match plan complexity to request complexity.
- **Include context propagation** — each task description should include what prior steps will have produced.
- **Apply chunking heuristics** — each task should touch 3-5 files max, have a machine-verifiable exit condition, and be completable in ~1 hour. Split tasks that violate these limits.
- **Every task needs a verifiable exit condition** in its description (test command, type-check, endpoint assertion). "Implementation complete" is not verifiable.
- **Prefer spec-first** for work involving new data shapes, APIs, or integration points — the cost of specifying before building is always less than the cost of reworking after.

## Session Continuity

At the start of any session, check for `plans/sdd-state.md`. If it exists, read it to understand current SDD progress before asking the user what to do next. This file is the authoritative record of which SDD phase the project is in and what has been completed.

Update `plans/sdd-state.md` at every phase transition — phase completion, review gate pass, consensus gate. See `workflow-patterns` skill § SDD State Tracking for the template and update protocol.

## Cost Tiers

| Tier | Model | Agents | Use When |
|---|---|---|---|
| **High** | opus | Product Manager, Architect, Tech Lead, Code Reviewer | Product strategy, architecture, technical design, code review — errors in planning and review cascade through everything |
| **Standard** | sonnet | All others | Implementation, analysis, project management, documentation — quality sufficient for the task |

Opus is reserved for decisions and reviews with high blast radius: product direction, architecture, technical design (plan quality), and code review (review rigor). All implementation, analysis, and project management work uses sonnet to optimize cost.

## Agent Memory (`memory: project`)

Nine agents have `memory: project` enabled: Product Manager, Architect, Tech Lead, Code Reviewer, Security Engineer, Project Manager, SRE Engineer, Technical Writer, and Requirements Analyst. This means they retain context across sessions for the current project.

**What agents should remember:**

*Agent-specific knowledge:*
- Product vision, personas, success metrics, and feature priorities (Product Manager)
- Architectural decisions and their rationale (Architect)
- Feature-level technical patterns, interface conventions, and implementation approaches that worked well (Tech Lead)
- Recurring code quality patterns — both positive and negative (Code Reviewer)
- Known vulnerabilities, accepted risks, and security exceptions (Security Engineer)
- Estimation accuracy, velocity patterns, and dependency structures (Project Manager)
- SLO targets, incident history, capacity baselines, and operational patterns (SRE Engineer)
- Project terminology, documentation structure, and style preferences (Technical Writer)
- Stakeholder preferences, domain rules, and requirements history (Requirements Analyst)

*Cross-cutting — all memory-enabled agents should track:*
- **Stakeholder preferences** — Decision patterns, risk tolerance, scope tendencies, communication style, technology biases. When you observe a consistent preference across interactions (e.g., "stakeholder always defers nice-to-haves to Phase 2", "prefers conservative technology choices"), record it. Over time, this lets agents anticipate preferences rather than re-asking. The canonical record lives in the root `CLAUDE.md` Stakeholder Preferences table — update it when a pattern is clear.

**What agents should NOT remember:**
- Transient debugging state or temporary workarounds
- Content of secret/credential values encountered during sessions
- Personal preferences of individual developers (use `settings.local.json` for those)

**When agents should write memory:**

Agents with `memory: project` should write to their memory file at the end of any session where they:
- Made or discovered a significant decision (architecture choice, design pattern, stakeholder preference)
- Encountered a recurring pattern (positive or negative) worth capturing for future sessions
- Completed a planning artifact that downstream agents will need to reference
- Discovered a constraint or gotcha that isn't documented elsewhere

Memory is only valuable if agents proactively write it. The "what to remember" list above is not sufficient on its own -- agents must actively persist their learnings before their session ends.

Memory builds up naturally over sessions. Agents with memory become more effective as the project matures because they can reference prior decisions and patterns without re-reading every file.
