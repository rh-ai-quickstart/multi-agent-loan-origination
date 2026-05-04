# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent loan origination system demonstrating agentic AI on Red Hat OpenShift AI. A fictional mortgage lender with 5 personas (prospect, borrower, loan officer, underwriter, CEO), each served by a dedicated LangGraph agent with role-scoped tools.

**Maturity:** MVP (architected for production growth)

## Quick Commands

```bash
# Setup
make setup              # Install all deps (pnpm + uv)
cp .env.example .env    # Configure LLM endpoint

# Development
make db-start           # Start PostgreSQL + MinIO
make db-upgrade         # Run Alembic migrations
make dev                # Start API (8000) + UI (3000)

# Testing
make test               # All tests via Turborepo
cd packages/api && AUTH_DISABLED=true uv run pytest -v     # API tests (1083)
cd packages/api && AUTH_DISABLED=true uv run pytest -k "test_health"  # Pattern match
pnpm --filter ui test:run           # UI tests (Vitest)

# Linting
make lint               # All packages
cd packages/api && uv run ruff check src/ --fix
pnpm --filter ui lint:fix

# Database migrations
cd packages/db && pnpm migrate:new -m "description"  # Create migration
cd packages/db && pnpm migrate                       # Apply migrations

# Containers
make run                # Full stack (postgres, api, ui, keycloak, mlflow)
make run-minimal        # Just postgres + api + ui
make stop               # Stop all

# OpenShift deployment
make deploy             # Deploy via Helm
make status             # Check deployment
make undeploy           # Tear down
```

## Architecture

### Monorepo Structure (Turborepo + pnpm workspaces)

```
packages/
  api/     # FastAPI backend + LangGraph agents (uv, Python 3.11+)
  ui/      # React 19 frontend (pnpm, Vite, TanStack Router/Query)
  db/      # SQLAlchemy models + Alembic migrations (uv)
  e2e/     # Playwright end-to-end tests (pnpm)
  configs/ # Shared TypeScript configs

config/
  agents/  # Agent YAML configurations (system prompts, tools, routing)
  keycloak/# Realm export for identity
```

### Agent System

Five LangGraph agents in `packages/api/src/agents/`:

| Agent | WebSocket | Key Pattern |
|-------|-----------|-------------|
| Public Assistant | `/api/chat` | Unauthenticated, ephemeral |
| Borrower Assistant | `/api/borrower/chat` | JWT auth, persistent threads |
| LO Assistant | `/api/loan-officer/chat` | Pipeline tools, KB search |
| Underwriter Assistant | `/api/underwriter/chat` | Risk/compliance/decision tools |
| CEO Assistant | `/api/ceo/chat` | Analytics, audit, PII masking |

**Base graph pattern** (`agents/base.py`):
```
input -> input_shield -> classify (rule-based) -> agent_fast / agent_capable
                                                           |
                                        tools <-> agent_capable -> output_shield -> END
```

- Rule-based routing (no LLM call): keywords classify SIMPLE vs COMPLEX
- SIMPLE routes to fast model (no tools), COMPLEX routes to capable model with tools
- Low-confidence fast responses auto-escalate to capable model

### Data Flow

**API Integration (UI):** Component -> Hook -> TanStack Query -> Service -> API
- Zod schemas validate all API responses at service layer
- Components never call services directly

**WebSocket Chat Protocol:**
```json
// Client -> Server
{"type": "message", "content": "user text"}

// Server -> Client
{"type": "token", "content": "partial"}
{"type": "tool_start", "content": "tool_name"}
{"type": "tool_end", "content": "result"}
{"type": "done"}
```

### Database Patterns

- **PostgreSQL 16 + pgvector** for compliance KB embeddings
- **HMDA isolation**: Separate `hmda` schema, dedicated `compliance_app` role, separate connection string (`COMPLIANCE_DATABASE_URL`)
- **Audit hash chains**: Append-only `audit_events` with `prev_hash` linking; triggers block UPDATE/DELETE

### Key Integration Points

- **LLM:** Any OpenAI-compatible endpoint (`LLM_BASE_URL`, `LLM_MODEL`)
- **Embeddings:** Local by default (`nomic-ai/nomic-embed-text-v1.5`); optional remote via `EMBEDDING_PROVIDER=openai_compatible`
- **Auth:** Keycloak OIDC; bypass with `AUTH_DISABLED=true` for dev
- **Storage:** MinIO S3-compatible for documents
- **Observability:** MLflow for agent tracing (optional)

## Critical Patterns

### Adding a New Agent Tool

1. Create tool function in `packages/api/src/agents/<persona>_tools.py`
2. Register in `config/agents/<persona>.yaml` under `tools:`
3. Tool receives `ToolContext` with `user`, `session`, `config`
4. Return structured result (Pydantic model or dict)

### Adding a New API Endpoint

1. Create route in `packages/api/src/routes/<domain>.py`
2. Add Pydantic schemas in `packages/api/src/schemas/<domain>.py`
3. Register router in `packages/api/src/main.py`
4. Add corresponding UI service + hook + Zod schema

### Adding a Database Model

1. Add model class to `packages/db/src/db/models.py`
2. Generate migration: `cd packages/db && pnpm migrate:new -m "add model"`
3. Review generated migration in `alembic/versions/`
4. Apply: `pnpm migrate`

## Environment

Key `.env` variables (see `.env.example` for full list):

```bash
# LLM (required)
LLM_BASE_URL=http://localhost:1234/v1
LLM_MODEL=qwen3-30b-a3b

# Database
DATABASE_URL=postgresql+asyncpg://lending_app:lending_pass@localhost:5433/mortgage-ai

# Dev shortcuts
AUTH_DISABLED=true   # Skip Keycloak
```

## Package READMEs

Detailed documentation for each package:
- [API](packages/api/README.md) - Agents, routes, WebSocket protocol, compliance features
- [UI](packages/ui/README.md) - Components, routing, state management, Storybook
- [DB](packages/db/README.md) - Models, migrations, HMDA isolation

## Additional Rules

The `.claude/` directory contains detailed rules for multi-agent orchestration, code style, testing standards, and review governance. These are loaded automatically and apply to all work in this repository.
