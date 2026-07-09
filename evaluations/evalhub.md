# EvalHub on RHOAI

TrustyAI EvalHub is the evaluation harness for Red Hat OpenShift AI (RHOAI). It provides a framework for evaluating and validating AI/ML models using multiple evaluation providers and benchmark collections. The deployment stack combines EvalHub (evaluation engine), MLflow (experiment tracking), and DSPA (Data Science Pipelines for orchestrating evaluation pipelines via Kubeflow Pipelines v2).

## Prerequisites

- RHOAI 3.4+ with MLflow and TrustyAI operators installed
- MLflow CR deployed with `--app-name=kubernetes-auth` and `--enable-workspaces`
- Cluster admin access

## Install

```bash
oc apply -k evaluations/evalhub/
```

Wait ~2-3 min for DSPA pods, then verify:

```bash
oc get evalhub -n redhat-ods-applications
oc get pods -n evaluations
oc get dspa -n evaluations
oc get routes -n evaluations
oc get routes -n redhat-ods-applications | grep evalhub
```

## What Gets Deployed

| File | What | Namespace |
|------|------|-----------|
| 00-namespace | `evaluations` namespace with tenant labels | - |
| 01-evalhub-cr | EvalHub CR (sqlite, 3 providers) | redhat-ods-applications |
| 02-dspa | DataSciencePipelinesApplication (KFP v2, in-cluster MinIO) | evaluations |
| 03-rbac-evaluations | Role + 2 RoleBindings for job runner DSPA access | evaluations |
| 04-rbac-mlflow | 2 ClusterRoleBindings for MLflow kubernetes-auth | cluster-scoped |
| 05-secret-patcher | Job that patches DSPA S3 secret with AWS-style keys | evaluations |
| 06-rbac-tenant | 3 ClusterRoleBindings for configmap/job creation in tenant namespaces | cluster-scoped |

The RBAC files (03, 04, 06) fix a gap in the TrustyAI operator: it creates ClusterRoles but only binds its own controller-manager SA, not the runtime SAs (`evalhub-service`, `evalhub-redhat-ods-applications-job`).

### Resource Summary

Once deployed, you should see the following:

**EvalHub CR** (`redhat-ods-applications`):

| Resource | Name | Notes |
|----------|------|-------|
| EvalHub | `evalhub` | Ready |
| Route | `evalhub` | External URL at `https://evalhub-redhat-ods-applications.apps.<cluster-domain>` |

Internal URL: `https://evalhub.redhat-ods-applications.svc.cluster.local:8443`

Active evaluation providers:
- `garak`
- `garak-kfp`
- `lm-evaluation-harness`

Active benchmark collections:
- `leaderboard-v2`
- `safety-and-fairness-v1`
- `toxicity-and-ethical-principles`

Configuration:
- Database: SQLite (embedded)
- MLflow tracking URI: `https://mlflow.redhat-ods-applications.svc.cluster.local:8443`
- Replicas: 1

**MLflow** (pre-existing, `redhat-ods-applications`):

- Backend store: `sqlite:////mlflow/mlflow.db`
- Artifacts: `file:///mlflow/artifacts` (serve artifacts enabled)
- Storage: 100Gi PVC (ReadWriteOnce)

**Data Science Pipelines** (`evaluations` namespace):

| Resource | Name |
|----------|------|
| DSPA | `dspa` |
| MinIO | `minio-dspa` |
| MariaDB | `mariadb-dspa` |
| Pipeline Server | `ds-pipeline-dspa` |
| Metadata gRPC | `ds-pipeline-metadata-grpc-dspa` |
| Metadata Envoy | `ds-pipeline-metadata-envoy-dspa` |
| Persistence Agent | `ds-pipeline-persistenceagent-dspa` |
| Scheduled Workflow | `ds-pipeline-scheduledworkflow-dspa` |
| Workflow Controller | `ds-pipeline-workflow-controller-dspa` |

Routes in `evaluations`:
- Pipeline API: `https://ds-pipeline-dspa-evaluations.apps.<cluster-domain>`
- Metadata: `https://ds-pipeline-md-dspa-evaluations.apps.<cluster-domain>`
- MinIO: `https://minio-dspa-evaluations.apps.<cluster-domain>`

**RBAC** (`evaluations` namespace):

- Role `evalhub-jobs-dspa-api` - grants access to DSPA API for evaluation jobs
- RoleBinding `evalhub-jobs-dspa-api` - binds to `evalhub-redhat-ods-applications-job` SA
- RoleBinding `evalhub-jobs-pipeline-management` - binds `ds-pipeline-dspa` role

**Secret Patching Job** (`evaluations` namespace):

Job `update-secret-minio` - patches `ds-pipeline-s3-dspa` secret with AWS-style keys for downstream consumers.

### Namespace Layout

| Namespace | Resources |
|-----------|-----------|
| `redhat-ods-applications` | EvalHub CR, MLflow CR (operator-managed) |
| `evaluations` | DSPA, MinIO, MariaDB, pipeline components, RBAC, secret-patching job |

## Running Benchmarks

### 1. Create the model auth secret

The EvalHub UI "API key" field expects a **Kubernetes secret name**, not a raw key (RHOAIENG-68008). Create the secret first:

```bash
oc create secret generic model-api-key \
  --from-literal=api-key="<your-actual-api-key>" \
  -n evaluations
```

### 2. Configure the SDK

```bash
pip install "eval-hub-sdk[cli]"

evalhub config set base_url https://$(oc get route evalhub -n redhat-ods-applications -o jsonpath='{.spec.host}')
evalhub config set token $(oc whoami -t)
evalhub config set tenant evaluations
```

### 3. Run an evaluation with envsubst

The eval configs use `${VAR}` placeholders so you can target any model without editing the files. Set the variables and pipe through `envsubst`:

```bash
export MODEL_URL="https://litellm-litemaas.apps.prod.rhoai.rh-aiservices-bu.com/v1"
export MODEL_NAME="Qwen3.6-35B-A3B"
export MODEL_TOKENIZER="Qwen/Qwen3.6-35B-A3B"
export MODEL_AUTH_SECRET="model-api-key"
```

| Variable | Description |
|----------|-------------|
| `MODEL_URL` | OpenAI-compatible model endpoint |
| `MODEL_NAME` | Model name as known by the serving endpoint |
| `MODEL_TOKENIZER` | HuggingFace tokenizer path (for lm-evaluation-harness) |
| `MODEL_AUTH_SECRET` | Name of the K8s secret in the `evaluations` namespace containing key `api-key` |

**ARC-Easy:**

```bash
envsubst < evaluations/eval-arceasy.yaml | evalhub eval run --config -
evalhub eval status
```

**OpenLLM Leaderboard v2** (full suite - IFEval, BBH, GPQA, MMLU-Pro, MuSR, MATH-Hard):

```bash
envsubst < evaluations/eval-leaderboard-v2.yaml | evalhub eval run --config -
evalhub eval status
```

To evaluate a different model, just change the exports:

```bash
export MODEL_URL="https://my-other-endpoint/v1"
export MODEL_NAME="granite-3.3-8b-instruct"
export MODEL_TOKENIZER="ibm-granite/granite-3.3-8b-instruct"
export MODEL_AUTH_SECRET="other-model-key"

envsubst < evaluations/eval-arceasy.yaml | evalhub eval run --config -
```

## ArgoCD Note

If ArgoCD manages the target namespaces, disable autosync before installation to prevent conflicts:

```bash
for appset in dspa grafana minio mortgage-ai workspace; do
  oc patch applicationset "$appset" -n openshift-gitops --type=merge \
    -p='{"spec":{"template":{"spec":{"syncPolicy":{"automated":null}}}}}'
done
```

To re-enable after installation:

```bash
for appset in dspa grafana minio mortgage-ai workspace; do
  oc patch applicationset "$appset" -n openshift-gitops --type=merge \
    -p='{"spec":{"template":{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true}}}}}}'
done
```

## Uninstall

```bash
oc delete -k evaluations/evalhub/
oc delete clusterrolebinding evalhub-service-mlflow-integration evalhub-jobs-mlflow-integration \
  evalhub-service-job-config evalhub-service-jobs-writer evalhub-service-manager
oc delete namespace evaluations
```
