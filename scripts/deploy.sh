#!/bin/bash
# This project was developed with assistance from AI tools.
#
# Deploy application via Helm to OpenShift.
#
# Usage: scripts/deploy.sh [extra-helm-set-args...]
#
# Env vars (set by Makefile exports):
#   PROJECT_NAME    -- helm release name (default: mortgage-ai)
#   NAMESPACE       -- OpenShift namespace (default: mortgage-ai)
#   ENV_FILE        -- env file to source (default: .env)
#   IMAGE_TAG       -- image tag (default: latest)
#   REGISTRY        -- registry host (default: quay.io)
#   REGISTRY_NS     -- registry namespace/org (default: rh-ai-quickstart)
#   HELM_TIMEOUT    -- helm timeout (default: 15m)
#   HELM_EXTRA_ARGS -- additional helm args (default: empty)
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-mortgage-ai}"
NAMESPACE="${NAMESPACE:-$PROJECT_NAME}"
ENV_FILE="${ENV_FILE:-.env}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-quay.io}"
REGISTRY_NS="${REGISTRY_NS:-rh-ai-quickstart}"
HELM_TIMEOUT="${HELM_TIMEOUT:-15m}"
HELM_EXTRA_ARGS="${HELM_EXTRA_ARGS:-}"

# Load env file only when explicitly specified via ENV_FILE.
# The default .env contains local dev values (localhost URLs) that override
# the Helm chart's cluster-internal defaults -- never source it automatically.
if [ "$ENV_FILE" != ".env" ] && [ -f "$ENV_FILE" ]; then
    echo "Loading env from: $ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

# Resolve cluster domain for routes
CLUSTER_DOMAIN="${CLUSTER_DOMAIN:-}"
if [ -z "$CLUSTER_DOMAIN" ]; then
    CLUSTER_DOMAIN=$(oc whoami --show-server 2>/dev/null \
        | sed -E 's|https://api\.([^:]+).*|apps.\1|' || echo "")
fi

echo "Registry:  $REGISTRY/$REGISTRY_NS"
echo "Namespace: $NAMESPACE"

# Build --set args only for env vars that are actually set.
# This avoids overriding values.yaml defaults with empty strings.
SET_ARGS=()

add_if_set() {
    local helm_key="$1"
    local env_var="$2"
    local value="${!env_var:-}"
    if [ -n "$value" ]; then
        SET_ARGS+=(--set "$helm_key=$value")
    fi
}

# Always set (have explicit values)
SET_ARGS+=(--set "global.imageRegistry=$REGISTRY")
SET_ARGS+=(--set "global.imageRepository=$REGISTRY_NS")
SET_ARGS+=(--set "global.imageTag=$IMAGE_TAG")
SET_ARGS+=(--set "routes.sharedHost=$PROJECT_NAME-$NAMESPACE.$CLUSTER_DOMAIN")

# Conditionally set secrets (only override values.yaml when env var is present)
add_if_set secrets.POSTGRES_DB POSTGRES_DB
add_if_set secrets.POSTGRES_USER POSTGRES_USER
add_if_set secrets.POSTGRES_PASSWORD POSTGRES_PASSWORD
add_if_set secrets.DATABASE_URL DATABASE_URL
add_if_set secrets.COMPLIANCE_DATABASE_URL COMPLIANCE_DATABASE_URL
add_if_set secrets.DEBUG DEBUG
add_if_set secrets.ALLOWED_HOSTS ALLOWED_HOSTS
add_if_set secrets.AUTH_DISABLED AUTH_DISABLED
add_if_set secrets.KEYCLOAK_URL KEYCLOAK_URL
add_if_set secrets.KEYCLOAK_ISSUER KEYCLOAK_ISSUER
add_if_set secrets.KEYCLOAK_REALM KEYCLOAK_REALM
add_if_set secrets.KEYCLOAK_CLIENT_ID KEYCLOAK_CLIENT_ID
add_if_set secrets.JWKS_CACHE_TTL JWKS_CACHE_TTL
add_if_set secrets.S3_ENDPOINT S3_ENDPOINT
add_if_set secrets.S3_ACCESS_KEY S3_ACCESS_KEY
add_if_set secrets.S3_SECRET_KEY S3_SECRET_KEY
add_if_set secrets.S3_BUCKET S3_BUCKET
add_if_set secrets.S3_REGION S3_REGION
add_if_set secrets.UPLOAD_MAX_SIZE_MB UPLOAD_MAX_SIZE_MB
add_if_set secrets.LLM_API_KEY LLM_API_KEY
add_if_set secrets.LLM_BASE_URL LLM_BASE_URL
add_if_set secrets.LLM_MODEL_FAST LLM_MODEL_FAST
add_if_set secrets.LLM_MODEL_CAPABLE LLM_MODEL_CAPABLE
add_if_set secrets.EMBEDDING_MODEL EMBEDDING_MODEL
add_if_set secrets.EMBEDDING_PROVIDER EMBEDDING_PROVIDER
add_if_set secrets.EMBEDDING_BASE_URL EMBEDDING_BASE_URL
add_if_set secrets.EMBEDDING_API_KEY EMBEDDING_API_KEY
add_if_set secrets.SAFETY_MODEL SAFETY_MODEL
add_if_set secrets.SAFETY_ENDPOINT SAFETY_ENDPOINT
add_if_set secrets.SAFETY_API_KEY SAFETY_API_KEY
add_if_set secrets.LANGFUSE_PUBLIC_KEY LANGFUSE_PUBLIC_KEY
add_if_set secrets.LANGFUSE_SECRET_KEY LANGFUSE_SECRET_KEY
add_if_set secrets.LANGFUSE_HOST LANGFUSE_HOST
add_if_set secrets.SQLADMIN_USER SQLADMIN_USER
add_if_set secrets.SQLADMIN_PASSWORD SQLADMIN_PASSWORD
add_if_set secrets.SQLADMIN_SECRET_KEY SQLADMIN_SECRET_KEY
add_if_set secrets.KC_BOOTSTRAP_ADMIN_USERNAME KC_BOOTSTRAP_ADMIN_USERNAME
add_if_set secrets.KC_BOOTSTRAP_ADMIN_PASSWORD KC_BOOTSTRAP_ADMIN_PASSWORD
add_if_set secrets.MINIO_ROOT_USER MINIO_ROOT_USER
add_if_set secrets.MINIO_ROOT_PASSWORD MINIO_ROOT_PASSWORD

# Feature toggles (these have safe defaults so always pass)
SET_ARGS+=(--set "keycloak.enabled=${KEYCLOAK_ENABLED:-true}")
SET_ARGS+=(--set "llamastack.enabled=${LLAMASTACK_ENABLED:-false}")
SET_ARGS+=(--set "langfuse.enabled=${LANGFUSE_ENABLED:-false}")

helm upgrade --install "$PROJECT_NAME" "./deploy/helm/$PROJECT_NAME" \
    --namespace "$NAMESPACE" \
    --timeout "$HELM_TIMEOUT" \
    --wait \
    --wait-for-jobs \
    "${SET_ARGS[@]}" \
    "$@" \
    $HELM_EXTRA_ARGS \
    || {
        echo ""
        echo "Helm deployment failed!"
        echo ""
        echo "Run 'make debug' for diagnostics or 'make status' for quick status."
        exit 1
    }

echo "Deployment successful"
