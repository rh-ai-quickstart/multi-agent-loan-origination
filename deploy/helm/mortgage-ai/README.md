# Mortgage AI Helm Chart

Helm chart for deploying the Multi-Agent Loan Origination application to OpenShift.

## Installation

### With values.local.yaml (recommended)

```bash
cp deploy/helm/mortgage-ai/values.local.yaml.example deploy/helm/mortgage-ai/values.local.yaml
# Edit values.local.yaml with your cluster-specific settings
helm upgrade --install mortgage-ai ./deploy/helm/mortgage-ai \
  -n mortgage-ai --create-namespace \
  -f deploy/helm/mortgage-ai/values.local.yaml
```

### Without values.local.yaml (inline --set)

```bash
helm upgrade --install mortgage-ai ./deploy/helm/mortgage-ai \
  -n mortgage-ai --create-namespace \
  --set secrets.LLM_BASE_URL=<llm-endpoint> \
  --set secrets.LLM_API_KEY=<api-key> \
  --set secrets.LLM_MODEL=<model> \
  --set secrets.COMPANY_NAME="<company>" \
  --set secrets.AUTH_DISABLED=true \
  --set keycloak.enabled=false \
  --set secrets.MLFLOW_TRACKING_URI=<mlflow-url> \
  --set secrets.MLFLOW_EXPERIMENT_NAME=<experiment> \
  --set secrets.MLFLOW_WORKSPACE=<workspace> \
  --set secrets.MLFLOW_TRACKING_INSECURE_TLS=true \
  --set mlflow.rbac.enabled=true \
  --set seed.enabled=true
```

## Configuration

### Core Services

| Parameter | Description | Default |
|-----------|-------------|---------|
| `api.enabled` | Deploy API service | `true` |
| `ui.enabled` | Deploy UI service | `true` |
| `database.enabled` | Deploy PostgreSQL | `true` |
| `keycloak.enabled` | Deploy Keycloak | `true` |
| `minio.enabled` | Deploy MinIO | `true` |

### LLM Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `secrets.LLM_BASE_URL` | OpenAI-compatible endpoint | `http://vllm:8000/v1` |
| `secrets.LLM_API_KEY` | API key for LLM endpoint | `not-needed` |
| `secrets.LLM_MODEL` | Primary model name | `gpt-4o-mini` |
| `secrets.VISION_MODEL` | Vision model name (optional, falls back to LLM_MODEL) | `""` |
| `secrets.VISION_BASE_URL` | Vision model endpoint (optional, falls back to LLM_BASE_URL) | `""` |
| `secrets.VISION_API_KEY` | Vision model API key (optional, falls back to LLM_API_KEY) | `""` |

### NeMo Guardrails (Safety Shields)

NeMo Guardrails provides input/output safety filtering via the TrustyAI operator.
When enabled, the API routes all user messages and agent responses through NeMo's
rails (forbidden words, PII detection, content safety) before processing.

#### Quick Start

```bash
helm upgrade --install mortgage-ai ./deploy/helm/mortgage-ai \
  --set nemoGuardrails.enabled=true \
  --set nemoGuardrails.llm.baseUrl=https://<llm-endpoint>/v1 \
  --set nemoGuardrails.llm.modelName=<model-name> \
  --set nemoGuardrails.llm.apiKey=<api-key>
```

When `nemoGuardrails.enabled=true`, the chart automatically sets
`NEMO_GUARDRAILS_ENDPOINT` to the in-cluster NeMo service
(`http://nemo-guardrails-internal:8000`). No manual endpoint configuration needed.

#### Configuration Reference

| Parameter | Description | Default |
|-----------|-------------|---------|
| `nemoGuardrails.enabled` | Deploy NeMo Guardrails CR and wire endpoint | `false` |
| `nemoGuardrails.llm.baseUrl` | LLM endpoint for NeMo response generation | `""` |
| `nemoGuardrails.llm.modelName` | LLM model name | `""` |
| `nemoGuardrails.llm.apiKey` | LLM API key | `""` |
| `secrets.NEMO_GUARDRAILS_ENDPOINT` | Override auto-wired endpoint (external NeMo) | `""` |

#### Testing

```bash
GUARDRAILS_URL=https://<nemo-route> scripts/test-guardrails.sh
```

#### How It Works

The API's `input_shield` and `output_shield` LangGraph nodes call the NeMo server
before and after agent processing. NeMo applies Colang-defined rails:

- **Forbidden words**: Security terms (hack, exploit), inappropriate content, competitor names
- **PII detection**: Email addresses and other sensitive data
- **Content safety**: Via NemoGuard 8B content safety model (optional)

When NeMo blocks a message, the agent returns a refusal. When NeMo allows it,
the agent processes normally with its own LLM call.

### MLflow Observability (RHOAI 3.4+)

Enable MLflow tracing when deploying with Red Hat OpenShift AI.

#### Authentication: Kubernetes Plugin (recommended)

On RHOAI 3.4+, set `MLFLOW_TRACKING_AUTH=kubernetes` for automatic authentication
via the mounted ServiceAccount token. No manual token generation needed:

```bash
helm upgrade --install mortgage-ai ./deploy/helm/mortgage-ai \
  --set mlflow.rbac.enabled=true \
  --set secrets.MLFLOW_TRACKING_AUTH=kubernetes \
  --set secrets.MLFLOW_TRACKING_URI=https://<mlflow-route>/mlflow \
  --set secrets.MLFLOW_EXPERIMENT_NAME=mortgage-ai \
  --set secrets.MLFLOW_WORKSPACE=mortgage-ai \
  --set secrets.MLFLOW_TRACKING_INSECURE_TLS=true
```

#### Authentication: Manual Token (fallback)

If the Kubernetes auth plugin is not available, generate a token manually:

```bash
# Deploy first (creates the ServiceAccount)
helm upgrade --install mortgage-ai ./deploy/helm/mortgage-ai \
  --set mlflow.rbac.enabled=true \
  --set secrets.MLFLOW_TRACKING_URI=https://<mlflow-route>/mlflow \
  --set secrets.MLFLOW_EXPERIMENT_NAME=mortgage-ai \
  --set secrets.MLFLOW_WORKSPACE=mortgage-ai \
  --set secrets.MLFLOW_TRACKING_INSECURE_TLS=true

# Generate a 30-day token from the mlflow-client ServiceAccount
TOKEN=$(oc create token mortgage-ai-mlflow-client --duration=720h -n mortgage-ai)

# Patch the secret and restart
oc patch secret mortgage-ai-secret -n mortgage-ai \
  --type='json' -p="[{\"op\":\"replace\",\"path\":\"/data/MLFLOW_TRACKING_TOKEN\",\"value\":\"$(echo -n $TOKEN | base64)\"}]"
oc rollout restart deployment/mortgage-ai-api -n mortgage-ai
```

#### Configuration Reference

| Parameter | Description | Default |
|-----------|-------------|---------|
| `mlflow.rbac.enabled` | Create MLflow RBAC resources | `false` |
| `secrets.MLFLOW_TRACKING_URI` | MLflow server URL | `""` |
| `secrets.MLFLOW_TRACKING_AUTH` | Auth mode (`kubernetes` for auto SA auth) | `""` |
| `secrets.MLFLOW_EXPERIMENT_NAME` | Experiment name | `""` |
| `secrets.MLFLOW_WORKSPACE` | MLflow workspace (auto-detected from pod namespace if empty) | `""` |
| `secrets.MLFLOW_TRACKING_TOKEN` | Manual bearer token (not needed with `kubernetes` auth) | `""` |
| `secrets.MLFLOW_TRACKING_INSECURE_TLS` | Skip TLS verification | `false` |

#### MLflow RBAC Resources

When `mlflow.rbac.enabled=true`, the chart creates:

- **ClusterRole** (`mortgage-ai-mlflow-integration`): Permissions for MLflow CRDs
  - `mlflow.kubeflow.org/experiments`: get, list, create, update
  - `mlflow.kubeflow.org/datasets`: get, list, create, update
  - `mlflow.kubeflow.org/registeredmodels`: get, list, create, update
  - `mlflow.kubeflow.org/gatewayendpoints`: get, list
  - `mlflow.kubeflow.org/gatewayendpoints/use`: create

- **ServiceAccount** (`mortgage-ai-mlflow-client`): Identity for MLflow authentication

- **ClusterRoleBinding**: Connects the ServiceAccount to the ClusterRole

### Kagenti A2A Integration

Enable [Kagenti](https://github.com/kagenti/kagenti) to expose all 5 LangGraph agents as [A2A (Agent-to-Agent)](https://google.github.io/A2A/) endpoints. Other agents, orchestrators, or the Kagenti UI can then discover and invoke them programmatically.

See [docs/kagenti.md](../../docs/kagenti.md) for full architecture details, screenshots, and SPIFFE identity tagging.

#### Prerequisites

- Kagenti operator installed on the cluster
- SPIRE server running (provides workload identity via SPIFFE)
- Target namespace labeled: `oc label namespace <ns> kagenti-enabled=true`
- `kagenti-authbridge` SCC granted to the API service account:
  ```bash
  oc adm policy add-scc-to-user kagenti-authbridge -z mortgage-ai-mlflow-client -n <ns>
  ```

#### Quick Start

```bash
helm upgrade --install mortgage-ai ./deploy/helm/mortgage-ai \
  -n <ns> \
  --set kagenti.enabled=true \
  --set secrets.KAGENTI_ENABLED=true \
  --set api.image.tag=kagentiv1
```

#### Configuration Reference

| Parameter | Description | Default |
|-----------|-------------|---------|
| `kagenti.enabled` | Enable Kagenti labels, annotations, ports, and AgentRuntime CR | `false` |
| `kagenti.a2aBasePort` | First A2A port (agents use 8080-8084) | `8080` |
| `kagenti.inboundPortsExclude` | Ports excluded from AuthBridge inbound proxying | `"8000"` |
| `kagenti.outboundPortsExclude` | Ports excluded from AuthBridge outbound proxying | `"5432,9000,8081"` |
| `secrets.KAGENTI_ENABLED` | Feature flag read by the API at runtime | `false` |
| `secrets.KAGENTI_SERVICE_NAME` | Service name used in A2A agent card endpoints | `"mortgage-ai-api"` |

#### What the Chart Creates

When `kagenti.enabled=true`, the chart adds:

- **Deployment metadata labels**: `kagenti.io/type: agent`, `protocol.kagenti.io/a2a: ""`
- **Pod template annotations**: `kagenti.io/inject: "enabled"`, `kagenti.io/spire: "enabled"`, port exclusions
- **Container ports**: 5 additional ports (8080-8084) for the A2A servers
- **SVID volume mount**: `svid-output` emptyDir mounted at `/spiffe` in the API container for SPIRE identity access
- **AgentRuntime CR**: `kagenti-agentruntime.yaml` -- tells Kagenti to manage this deployment

Kagenti's webhook then injects two sidecars into the pod:

| Container | Purpose |
|-----------|---------|
| `envoy-proxy` | AuthBridge -- enforces mTLS and JWT auth on A2A ports |
| `spiffe-helper` | Fetches and rotates SPIFFE identity (X.509 certs + JWT SVIDs) |

#### Verify

```bash
# Check all 3 containers are running (api + 2 Kagenti sidecars)
oc get pod -l app.kubernetes.io/component=api -n <ns> \
  -o jsonpath='{range .items[0].spec.containers[*]}{.name}{"\n"}{end}'
# Expected: api, envoy-proxy, spiffe-helper

# Check AgentCard was created and synced
oc get agentcard -n <ns>

# Check SPIFFE identity is available in the API container
oc exec deploy/mortgage-ai-api -c api -n <ns> -- ls /spiffe/
# Expected: jwt_svid.token  svid.pem  svid_key.pem  svid_bundle.pem

# Test agent card endpoint
oc exec deploy/mortgage-ai-api -c api -n <ns> -- \
  curl -s localhost:8000/.well-known/agent-card.json | python3 -m json.tool
```

#### SPIFFE Identity in MLflow Traces

When Kagenti/SPIRE is active, every MLflow trace is tagged with the workload's SPIFFE identity (`spiffe.id`, `spiffe.audience`, `spiffe.issuer`, `spiffe.expiry`, `spiffe.jwt_svid`, `spiffe.x509_svid`). This works on both the A2A path (Kagenti UI) and the WebSocket path (regular UI). See [docs/kagenti.md](../../docs/kagenti.md) for the full tag reference and screenshots.

## External Services

To use external services instead of the chart-provided ones:

```bash
# External database
helm install mortgage-ai ./deploy/helm/mortgage-ai \
  --set database.enabled=false \
  --set secrets.DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# External Keycloak
helm install mortgage-ai ./deploy/helm/mortgage-ai \
  --set keycloak.enabled=false \
  --set secrets.KEYCLOAK_URL=https://keycloak.example.com

# External S3
helm install mortgage-ai ./deploy/helm/mortgage-ai \
  --set minio.enabled=false \
  --set secrets.S3_ENDPOINT=https://s3.amazonaws.com
```

## Troubleshooting

Check deployment status:

```bash
# Pod status
oc get pods -n mortgage-ai

# API logs
oc logs -l app.kubernetes.io/name=mortgage-ai-api -n mortgage-ai

# Check MLflow connection
oc exec deployment/mortgage-ai-api -n mortgage-ai -- python3 -c "
import mlflow
import os
mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI'))
mlflow.set_experiment(os.getenv('MLFLOW_EXPERIMENT_NAME'))
print('MLflow connection: OK')
"
```
