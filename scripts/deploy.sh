#!/bin/bash
# This project was developed with assistance from AI tools.
#
# Deploy application via Helm to OpenShift.
#
# Usage: scripts/deploy.sh [extra-helm-set-args...]
#
# Env vars (set by Makefile exports):
#   PROJECT_NAME    -- helm release name (default: summit-cap)
#   NAMESPACE       -- OpenShift namespace (default: summit-cap)
#   ENV_FILE        -- env file to source (default: .env)
#   IMAGE_TAG       -- image tag (default: latest)
#   REGISTRY        -- registry host (default: quay.io)
#   REGISTRY_NS     -- registry namespace/org (default: summit-cap)
#   HELM_TIMEOUT    -- helm timeout (default: 15m)
#   HELM_EXTRA_ARGS -- additional helm args (default: empty)
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-summit-cap}"
NAMESPACE="${NAMESPACE:-$PROJECT_NAME}"
ENV_FILE="${ENV_FILE:-.env}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-quay.io}"
REGISTRY_NS="${REGISTRY_NS:-$PROJECT_NAME}"
HELM_TIMEOUT="${HELM_TIMEOUT:-15m}"
HELM_EXTRA_ARGS="${HELM_EXTRA_ARGS:-}"

# Load .env file if present
if [ -f "$ENV_FILE" ]; then
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

helm upgrade --install "$PROJECT_NAME" "./deploy/helm/$PROJECT_NAME" \
    --namespace "$NAMESPACE" \
    --timeout "$HELM_TIMEOUT" \
    --wait \
    --wait-for-jobs \
    --set global.imageRegistry="$REGISTRY" \
    --set global.imageRepository="$REGISTRY_NS" \
    --set global.imageTag="$IMAGE_TAG" \
    --set routes.sharedHost="$PROJECT_NAME-$NAMESPACE.$CLUSTER_DOMAIN" \
    --set secrets.POSTGRES_DB="${POSTGRES_DB:-}" \
    --set secrets.POSTGRES_USER="${POSTGRES_USER:-}" \
    --set secrets.POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}" \
    --set secrets.DATABASE_URL="${DATABASE_URL:-}" \
    --set secrets.COMPLIANCE_DATABASE_URL="${COMPLIANCE_DATABASE_URL:-}" \
    --set secrets.DEBUG="${DEBUG:-}" \
    --set secrets.ALLOWED_HOSTS="${ALLOWED_HOSTS:-}" \
    --set secrets.AUTH_DISABLED="${AUTH_DISABLED:-}" \
    --set secrets.KEYCLOAK_URL="${KEYCLOAK_URL:-}" \
    --set secrets.KEYCLOAK_REALM="${KEYCLOAK_REALM:-}" \
    --set secrets.KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-}" \
    --set secrets.JWKS_CACHE_TTL="${JWKS_CACHE_TTL:-}" \
    --set secrets.S3_ENDPOINT="${S3_ENDPOINT:-}" \
    --set secrets.S3_ACCESS_KEY="${S3_ACCESS_KEY:-}" \
    --set secrets.S3_SECRET_KEY="${S3_SECRET_KEY:-}" \
    --set secrets.S3_BUCKET="${S3_BUCKET:-}" \
    --set secrets.S3_REGION="${S3_REGION:-}" \
    --set secrets.UPLOAD_MAX_SIZE_MB="${UPLOAD_MAX_SIZE_MB:-}" \
    --set secrets.LLM_API_KEY="${LLM_API_KEY:-}" \
    --set secrets.LLM_BASE_URL="${LLM_BASE_URL:-}" \
    --set secrets.LLM_MODEL_FAST="${LLM_MODEL_FAST:-}" \
    --set secrets.LLM_MODEL_CAPABLE="${LLM_MODEL_CAPABLE:-}" \
    --set secrets.SAFETY_MODEL="${SAFETY_MODEL:-}" \
    --set secrets.SAFETY_ENDPOINT="${SAFETY_ENDPOINT:-}" \
    --set secrets.SAFETY_API_KEY="${SAFETY_API_KEY:-}" \
    --set secrets.LANGFUSE_PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-}" \
    --set secrets.LANGFUSE_SECRET_KEY="${LANGFUSE_SECRET_KEY:-}" \
    --set secrets.LANGFUSE_HOST="${LANGFUSE_HOST:-}" \
    --set secrets.SQLADMIN_USER="${SQLADMIN_USER:-}" \
    --set secrets.SQLADMIN_PASSWORD="${SQLADMIN_PASSWORD:-}" \
    --set secrets.SQLADMIN_SECRET_KEY="${SQLADMIN_SECRET_KEY:-}" \
    --set secrets.VITE_API_BASE_URL="${VITE_API_BASE_URL:-}" \
    --set secrets.VITE_ENVIRONMENT="${VITE_ENVIRONMENT:-}" \
    --set secrets.KC_BOOTSTRAP_ADMIN_USERNAME="${KC_BOOTSTRAP_ADMIN_USERNAME:-}" \
    --set secrets.KC_BOOTSTRAP_ADMIN_PASSWORD="${KC_BOOTSTRAP_ADMIN_PASSWORD:-}" \
    --set secrets.MINIO_ROOT_USER="${MINIO_ROOT_USER:-}" \
    --set secrets.MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-}" \
    --set keycloak.enabled="${KEYCLOAK_ENABLED:-true}" \
    --set llamastack.enabled="${LLAMASTACK_ENABLED:-false}" \
    --set langfuse.enabled="${LANGFUSE_ENABLED:-false}" \
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
