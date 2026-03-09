---
description: Customizable project conventions template. Adapt these settings to match your specific project's technology stack, structure, and standards.
user_invocable: false
---

# Project Conventions

Customize the sections below to match your project. All agents reference these conventions when making implementation decisions.

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend Language | Python | 3.11+ |
| Backend Framework | FastAPI | — |
| Data Validation | Pydantic | 2.x |
| AI/Agent Framework | LangGraph | — |
| LLM Stack | LlamaStack (model serving abstraction) | — |
| Observability | LangFuse (self-hosted) | — |
| Fairness Metrics | TrustyAI (Python library) | — |
| Frontend Language | TypeScript | 5.x |
| Frontend Framework | React | 19.x |
| Frontend Build | Vite | 6.x |
| Frontend Routing | TanStack Router | — |
| Frontend State | TanStack Query | — |
| Frontend Styling | Tailwind CSS + shadcn/ui (Radix) | — |
| Database | PostgreSQL + pgvector | 16 |
| ORM | SQLAlchemy 2.0 (async) | — |
| Migrations | Alembic | — |
| Identity | Keycloak (OIDC) | — |
| Backend Testing | pytest | — |
| Frontend Testing | Vitest + React Testing Library | — |
| Backend Package Manager | uv | — |
| Frontend Package Manager | pnpm | — |
| Backend Linting | Ruff | — |
| Frontend Linting | ESLint + Prettier | — |
| Build System | Turborepo | — |
| CI/CD | GitHub Actions | — |
| Container | Podman / Docker | — |
| Platform | OpenShift / Kubernetes | — |

## Project Structure

```
mortgage-ai/
├── packages/
│   ├── ui/                        # React frontend (pnpm) -- 5 persona UIs, chat, dashboards
│   ├── api/                       # FastAPI backend (uv/Python) -- gateway, agents, services
│   │   └── src/
│   │       ├── middleware/        # Auth, RBAC, PII masking
│   │       ├── routes/            # API route handlers
│   │       ├── agents/            # LangGraph agent definitions
│   │       ├── services/          # Domain services (application, document, underwriting,
│   │       │                      #   compliance, audit, analytics, conversation)
│   │       ├── inference/         # LlamaStack wrapper
│   │       └── schemas/           # Pydantic request/response models
│   ├── db/                        # Database models & migrations (uv/Python, separate package)
│   │   ├── src/db/
│   │   │   ├── models/            # SQLAlchemy models (all schemas)
│   │   │   └── database.py        # Engine, session, dual connection pools
│   │   └── alembic/               # Alembic migrations
│   └── configs/                   # Shared ESLint, Prettier, Ruff configs
├── config/
│   ├── app.yaml                   # Application configuration
│   ├── agents/                    # Per-agent config (prompts, tools, routing) -- hot-reloadable
│   ├── models.yaml                # Model routing configuration -- hot-reloadable
│   └── keycloak/
│       └── mortgage-ai-realm.json  # Pre-configured Keycloak realm
├── data/
│   ├── compliance-kb/             # Compliance knowledge base source documents
│   │   ├── tier1-federal/
│   │   ├── tier2-agency/
│   │   └── tier3-internal/
│   └── demo/                      # Demo data seed files
├── deploy/
│   └── helm/                      # Helm charts for OpenShift deployment
├── plans/                         # Planning artifacts (product plan, architecture, requirements)
│   └── reviews/                   # Agent review documents
├── tests/                         # Cross-package integration and e2e tests
├── compose.yml                    # Local development (podman-compose / docker compose)
├── turbo.json                     # Turborepo pipeline configuration
└── Makefile                       # Common development commands
```

## Planning Artifacts (SDD Workflow)

When following the Spec-Driven Development workflow (see `workflow-patterns/SKILL.md`), planning artifacts live in `plans/` with agent reviews in `plans/reviews/`.

| Artifact | Path | Produced By |
|----------|------|-------------|
| Product plan | `plans/product-plan.md` | @product-manager |
| Architecture design | `plans/architecture.md` | @architect |
| Requirements document | `plans/requirements.md` | @requirements-analyst |
| Technical design (per phase) | `plans/technical-design-phase-N.md` | @tech-lead |
| Agent review | `plans/reviews/<artifact>-review-<agent-name>.md` | Reviewing agent |
| Orchestrator review | `plans/reviews/<artifact>-review-orchestrator.md` | Main session (orchestrator) |
| Work breakdown (per phase) | `plans/work-breakdown-phase-N.md` | @project-manager |

### Review File Naming Convention

```
plans/reviews/product-plan-review-architect.md
plans/reviews/product-plan-review-security-engineer.md
plans/reviews/product-plan-review-orchestrator.md
plans/reviews/architecture-review-security-engineer.md
plans/reviews/architecture-review-orchestrator.md
plans/reviews/requirements-review-orchestrator.md
plans/reviews/technical-design-phase-1-review-code-reviewer.md
plans/reviews/technical-design-phase-1-review-orchestrator.md
```

## Environment Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (lending_app role) |
| `HMDA_DATABASE_URL` | Yes | PostgreSQL connection string (compliance_app role) |
| `KEYCLOAK_URL` | Yes | Keycloak server URL |
| `KEYCLOAK_REALM` | No | Keycloak realm name (default: `mortgage-ai`) |
| `LLAMASTACK_URL` | Yes | LlamaStack server endpoint |
| `LANGFUSE_HOST` | No | LangFuse server URL (optional, degrades gracefully) |
| `LANGFUSE_PUBLIC_KEY` | No | LangFuse public key |
| `LANGFUSE_SECRET_KEY` | No | LangFuse secret key |
| `APP_ENV` | No | `development`, `staging`, `production` (default: `development`) |
| `PORT` | No | API server port (default: 8000) |
| `LOG_LEVEL` | No | Logging level (default: `info`) |
| `CORS_ORIGINS` | No | Allowed CORS origins (default: `http://localhost:5173`) |
| `SEED_DEMO_DATA` | No | Seed demo data on startup (default: `true`) |

## Inter-Package Dependencies

```
ui ──────► api (HTTP/WebSocket)
           │
           ├──► db (Python import -- lending_app pool)
           ├──► db (Python import -- compliance_app pool, Compliance Service only)
           ├──► LlamaStack (inference client SDK)
           └──► LangFuse (callback handler)
```

- The `ui` package calls the `api` via HTTP (REST) and WebSocket (chat streaming)
- The `api` package imports models from `db` as a uv workspace path dependency
- The `db` package defines SQLAlchemy models and dual connection pool configuration
- Two PostgreSQL roles (`lending_app`, `compliance_app`) enforce HMDA data isolation at the database level

## Frontend Replaceability

The AI BU may provide their own frontend. The `packages/ui/` React app is a reference implementation, not a permanent dependency. Design rules:

- **Backend owns the contract.** Pydantic schemas are the source of truth. TypeScript types in `packages/ui/` are derived from the OpenAPI spec, not authoritative.
- **No business logic in the frontend.** Auth, RBAC, data scoping, PII masking, and all domain rules are enforced server-side. The frontend renders what the API returns.
- **OpenAPI spec is the integration surface.** FastAPI auto-generates it from Pydantic models. A replacement frontend can generate client types from `/docs` or `/openapi.json`.
- **Standard protocols only.** HTTP REST for data, WebSocket for chat streaming, Keycloak OIDC for auth. No custom frontend-backend coupling beyond these.

## Cross-References

Detailed conventions are defined in the rules files — do not duplicate here:

- **Naming:** `code-style.md`
- **Error handling:** `error-handling.md`
- **Git workflow:** `git-workflow.md`
- **API design:** `api-conventions.md`
- **Frontend patterns:** `ui-development.md` (path-scoped to `packages/ui/`)
- **Database patterns:** `database-development.md` (path-scoped to `packages/db/`)
- **Backend patterns:** `api-development.md` (path-scoped to `packages/api/`)
