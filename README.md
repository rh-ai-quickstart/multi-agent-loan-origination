<!-- This project was developed with assistance from AI tools. -->

# Automate mortgage lending with multi-agent AI

Red Hat AI reference application demonstrating agentic AI orchestration across the mortgage lending lifecycle, from prospect inquiry to underwriting approval.

## Table of contents

- [Detailed description](#detailed-description)
  - [See it in action](#see-it-in-action)
  - [Architecture diagrams](#architecture-diagrams)
- [Requirements](#requirements)
  - [Minimum hardware requirements](#minimum-hardware-requirements)
  - [Minimum software requirements](#minimum-software-requirements)
- [Deploy](#deploy)
  - [Delete](#delete)
- [References](#references)
- [Technical details](#technical-details)
  - [Personas](#personas)
  - [Key AI patterns](#key-ai-patterns)
  - [Project structure](#project-structure)
  - [Technology stack](#technology-stack)
  - [Testing](#testing)
  - [Environment configuration](#environment-configuration)
- [Tags](#tags)

## Detailed description

This Red Hat AI reference application showcases multi-agent AI systems on Red Hat OpenShift AI through a realistic, regulated-industry use case. Built for Red Hat Summit, Summit Cap Financial is a fictional mortgage lender that demonstrates how AI can orchestrate complex, multi-persona workflows in financial services.

The application covers the complete mortgage lending lifecycle with five distinct persona experiences: prospect inquiry, borrower application intake, loan officer pipeline management, underwriter compliance checks and risk assessment, and executive analytics. Each persona interacts with a specialized LangGraph agent backed by role-scoped tools, compliance knowledge retrieval, and comprehensive audit trails.

This quickstart demonstrates production-ready AI patterns including role-based access control (RBAC) scoped agent routing, pgvector-based compliance knowledge base with regulatory source tiering, HMDA demographic data isolation, fair lending safeguards, personally identifiable information (PII) masking, model complexity routing, and hash-chained audit events. The architecture deploys to OpenShift AI but also runs locally for development and exploration.

> **Regulatory disclaimer:** All compliance content (HMDA, ECOA, TRID, ATR/QM, FCRA) is simulated for demonstration purposes and does not constitute legal or regulatory advice.

### See it in action

Demo video inclusion/timeline TBD.

### Architecture diagrams

#### System architecture

![System architecture](docs/images/gemini-architecture.png)

#### Agent request flow

![Agent request flow](docs/images/gemini-agent-flow.png)

## Requirements

### Minimum hardware requirements

**For local development:**

- 16GB RAM minimum (32GB recommended for running all services + large language model (LLM) locally)
- 20GB available disk space for container images and model files
- Multi-core CPU (4+ cores recommended)

**For local LLM serving:**

- GPU with 8GB+ VRAM for running LM Studio with 7B-30B parameter models, or
- Access to a cloud-based OpenAI-compatible API endpoint

**For OpenShift deployment:**

- OpenShift cluster with OpenShift AI installed
- Persistent volume claims for PostgreSQL and MinIO storage
- See the [documentation site](https://jeremyary.github.io/multi-agent-loan-origination/) for detailed cluster requirements

### Minimum software requirements

- Node.js 18+ and pnpm 9+
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Podman 4+ and podman-compose
- PostgreSQL 16 (provided via compose for local development)
- An OpenAI-compatible LLM endpoint (LM Studio, virtual large language model (vLLM), OpenAI API, or similar)

## Deploy

### Local development deployment

Clone the repository and install dependencies:

```bash
make setup                # Install all dependencies
cp .env.example .env      # Configure LLM endpoint and model names
```

Edit `.env` to point to your LLM endpoint. For LM Studio running locally:

```env
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=not-needed
LLM_MODEL_FAST=qwen3-30b-a3b
LLM_MODEL_CAPABLE=qwen3-30b-a3b
```

Start the development environment:

```bash
make db-start             # Start PostgreSQL and MinIO
make db-upgrade           # Run database migrations
make dev                  # Start API and UI dev servers
```

The application will be available at the following URLs:

| Service | URL |
|---------|-----|
| Frontend (Vite) | http://localhost:3000 |
| API Server | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Database | postgresql://localhost:5433 |
| MinIO Console | http://localhost:9091 |

### Container deployment

To run the full stack including Keycloak and LangFuse:

```bash
make run      # Start all containers
make stop     # Stop all containers
```

Run `make help` for additional container targets including individual service profiles, image builds, and log streaming.

### OpenShift deployment

Deploy to Red Hat OpenShift AI using Helm:

```bash
make deploy      # Deploy via Helm charts
make status      # Show deployment status
make undeploy    # Remove deployment
```

See the [documentation site](https://jeremyary.github.io/multi-agent-loan-origination/) for detailed OpenShift deployment configuration, resource requirements, and troubleshooting.

### Delete

To tear down the local development environment:

```bash
make stop       # Stop all containers
make clean      # Remove build artifacts and dependencies
```

For OpenShift:

```bash
make undeploy   # Remove Helm deployment
```

## References

- [Documentation Site](https://jeremyary.github.io/multi-agent-loan-origination/)
- [API Documentation](http://localhost:8000/docs) (available when running locally)
- [Red Hat AI Quickstart Catalog](https://github.com/rh-ai-quickstart)
- Package READMEs:
  - [API](packages/api/README.md) - Routes, agents, schemas, WebSocket protocol, testing
  - [UI](packages/ui/README.md) - Components, routing, state management
  - [DB](packages/db/README.md) - Models, migrations, connection management

## Technical details

### Personas

The application implements five distinct persona experiences, each with a specialized LangGraph agent:

| Persona | Role | Agent | Key Capabilities |
|---------|------|-------|-----------------|
| Prospect | Unauthenticated | Public Assistant | Product info, affordability estimates |
| Borrower | `borrower` | Borrower Assistant | Application intake, document upload, status tracking, condition response |
| Loan Officer | `loan_officer` | LO Assistant | Pipeline management, application review, communication drafting, knowledge base search |
| Underwriter | `underwriter` | Underwriter Assistant | Risk assessment, compliance checks, condition management, decisions |
| CEO | `ceo` | CEO Assistant | Pipeline analytics, audit trail, decision trace, model monitoring |

### Key AI patterns

This quickstart demonstrates production-ready AI patterns for regulated industries:

- **Multi-agent orchestration** - Five LangGraph agents with role-scoped tools and RBAC enforcement
- **Compliance knowledge base** - pgvector retrieval-augmented generation (RAG) with tiered boosting (federal regulations > agency guidelines > internal policies)
- **Fair lending safeguards** - HMDA demographic data isolation in separate database schema with access controls
- **Model routing** - Complexity-based routing between fast and capable LLM tiers to optimize cost and latency
- **Comprehensive audit trail** - Hash-chained, append-only audit events with LangFuse trace correlation
- **PII masking** - Middleware-based masking for executive roles (SSN, DOB, account numbers)
- **Safety shields** - Input and output content filters with escalation pattern detection

### Project structure

```
summit-cap/
├── packages/
│   ├── ui/              # React frontend (pnpm)
│   ├── api/             # FastAPI backend + agents (uv)
│   └── db/              # Database models + migrations (uv)
├── config/
│   ├── agents/          # Agent YAML configurations
│   └── keycloak/        # Keycloak realm export
├── deploy/helm/         # Helm charts for OpenShift
├── compose.yml          # Local development services
├── Makefile             # Development commands
└── turbo.json           # Turborepo pipeline config
```

### Technology stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite, TanStack Router/Query, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, LangGraph, SQLAlchemy 2.0 (async), Pydantic 2.x |
| Database | PostgreSQL 16 + pgvector |
| Identity | Keycloak (OpenID Connect) |
| Observability | LangFuse (self-hosted) |
| Object Storage | MinIO (S3-compatible) |
| Deployment | Helm, OpenShift / Kubernetes |
| Build | Turborepo, uv (Python), pnpm (Node.js) |

### Testing

Run tests across all packages:

```bash
make test               # Run all tests
make lint               # Lint all packages
```

Package-specific test commands:

```bash
cd packages/api && uv run pytest -v          # Run 1083 API tests
cd packages/ui && pnpm test:run              # Run UI tests
```

| Package | Framework | Location |
|---------|-----------|----------|
| API | pytest | `packages/api/tests/` |
| UI | Vitest + React Testing Library | `packages/ui/src/**/*.test.tsx` |

### Environment configuration

Copy `.env.example` to `.env` and configure for your environment. Key settings to adjust:

```env
# LLM endpoint (LM Studio, vLLM, or OpenAI)
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=not-needed
LLM_MODEL_FAST=qwen3-30b-a3b
LLM_MODEL_CAPABLE=qwen3-30b-a3b
```

See `.env.example` for all available settings including database connection, authentication, safety shields, and LangFuse observability.

## Tags

- **Industry**: Financial Services
- **Product**: OpenShift AI
- **Use case**: Multi-agent orchestration
- **Contributor org**: Red Hat
