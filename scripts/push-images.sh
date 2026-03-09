#!/bin/bash
# This project was developed with assistance from AI tools.
#
# Tag and push container images to a registry (default: quay.io).
#
# Env vars (set by Makefile exports):
#   CONTAINER_CLI  -- podman or docker (default: podman)
#   IMAGE_TAG      -- image tag (default: latest)
#   REGISTRY       -- registry host (default: quay.io)
#   REGISTRY_NS    -- registry namespace/org (default: mortgage-ai)
set -euo pipefail

CONTAINER_CLI="${CONTAINER_CLI:-podman}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="${REGISTRY:-quay.io}"
REGISTRY_NS="${REGISTRY_NS:-mortgage-ai}"

# Build missing images
need_build=false
if ! $CONTAINER_CLI image exists "mortgage-ai-api:$IMAGE_TAG" 2>/dev/null; then
    echo "API image not found"
    need_build=true
fi
if ! $CONTAINER_CLI image exists "mortgage-ai-ui:$IMAGE_TAG" 2>/dev/null; then
    echo "UI image not found"
    need_build=true
fi
if [ "$need_build" = "true" ]; then
    echo "Building missing images..."
    make build-images
fi

echo "Pushing to $REGISTRY/$REGISTRY_NS..."

# Push API image
$CONTAINER_CLI tag "mortgage-ai-api:$IMAGE_TAG" \
    "$REGISTRY/$REGISTRY_NS/mortgage-ai-api:$IMAGE_TAG"
if ! $CONTAINER_CLI push "$REGISTRY/$REGISTRY_NS/mortgage-ai-api:$IMAGE_TAG"; then
    echo ""
    echo "Failed to push API image."
    echo "Are you logged in?  $CONTAINER_CLI login $REGISTRY"
    exit 1
fi

# Push UI image
$CONTAINER_CLI tag "mortgage-ai-ui:$IMAGE_TAG" \
    "$REGISTRY/$REGISTRY_NS/mortgage-ai-ui:$IMAGE_TAG"
if ! $CONTAINER_CLI push "$REGISTRY/$REGISTRY_NS/mortgage-ai-ui:$IMAGE_TAG"; then
    echo ""
    echo "Failed to push UI image."
    echo "Are you logged in?  $CONTAINER_CLI login $REGISTRY"
    exit 1
fi

echo "Images pushed successfully"
