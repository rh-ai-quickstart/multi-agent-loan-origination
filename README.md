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
  - [Required user permissions](#required-user-permissions)
- [Deploy](#deploy)
  - [Prerequisites](#prerequisites)
  - [Local development](#local-development)
  - [Try the application](#try-the-application)
  - [Container deployment](#container-deployment)
  - [OpenShift deployment](#openshift-deployment)
  - [In-cluster model serving](#in-cluster-model-serving)
  - [Validating the deployment](#validating-the-deployment)
  - [Delete](#delete)
- [Repository structure](#repository-structure)
- [References](#references)
- [Technical details](#technical-details)
  - [Personas](#personas)
  - [Agents and configuration](#agents-and-configuration)
  - [Key AI patterns](#key-ai-patterns)
  - [Technology stack](#technology-stack)
  - [Testing](#testing)
  - [Environment configuration](#environment-configuration)
  - [MLflow observability](#mlflow-observability-rhoai-34)
  - [Predictive model integration](#predictive-model-integration-optional)
  - [Safety shields, Kagenti, and evaluations](#safety-shields-kagenti-and-evaluations)
- [License](#license)
- [Tags](#tags)

## Detailed description

This Red Hat AI reference application showcases multi-agent AI systems on Red Hat OpenShift AI through a realistic, regulated-industry use case. Built for Red Hat Summit, this application uses a fictional mortgage lender to demonstrate how AI can orchestrate complex, multi-persona workflows in financial services.

![web application ui](docs/images/web-application-ui.png)

The application covers the complete mortgage lending lifecycle with five distinct persona experiences: prospect inquiry, borrower application intake, loan officer pipeline management, underwriter compliance checks and risk assessment, and executive analytics. Each persona interacts with a specialized LangGraph agent backed by role-scoped tools, compliance knowledge retrieval, and comprehensive audit trails.

This quickstart demonstrates AI patterns for regulated industries including role-based access control (RBAC) scoped agent routing, pgvector-based compliance knowledge base with regulatory source tiering, HMDA demographic data isolation, fair lending safeguards, personally identifiable information (PII) masking, vision-based document extraction, and hash-chained audit events. The architecture deploys to OpenShift AI but also runs locally for development and exploration.

> **Regulatory disclaimer:** All compliance content (HMDA, ECOA, TRID, ATR/QM, FCRA) is simulated for demonstration purposes and does not constitute legal or regulatory advice.

### See it in action

[Interactive walkthrough](https://interact.redhat.com/share/UgvwvL982CGksrFdjHT1)

### Architecture diagrams

#### System architecture

![System architecture](docs/images/system-architecture.png)

#### Agent request flow

![Agent request flow](docs/images/agent-request-flow.png)

## Requirements

### Minimum hardware requirements

**For local development:**

- 16GB RAM minimum (32GB recommended for running all services + LLM locally)
- 20GB available disk space for container images and model files
- Multi-core CPU (4+ cores recommended)

**For OpenShift deployment (tested with OpenShift 4.21):**

Application workloads (Helm defaults, excluding any in-cluster LLM):

| Component | CPU request / limit | Memory request / limit | Storage |
|-----------|---------------------|------------------------|---------|
| API | 200m / 1000m | 1Gi / 2Gi | — |
| UI | 50m / 250m | 32Mi / 128Mi | — |
| PostgreSQL | 100m / 500m | 256Mi / 1Gi | 10Gi PVC |
| MinIO | 100m / 500m | 128Mi / 384Mi | 10Gi PVC |
| Keycloak (optional) | 250m / 1000m | 512Mi / 1536Mi | — |
| MCP risk server | 100m / 500m | 256Mi / 512Mi | — |

LLM access via either:

- Model-as-a-Service (MaaS) or any OpenAI-compatible endpoint (no GPU required on the cluster), or
- GPU node for on-cluster model serving, sized for your chosen model. See [In-cluster model serving](#in-cluster-model-serving).

The first API startup downloads a local embedding model (`nomic-ai/nomic-embed-text-v1.5`, 768 dimensions) unless you set `EMBEDDING_PROVIDER=openai_compatible`. Allow extra disk and a Hugging Face download on that first run.

### Minimum software requirements

**Local development:**

- Node.js 22+ and pnpm 9+ (tested with Node.js 22 LTS, pnpm 9.15.9)
- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (tested with Python 3.13, uv 0.11)
- Podman 4+ and podman-compose, or Docker with Compose v2 (Makefile auto-detects; tested with Podman 4.9)
- PostgreSQL 16 with pgvector (provided via compose)
- An OpenAI-compatible LLM endpoint (local inference server, OpenShift AI model serving, or any compatible API)

**OpenShift:**

- OpenShift 4.14+ (tested with OpenShift 4.21)
- Red Hat OpenShift AI 3.4+ if you want MLflow tracing, EvalHub, or in-cluster serving (the app itself can run with only an external LLM URL)
- `oc` CLI matching your cluster, logged in
- Helm 3.12+
- Optional: NVIDIA GPU Operator and a vLLM ServingRuntime if you serve the model on-cluster

### Required user permissions

**Local:** no cluster access. You need permission to bind ports 3000, 8000, 5433, 8081, 9090, and 9091 on your machine (plus 8080 / 5000 / 8321 if you enable Keycloak, MLflow, or LlamaStack).

**OpenShift, preferred demo path** (`keycloak.enabled=false`, `mlflow.rbac.enabled=false`):

- Permission to create a project/namespace
- Permission to create Deployments, Services, Routes, Jobs, PersistentVolumeClaims, Secrets, and ConfigMaps

**OpenShift, default Helm values** (`mlflow.rbac.enabled=true`):

- The chart creates a `ClusterRole` and `ClusterRoleBinding` for MLflow. That requires cluster-admin or equivalent cluster-scoped RBAC. Disable it with `--set mlflow.rbac.enabled=false` if you are a namespace user and do not need MLflow.

Kagenti, NeMo Guardrails content-safety GPUs, and EvalHub have additional operator and cluster-scoped requirements; see [Safety shields, Kagenti, and evaluations](#safety-shields-kagenti-and-evaluations).

## Deploy

### Prerequisites

1. Clone the repository:

   ```bash
   git clone https://github.com/rh-ai-quickstart/multi-agent-loan-origination.git
   cd multi-agent-loan-origination
   ```

2. Provide an OpenAI-compatible LLM. The agents use tool calling; small models (around 3B parameters) are not reliable. You need the chat-completions URL, a model name, and an API key (use `not-needed` if the server does not require one).

3. For OpenShift: `oc login` to the target cluster, and Helm 3 installed. Published images live at `quay.io/rh-ai-quickstart/mortgage-ai-api` and `quay.io/rh-ai-quickstart/mortgage-ai-ui`. Building and pushing your own images is optional.

### Local development

Install dependencies and create an env file:

```bash
make setup                # pnpm install + Python deps (uv) for all packages
cp .env.example .env      # Configure LLM endpoint and model names
```

Edit `.env` at least for the LLM. For a local inference server:

```env
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=not-needed
LLM_MODEL=qwen3-30b-a3b
```

`.env.example` sets `AUTH_DISABLED=true`, so the UI and API run without Keycloak. For host-based `make dev`, also set the MCP risk server to a loopback URL (compose uses a container hostname):

```env
AUTH_DISABLED=true
MCP_RISK_SERVER_URL=http://localhost:8081/mcp
```

Start PostgreSQL, MinIO, and the underwriter MCP risk server, then run migrations and the API/UI:

```bash
# Postgres (host port 5433) + MinIO
make db-start

# MCP risk server used by the underwriter agent (host port 8081)
# Uses the same compose file; first run builds the API image.
podman-compose up -d mcp-risk-server
# or: docker compose up -d mcp-risk-server

make db-upgrade           # Alembic migrations
make dev                  # API (8000) + UI (3000) + Storybook (6006)
```

The API auto-seeds demo applications, borrowers, documents, conditions, and the compliance knowledge base on first startup. The embedding model download can take several minutes; Hugging Face rate limits will stall seeding until the download succeeds.

The application is then available at:

| Service | URL |
|---------|-----|
| Frontend (Vite) | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| SQLAdmin | http://localhost:8000/admin |
| MCP risk server | http://localhost:8081/health |
| PostgreSQL | `postgresql://user:password@localhost:5433/mortgage-ai` |
| MinIO API | http://localhost:9090 |
| MinIO console | http://localhost:9091 (user `minio` / password `miniosecret`) |
| Storybook | http://localhost:6006 |

Run `make help` for every Makefile target.

### Try the application

Open http://localhost:3000. The public landing page (`/`) is the prospect persona (no login). Sign in at http://localhost:3000/sign-in and pick a persona.

**Dev auth** (`AUTH_DISABLED=true`, default in `.env.example`): click a persona on the sign-in page. Password is `demo1234`.

**Keycloak** (`AUTH_DISABLED=false` and Keycloak running): use the same emails with password `demo`. Keycloak itself is http://localhost:8080 (admin / admin). Demo users come from `config/keycloak/mortgage-ai-realm.json`.

| Persona | Sign-in email | Dev password | Keycloak password | UI path |
|---------|---------------|--------------|-------------------|---------|
| Prospect | — | — | — | `/` |
| Borrower (Sarah Mitchell) | `sarah.mitchell@example.com` | `demo1234` | `demo` | `/borrower` |
| Loan officer (James Torres) | `james.torres@example.com` | `demo1234` | `demo` | `/loan-officer` |
| Underwriter (Maria Chen) | `maria.chen@example.com` | `demo1234` | `demo` | `/underwriter` |
| CEO (David Park) | `david.park@example.com` | `demo1234` | `demo` | `/ceo` |

Additional Keycloak users (password `demo` unless noted): `sarah.patel` and `marcus.williams` (loan officers); `admin` / `admin` (admin role).

To re-seed after you have changed demo fixtures:

```bash
cd packages/api && uv run python -m src.seed --force
# or, with AUTH_DISABLED=true:
curl -X POST 'http://localhost:8000/api/admin/seed?force=true'
```

### Container deployment

Compose profiles (see `compose.yml`):

| Profile | Services |
|---------|----------|
| *(default)* | PostgreSQL, MinIO, API, UI, MCP risk server |
| `auth` | + Keycloak |
| `ai` | + LlamaStack |
| `observability` | + MLflow (http://localhost:5000) |
| `full` | all of the above |

```bash
make run-minimal   # default profile
make run-auth      # + Keycloak
make run-ai        # + LlamaStack (http://localhost:8321)
make run-obs       # + MLflow
make run           # --profile full
make stop          # stop the full profile
```

`make run` prints UI, API, Keycloak, and related URLs. Enable Keycloak login by setting `AUTH_DISABLED=false` in `.env` before `make run` / `make run-auth`. For the UI to talk to Keycloak during `make dev` (not the UI container), also set `VITE_KEYCLOAK_URL`, `VITE_KEYCLOAK_REALM`, and `VITE_KEYCLOAK_CLIENT_ID` in `packages/ui/.env.local` as described in [packages/ui/README.md](packages/ui/README.md).

To build and push your own images:

```bash
make build-images CONTAINER_CLI=docker
make push-images CONTAINER_CLI=docker REGISTRY=quay.io REGISTRY_NS=<your-org>
```

`make smoke` starts the minimal stack, checks health endpoints, and tears it down.

### OpenShift deployment

The Helm chart is `deploy/helm/mortgage-ai`. Full value reference: [deploy/helm/mortgage-ai/README.md](deploy/helm/mortgage-ai/README.md).

**Recommended: install with published images** (no local image build or registry push).

```bash
oc new-project mortgage-ai   # or: oc project <existing-namespace>

cp deploy/helm/mortgage-ai/values.local.yaml.example \
   deploy/helm/mortgage-ai/values.local.yaml
```

Edit `values.local.yaml`: set `secrets.LLM_BASE_URL`, `secrets.LLM_API_KEY`, `secrets.LLM_MODEL`, and `routes.sharedHost` to `<project>-<namespace>.apps.<cluster-domain>`. The example file disables Keycloak and sets `AUTH_DISABLED=true` so you can use the persona picker immediately.

```bash
helm upgrade --install mortgage-ai ./deploy/helm/mortgage-ai \
  -n mortgage-ai --create-namespace \
  -f deploy/helm/mortgage-ai/values.local.yaml
```

Equivalent inline install without a values file:

```bash
helm upgrade --install mortgage-ai ./deploy/helm/mortgage-ai \
  -n mortgage-ai --create-namespace \
  --set secrets.LLM_BASE_URL=<llm-endpoint> \
  --set secrets.LLM_API_KEY=<api-key> \
  --set secrets.LLM_MODEL=<model> \
  --set secrets.AUTH_DISABLED=true \
  --set keycloak.enabled=false \
  --set seed.enabled=true \
  --set mlflow.rbac.enabled=false
```

`seed.enabled=true` runs a post-install Job (`python -m src.seed --force`). The API also auto-seeds on startup if the database is empty.

**Optional: `make deploy`** builds images, pushes them to `quay.io/rh-ai-quickstart` (override with `REGISTRY` / `REGISTRY_NS` / `IMAGE_TAG`), then runs `scripts/deploy.sh`. You need write access to that registry, or you will fail at the push step. It also defaults `SEED_ENABLED=true` and `keycloak.enabled=true`. Prefer the Helm commands above unless you intend to ship custom images.

```bash
make deploy NAMESPACE=mortgage-ai REGISTRY=<registry> REGISTRY_NS=<org>
make status
make debug          # if a release fails
```

If `values.local.yaml` exists, `scripts/deploy.sh` passes it as `-f` automatically.

### In-cluster model serving

This chart does not deploy an LLM. Point `LLM_BASE_URL` at MaaS, a local server, or a KServe InferenceService.

The agents send large system prompts (authenticated personas include 12–26 tool definitions, often more than 4,000 tokens) and require tool calling. Combinations that have been used successfully:

| Model | Hardware | Notes |
|-------|----------|--------|
| `qwen3-8b` (for example `quay.io/redhat-ai-services/modelcar-catalog:qwen3-8b`) | 1× NVIDIA T4 16GB via KServe `vllm-gpu-runtime` | Set `--max-model-len=8192` so weights plus KV cache fit. Enable `--enable-auto-tool-choice` and `--tool-call-parser=hermes` or every agent call returns HTTP 400. |
| Larger Qwen3 / Llama-class instruct models (8B+) with a matching tool parser | GPU sized for weights + 8k context | `llama3_json` is the usual parser for Llama; `hermes` for Qwen. |

Avoid `llama-3.2-3b-instruct` for this app: it fits a T4 but is too small for reliable tool calling against these prompts. `granite-3.3-8b-instruct` has been observed to OOM on a 16GB T4 with default context.

Any OpenAI-compatible server (vLLM, LlamaStack, cloud API) works if it implements `/v1/chat/completions` and tool calling.

### Validating the deployment

**Local (`make dev`):**

```bash
curl -sf http://localhost:8000/health/
curl -sf http://localhost:3000/ >/dev/null && echo UI_OK
```

Open http://localhost:3000, use the prospect chat, then sign in as Sarah Mitchell and confirm `/borrower` loads seeded applications.

**Containers:** `make smoke`, or `make run-minimal` and the same curls.

**OpenShift:**

```bash
make status
oc get pods -n mortgage-ai
oc get route -n mortgage-ai

echo "https://$(oc get route mortgage-ai-ui-route -n mortgage-ai -o jsonpath='{.spec.host}')"
curl -sk "https://$(oc get route mortgage-ai-api-health-route -n mortgage-ai -o jsonpath='{.spec.host}')/health/"
```

Expect API, UI, database, MinIO, and MCP risk-server pods `Running` / `Ready`. A seed Job named `mortgage-ai-seed` should complete when `seed.enabled=true`.

### Delete

Local:

```bash
make stop       # Stop compose (full profile)
make db-stop    # Stop only Postgres if you used make db-start
make clean      # Remove build artifacts and node_modules
```

OpenShift:

```bash
make undeploy   # helm uninstall mortgage-ai -n $NAMESPACE
# optional:
oc delete project mortgage-ai
```

PVCs for PostgreSQL and MinIO may remain until the project is deleted.

## Repository structure

```
.
├── packages/
│   ├── ui/              # React frontend (pnpm, Vite, port 3000)
│   ├── api/             # FastAPI + LangGraph agents (uv, port 8000)
│   ├── db/              # SQLAlchemy models + Alembic (uv)
│   ├── e2e/             # Playwright tests (pnpm)
│   └── configs/         # Shared ESLint / Prettier / Ruff config
├── config/
│   ├── agents/          # Per-persona YAML: system prompts, tools, RBAC
│   ├── keycloak/        # Realm export with demo users
│   ├── llamastack/      # LlamaStack run config
│   ├── models.yaml      # LLM / vision / embedding routing (hot-reloaded)
│   └── postgres/        # DB init (pgvector, roles, mlflow DB)
├── data/compliance-kb/  # Tiered regulatory source docs for RAG
├── deploy/helm/mortgage-ai/  # OpenShift Helm chart
├── docs/                # MkDocs site (architecture, personas, API)
├── evaluations/         # MLflow / EvalHub / KFP agent evals
├── scripts/             # deploy, smoke, image push, guardrail tests
├── compose.yml          # Local services (profile-based)
├── Makefile
├── turbo.json
└── .env.example
```

## References

- [Documentation site](https://rh-ai-quickstart.github.io/multi-agent-loan-origination/) (architecture, personas, API)
- [API OpenAPI](http://localhost:8000/docs) (when running locally)
- [Helm chart README](deploy/helm/mortgage-ai/README.md) — values, NeMo Guardrails, MLflow, Kagenti, MCP Gateway
- [API package](packages/api/README.md) — routes, agents, WebSocket protocol, compliance
- [UI package](packages/ui/README.md) — routing, auth, Storybook
- [DB package](packages/db/README.md) — models, migrations, HMDA isolation
- [Evaluations](evaluations/README.md) — MLflow GenAI eval CLI and KFP pipelines
- [Kagenti A2A](docs/kagenti.md) — expose the five agents as A2A services
- [Red Hat AI Quickstart Catalog](https://github.com/rh-ai-quickstart)
- [OpenShift AI documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai/)
- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)

## Technical details

### Personas

Five persona experiences, each with a dedicated LangGraph agent:

| Persona | Role | Agent | Key capabilities |
|---------|------|-------|------------------|
| Prospect | Unauthenticated | Public Assistant | Product info, affordability estimates |
| Borrower | `borrower` | Borrower Assistant | Application intake, document upload, status tracking, condition response |
| Loan Officer | `loan_officer` | LO Assistant | Pipeline management, application review, communication drafting, knowledge base search |
| Underwriter | `underwriter` | Underwriter Assistant | Risk assessment, compliance checks, condition management, decisions |
| CEO | `ceo` | CEO Assistant | Pipeline analytics, audit trail, decision trace, model monitoring |

### Agents and configuration

Agent graphs live in `packages/api/src/agents/`. Prompts, tool allow-lists, and `allowed_roles` are loaded from `config/agents/*.yaml` (not hard-coded). Model endpoints are in `config/models.yaml` and hot-reload when that file changes.

| Agent | Config | WebSocket |
|-------|--------|-----------|
| Public Assistant | `config/agents/public-assistant.yaml` | `/api/chat` |
| Borrower Assistant | `config/agents/borrower-assistant.yaml` | `/api/borrower/chat?token=<jwt>` |
| Loan Officer Assistant | `config/agents/loan-officer-assistant.yaml` | `/api/loan-officer/chat?token=<jwt>` |
| Underwriter Assistant | `config/agents/underwriter-assistant.yaml` | `/api/underwriter/chat?token=<jwt>` |
| CEO Assistant | `config/agents/ceo-assistant.yaml` | `/api/ceo/chat?token=<jwt>` |

Shared graph (`packages/api/src/agents/base.py`):

```
input → input_shield → classify (rule-based SIMPLE vs COMPLEX)
                         → agent_fast (no tools) or agent_capable ↔ tools
                         → output_shield → END
```

SIMPLE queries skip tools. Low-confidence fast responses escalate to the capable path. When `AUTH_DISABLED=true`, the API treats callers as `admin` unless the UI sends `X-Dev-Role` / `X-Dev-User-Id` (the sign-in persona picker does this).

WebSocket messages: client `{"type":"message","content":"..."}`; server `token`, `tool_start`, `tool_end`, `safety_override`, `done`, or `error`. Public chat is ephemeral; authenticated threads persist in PostgreSQL as `user:{userId}:agent:{agent-name}`.

### Key AI patterns

- **Multi-agent orchestration** — five LangGraph agents with role-scoped tools and RBAC
- **Compliance knowledge base** — pgvector RAG with tiered boosting (federal regulations > agency guidelines > internal policies) from `data/compliance-kb/`
- **Fair lending safeguards** — HMDA demographic data in a separate schema with a dedicated `compliance_app` DB role
- **Document extraction** — optional vision model (`VISION_MODEL` / `VISION_BASE_URL`) for uploaded document images
- **Audit trail** — hash-chained, append-only `audit_events` (triggers block UPDATE/DELETE)
- **PII masking** — middleware masking for the CEO role (SSN, DOB, account numbers)
- **Safety shields** — optional NeMo Guardrails (or other OpenAI-compatible safety endpoint) on input and output

### Technology stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite, TanStack Router/Query, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, LangGraph, SQLAlchemy 2.0 (async), Pydantic 2.x |
| Database | PostgreSQL 16 + pgvector |
| Identity | Keycloak 26 (OpenID Connect) |
| Observability | MLflow (RHOAI 3.4+) |
| Object storage | MinIO (S3-compatible) |
| Risk tools | MCP server (`python -m src.mcp_server`, port 8081) |
| Deployment | Helm, OpenShift / Kubernetes |
| Build | Turborepo, uv (Python), pnpm 9.15 (Node.js) |

### Testing

```bash
make test               # All package tests via Turborepo
make lint               # All package linters
make lint-hmda          # HMDA isolation static check
make test-e2e           # Seed + Playwright (needs a running stack)
```

| Package | Framework | Location | Command |
|---------|-----------|----------|---------|
| API | pytest | `packages/api/tests/` | `cd packages/api && AUTH_DISABLED=true uv run pytest -v` |
| UI | Vitest + React Testing Library | `packages/ui/src/**/*.test.tsx` | `pnpm --filter @mortgage-ai/ui test` |
| DB | pytest | `packages/db/tests/` | `cd packages/db && uv run pytest -v` |
| E2E | Playwright | `packages/e2e/` | `make test-e2e` |

### Environment configuration

Copy `.env.example` to `.env`. Settings that most people change:

```env
# Required: any OpenAI-compatible server
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=not-needed
LLM_MODEL=qwen3-30b-a3b

# Local make dev without Keycloak
AUTH_DISABLED=true

# Host-based MCP (compose overrides this to http://mcp-risk-server:8081/mcp)
MCP_RISK_SERVER_URL=http://localhost:8081/mcp

# Optional vision fallback (defaults to LLM_* when empty)
# VISION_MODEL=
# VISION_BASE_URL=
# VISION_API_KEY=

# Optional remote embeddings (default: local nomic-embed-text-v1.5)
# EMBEDDING_PROVIDER=openai_compatible
# EMBEDDING_BASE_URL=
# EMBEDDING_MODEL=
```

Database defaults for compose Postgres on host port 5433:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5433/mortgage-ai
COMPLIANCE_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5433/mortgage-ai
```

The container/Helm API uses `compliance_app` / `compliance_pass` for HMDA. `config/postgres/init-databases.sh` also creates `lending_app` / `lending_pass`. Leave `MLFLOW_TRACKING_URI` empty to disable tracing. See `.env.example` for Keycloak, S3/MinIO, NeMo Guardrails (`NEMO_GUARDRAILS_ENDPOINT`), and UI (`VITE_API_BASE_URL`).

### MLflow observability (RHOAI 3.4+)

On OpenShift AI 3.4+, prefer Kubernetes ServiceAccount auth (no manual token):

```bash
helm upgrade --install mortgage-ai ./deploy/helm/mortgage-ai \
  --set mlflow.rbac.enabled=true \
  --set secrets.MLFLOW_TRACKING_AUTH=kubernetes \
  --set secrets.MLFLOW_TRACKING_URI=https://<mlflow-route>/mlflow \
  --set secrets.MLFLOW_EXPERIMENT_NAME=multi-agent-loan-origination \
  --set secrets.MLFLOW_WORKSPACE=<workspace-name> \
  --set secrets.MLFLOW_TRACKING_INSECURE_TLS=true
```

This requires permission to create ClusterRole objects. Local compose: `make run-obs` or `make run`, then set `MLFLOW_TRACKING_URI=http://localhost:5000`.

Manual token fallback (when the Kubernetes auth plugin is unavailable):

```bash
oc create token mortgage-ai-mlflow-client --duration=720h -n <namespace>

oc patch secret mortgage-ai-secret -n <namespace> \
  --type='json' -p='[{"op":"replace","path":"/data/MLFLOW_TRACKING_TOKEN","value":"'$(echo -n "<token>" | base64)'"}]'
oc rollout restart deployment/mortgage-ai-api -n <namespace>
```

With `mlflow.rbac.enabled=true` the chart creates a ClusterRole (`mlflow.kubeflow.org` experiments, datasets, models, gateway), ServiceAccount `mortgage-ai-mlflow-client`, and a ClusterRoleBinding. More detail: [Helm README](deploy/helm/mortgage-ai/README.md).

### Predictive model integration (optional)

An external predictive ML model can optionally augment the underwriter's risk assessment. When configured, the model classifies loan approval likelihood and its result appears alongside the rule-based risk factors.

Set `PREDICTIVE_MODEL_MCP_URL` to the MCP server's Streamable HTTP endpoint:

```env
# Local development (.env)
PREDICTIVE_MODEL_MCP_URL=http://localhost:8002/mcp
```

```bash
# OpenShift (Helm)
helm upgrade --install mortgage-ai ./deploy/helm/mortgage-ai \
  --set secrets.PREDICTIVE_MODEL_MCP_URL=http://mcp-server.<namespace>.svc.cluster.local:8000/mcp
```

When the variable is unset or empty, the feature is disabled and the underwriter workflow uses the standard risk factors only. If the predictive model server is unreachable at startup, the API logs a warning and continues without it. If the **required** risk MCP server at `MCP_RISK_SERVER_URL` is unreachable, API startup fails.

| Component | Behavior when enabled | Behavior when disabled |
|-----------|----------------------|------------------------|
| API | Calls `check_loan_approval` MCP tool during risk assessment | Skips predictive step, no error |
| UI | Shows 4th "Auto U/W" card in risk assessment grid | Shows 3-column grid (Credit, Capacity, Collateral) |
| Database | Stores `predictive_model_result` and `predictive_model_available` on risk assessment records | Columns remain null |

### Safety shields, Kagenti, and evaluations

**NeMo Guardrails.** Set `NEMO_GUARDRAILS_ENDPOINT` or, on OpenShift, `--set nemoGuardrails.enabled=true` plus LLM settings. The API `input_shield` / `output_shield` nodes call that server. Test with `scripts/test-guardrails.sh`. See [Helm README](deploy/helm/mortgage-ai/README.md#nemo-guardrails-safety-shields).

**Kagenti A2A.** `--set kagenti.enabled=true` and `secrets.KAGENTI_ENABLED=true` expose the five agents on ports 8080–8084 for Agent-to-Agent discovery. Requires the Kagenti operator and SPIRE. See [docs/kagenti.md](docs/kagenti.md).

**MCP Gateway.** `--set mcpGateway.enabled=true` only when the `MCPServerRegistration` CRD is installed.

**Evaluations.** From the repo root, with MLflow configured:

```bash
MLFLOW_TRACKING_TOKEN=$(oc whoami --show-token) uv run python -m evaluations.run_agent_eval --mode simple
```

EvalHub on RHOAI: `oc apply -k evaluations/evalhub/` (cluster-admin). Details: [evaluations/README.md](evaluations/README.md) and [evaluations/evalhub.md](evaluations/evalhub.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Tags

- **Title:** Automate mortgage lending with multi-agent AI
- **Description:** Red Hat AI reference application demonstrating agentic AI orchestration across the mortgage lending lifecycle, from prospect inquiry to underwriting approval.
- **Industry:** Banking and securities
- **Product:** Red Hat OpenShift AI
- **Use case:** Multi-agent orchestration
- **Contributor org:** Red Hat
