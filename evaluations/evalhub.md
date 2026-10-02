# EvalHub on RHOAI

TrustyAI EvalHub is the evaluation harness for Red Hat OpenShift AI (RHOAI). It
combines EvalHub, MLflow, and a KFP v2 Data Science Pipelines Application
(DSPA).

The DSPA stores artifacts in the standalone S4 service in the `evaluations`
namespace. It does not deploy or depend on an operator-managed object store.

## Prerequisites

- RHOAI 3.4+ with MLflow and TrustyAI operators installed
- MLflow CR deployed with `--app-name=kubernetes-auth` and `--enable-workspaces`
- Cluster-admin access for the EvalHub and MLflow RBAC resources
- The shared `aws-compatible-storage-0.1.0.tgz` dependency under
  `deploy/helm/mortgage-ai/charts/`

## Install

The S4 data-connection Secret must exist before Helm installs the chart because
the values overlay uses it as `s3.existingSecret`. The bucket must exist before
the DSPA is created.

```bash
# 1. Create the namespace, direct S3 data connection, and S4 UI credentials.
# Supply non-demo S3 credentials and a local UI credential env file.
oc apply -f evaluations/evalhub/00-namespace.yaml
: "${S4_ACCESS_KEY_ID:?set S4_ACCESS_KEY_ID}"
: "${S4_SECRET_ACCESS_KEY:?set S4_SECRET_ACCESS_KEY}"
: "${S4_UI_CREDENTIALS_FILE:?set a local credentials env-file path}"
oc create secret generic ds-pipeline-s3-dspa -n evaluations \
  --from-literal=AWS_ACCESS_KEY_ID="$S4_ACCESS_KEY_ID" \
  --from-literal=AWS_SECRET_ACCESS_KEY="$S4_SECRET_ACCESS_KEY" \
  --from-literal=AWS_S3_ENDPOINT=http://s4.evaluations.svc.cluster.local:7480 \
  --from-literal=AWS_S3_BUCKET=mlpipeline \
  --from-literal=AWS_DEFAULT_REGION=us-east-1 \
  --dry-run=client -o yaml | oc apply -f -
oc label secret ds-pipeline-s3-dspa -n evaluations opendatahub.io/dashboard=true --overwrite
oc annotate secret ds-pipeline-s3-dspa -n evaluations \
  opendatahub.io/connection-type=s3 \
  openshift.io/display-name='Evaluation Pipeline Artifacts (S4)' --overwrite
oc create secret generic s4-ui-credentials -n evaluations \
  --from-env-file="$S4_UI_CREDENTIALS_FILE" \
  --dry-run=client -o yaml | oc apply -f -

# 2. Install the shared S4 chart. Chart 0.1.0 defaults to S4 0.3.2.
helm upgrade --install evalhub-s4 \
  deploy/helm/mortgage-ai/charts/aws-compatible-storage-0.1.0.tgz \
  --namespace evaluations \
  --values evaluations/evalhub-s4-values.yaml \
  --wait

# 3. Reuse the shared, provider-neutral bucket bootstrap script for mlpipeline.
oc create configmap s4-bucket-bootstrap -n evaluations \
  --from-file=create-buckets.py=deploy/helm/mortgage-ai/files/create-buckets.py \
  --dry-run=client -o yaml | oc apply -f -
oc apply -f evaluations/evalhub/06-s4-bucket-bootstrap.yaml
oc wait --for=condition=complete job/s4-create-mlpipeline -n evaluations --timeout=5m

# 4. Create EvalHub, the DSPA, and their RBAC.
oc apply -k evaluations/evalhub/
```

Verify the prerequisites and resulting services:

```bash
oc get secret ds-pipeline-s3-dspa s4-ui-credentials -n evaluations
oc get job s4-create-mlpipeline -n evaluations
oc get svc s4 -n evaluations
oc get dspa -n evaluations
oc get evalhub -n redhat-ods-applications
oc get pods -n evaluations
```

S4 is internal only: both the UI and S3 API Routes are disabled by default. To
inspect it, port-forward in separate terminals:

```bash
oc port-forward -n evaluations service/s4 5000:5000  # S4 UI
oc port-forward -n evaluations service/s4 7480:7480  # S3 API
```

## What Gets Deployed

| File | What | Namespace |
|------|------|-----------|
| 00-namespace | `evaluations` namespace with tenant labels | - |
| 01-evalhub-cr | EvalHub CR (sqlite, 3 providers) | redhat-ods-applications |
| 02-dspa | KFP v2 DSPA using external S4 storage | evaluations |
| 03-rbac-evaluations | Narrow DSPA API access for the EvalHub job runner | evaluations |
| 04-rbac-mlflow | 2 ClusterRoleBindings for MLflow kubernetes-auth | cluster-scoped |
| 06-s4-bucket-bootstrap | Creates the `mlpipeline` artifact bucket | evaluations |
| 06-rbac-tenant | 3 ClusterRoleBindings for configmap/job creation in tenant namespaces | cluster-scoped |

The RBAC files (03, 04, 06) fix a gap in the TrustyAI operator: it creates ClusterRoles but only binds its own controller-manager SA, not the runtime SAs (`evalhub-service`, `evalhub-redhat-ods-applications-job`).

The `ds-pipeline-s3-dspa` Secret is the data connection and S3 credential
source for both S4 and DSPA:

| Key | Value |
|-----|-------|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S4 credentials |
| `AWS_S3_ENDPOINT` | `http://s4.evaluations.svc.cluster.local:7480` |
| `AWS_S3_BUCKET` | `mlpipeline` |
| `AWS_DEFAULT_REGION` | `us-east-1` |

The local file named by `S4_UI_CREDENTIALS_FILE` supplies non-empty, randomly
generated `username`, `password`, and `jwt` values to the separate
`s4-ui-credentials` Secret. Do not commit that file; the DSPA does not receive
the UI Secret.

The external DSPA configuration uses
`s4.evaluations.svc.cluster.local:7480` over HTTP and retains the
`ds-pipeline-s3-dspa` secret name for downstream consumers. There is no secret
patching Job and no service account with the broad `edit` role. The S4 overlay
keeps S4's own RGW endpoint at `http://localhost:7480`; clients use the service
FQDN in the data connection.

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

## Existing Infrastructure

This procedure manages only the standalone S4 release in `evaluations`. It does
not alter separately managed application sets or historical object-storage
deployments.

## Uninstall

```bash
oc delete -k evaluations/evalhub/
helm uninstall evalhub-s4 -n evaluations
oc delete configmap s4-bucket-bootstrap -n evaluations --ignore-not-found
oc delete secret ds-pipeline-s3-dspa -n evaluations --ignore-not-found
oc delete secret s4-ui-credentials -n evaluations --ignore-not-found
oc delete clusterrolebinding evalhub-service-mlflow-integration evalhub-jobs-mlflow-integration \
  evalhub-service-job-config evalhub-service-jobs-writer evalhub-service-manager
oc delete namespace evaluations
```
