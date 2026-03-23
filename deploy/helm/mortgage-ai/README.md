# Mortgage AI Helm Chart

Helm chart for deploying the Multi-Agent Loan Origination application to OpenShift.

## Installation

```bash
helm install mortgage-ai ./deploy/helm/mortgage-ai -n mortgage-ai --create-namespace
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
| `secrets.LLM_MODEL_FAST` | Fast tier model name | `gpt-4o-mini` |
| `secrets.LLM_MODEL_CAPABLE` | Capable tier model name | `gpt-4o-mini` |

### MLflow Observability (RHOAI 3.4+)

Enable MLflow tracing when deploying with Red Hat OpenShift AI:

```bash
helm upgrade --install mortgage-ai ./deploy/helm/mortgage-ai \
  --set mlflow.rbac.enabled=true \
  --set secrets.MLFLOW_TRACKING_URI=https://<mlflow-route>/mlflow \
  --set secrets.MLFLOW_EXPERIMENT_NAME=multi-agent-loan-origination \
  --set secrets.MLFLOW_WORKSPACE=<workspace-name> \
  --set secrets.MLFLOW_TRACKING_INSECURE_TLS=true
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `mlflow.rbac.enabled` | Create MLflow RBAC resources | `false` |
| `secrets.MLFLOW_TRACKING_URI` | MLflow server URL | `""` |
| `secrets.MLFLOW_EXPERIMENT_NAME` | Experiment name | `""` |
| `secrets.MLFLOW_WORKSPACE` | MLflow workspace (multi-tenant) | `""` |
| `secrets.MLFLOW_TRACKING_TOKEN` | ServiceAccount token | `""` |
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

#### Generating MLflow Token

After deploying with RBAC enabled, generate a token for the ServiceAccount:

```bash
# Generate a 30-day token
TOKEN=$(oc create token mortgage-ai-mlflow-client --duration=720h -n mortgage-ai)

# Update the secret
oc patch secret mortgage-ai-secret -n mortgage-ai \
  --type='json' -p="[{\"op\":\"replace\",\"path\":\"/data/MLFLOW_TRACKING_TOKEN\",\"value\":\"$(echo -n $TOKEN | base64)\"}]"

# Restart API to pick up the new token
oc rollout restart deployment/mortgage-ai-api -n mortgage-ai
```

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
