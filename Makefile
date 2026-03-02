# This project was developed with assistance from AI tools.
#
# Makefile for Summit Cap Financial
#
# Usage:
#   make run            Full stack (all profiles)
#   make run-minimal    Minimal stack (postgres + api + ui)
#   make stop           Stop all containers
#   make help           Show all targets

# -- Tool detection ----------------------------------------------------------

# Auto-detect compose: podman-compose > docker compose v2
# Override with: make run COMPOSE="docker compose"
COMPOSE ?= $(shell command -v podman-compose >/dev/null 2>&1 && echo "podman-compose" || echo "docker compose")

# Auto-detect container CLI: podman > docker (used by build-images / push-images)
# Override with: make build-images CONTAINER_CLI="docker"
CONTAINER_CLI ?= $(shell command -v podman >/dev/null 2>&1 && echo "podman" || echo "docker")

# -- Image registry ----------------------------------------------------------

# Override with: make push-images REGISTRY=my-registry.example.com REGISTRY_NS=my-org
REGISTRY    ?= quay.io
REGISTRY_NS ?= summit-cap

# -- Deployment configuration (OpenShift targets only) -----------------------

PROJECT_NAME    = summit-cap
NAMESPACE      ?= $(PROJECT_NAME)
IMAGE_TAG      ?= latest
HELM_TIMEOUT   ?= 15m
ENV_FILE       ?= .env
HELM_EXTRA_ARGS ?=

# Export vars so scripts/deploy.sh, scripts/push-images.sh etc. can read them
export PROJECT_NAME NAMESPACE REGISTRY REGISTRY_NS IMAGE_TAG CONTAINER_CLI \
       ENV_FILE HELM_TIMEOUT HELM_EXTRA_ARGS

.DEFAULT_GOAL := help

# -- Help --------------------------------------------------------------------

help:
	@echo "Available targets:"
	@echo ""
	@echo "  Local stack:"
	@echo "    run              Start full stack (all profiles)"
	@echo "    run-minimal      Start minimal stack (postgres + api + ui)"
	@echo "    run-auth         Start with auth profile (+ keycloak)"
	@echo "    run-ai           Start with ai profile (+ llamastack)"
	@echo "    run-obs          Start with observability profile (+ langfuse)"
	@echo "    stop             Stop all containers"
	@echo ""
	@echo "  Development:"
	@echo "    setup            Install dependencies for all packages"
	@echo "    dev              Run dev servers (turbo dev)"
	@echo "    build            Build all packages"
	@echo "    test             Run tests for all packages"
	@echo "    lint             Run linters for all packages"
	@echo "    clean            Remove build artifacts and dependencies"
	@echo ""
	@echo "  Database:"
	@echo "    db-start         Start the database container"
	@echo "    db-stop          Stop the database container"
	@echo "    db-logs          View database container logs"
	@echo "    db-upgrade       Run database migrations"
	@echo ""
	@echo "  Containers:"
	@echo "    containers-build Build all container images (compose build)"
	@echo "    containers-up    Start all containers (alias for run-minimal)"
	@echo "    containers-down  Stop all containers"
	@echo "    containers-logs  View logs for all containers"
	@echo "    build-images     Build API and UI container images"
	@echo "    push-images      Push images to registry (default: quay.io)"
	@echo "    smoke            Smoke test: start stack, check endpoints, tear down"
	@echo ""
	@echo "  Deployment (OpenShift):"
	@echo "    deploy           Deploy application using Helm"
	@echo "    deploy-dev       Deploy in development mode"
	@echo "    undeploy         Remove application deployment"
	@echo "    status           Show deployment status"
	@echo "    debug            Show detailed diagnostics for failed deployments"
	@echo "    helm-lint        Lint Helm chart"
	@echo "    helm-template    Render Helm templates"
	@echo ""
	@echo "Run 'make <target>' to execute a target."

# -- Local stack -------------------------------------------------------------

run:
	$(COMPOSE) --profile full up -d
	@echo ""
	@echo "Services starting..."
	@echo "  UI:        http://localhost:3000"
	@echo "  API:       http://localhost:8000"
	@echo "  API Docs:  http://localhost:8000/docs"
	@echo "  LangFuse:  http://localhost:3001"
	@echo "  Keycloak:  http://localhost:8080"

run-minimal:
	$(COMPOSE) up -d

run-auth:
	$(COMPOSE) --profile auth up -d

run-ai:
	$(COMPOSE) --profile ai up -d

run-obs:
	$(COMPOSE) --profile observability up -d

stop:
	$(COMPOSE) --profile full down

# -- Development -------------------------------------------------------------

setup:
	pnpm install
	pnpm -r --if-present install:deps

dev:
	pnpm dev

build:
	pnpm build

test:
	pnpm test

lint:
	pnpm lint

lint-hmda:
	@scripts/lint-hmda-isolation.sh

clean:
	pnpm clean
	rm -rf node_modules
	rm -rf packages/*/node_modules
	rm -rf packages/*/dist
	rm -rf packages/*/build
	rm -rf packages/*/__pycache__
	rm -rf packages/*/.pytest_cache

# -- Database ----------------------------------------------------------------

db-start:
	$(COMPOSE) up -d summit-cap-db

db-stop:
	$(COMPOSE) stop summit-cap-db

db-logs:
	$(COMPOSE) logs -f summit-cap-db

db-upgrade:
	pnpm --filter @*/db migrate

# -- Containers --------------------------------------------------------------

containers-build:
	$(COMPOSE) build

containers-up: run-minimal

containers-down:
	$(COMPOSE) --profile full down

containers-logs:
	$(COMPOSE) logs -f

build-images:
	@echo "Building API image..."
	@$(CONTAINER_CLI) build -f packages/api/Containerfile -t summit-cap-api:$(IMAGE_TAG) .
	@echo "Building UI image..."
	@$(CONTAINER_CLI) build -f packages/ui/Containerfile -t summit-cap-ui:$(IMAGE_TAG) .
	@echo "Images built successfully"

push-images:
	@scripts/push-images.sh

smoke:
	@COMPOSE="$(COMPOSE)" scripts/smoke-test.sh

# -- Deployment (OpenShift) --------------------------------------------------

create-project:
	@echo "Creating OpenShift project: $(NAMESPACE)"
	@oc new-project $(NAMESPACE) || echo "Project $(NAMESPACE) already exists"

helm-dep-update:
	@echo "Updating Helm chart dependencies..."
	@helm dependency update ./deploy/helm/$(PROJECT_NAME) || echo "No dependencies to update"
	@echo "Helm dependencies updated successfully"

deploy: create-project push-images helm-dep-update
	@echo "Deploying application using Helm..."
	@scripts/deploy.sh

deploy-dev: create-project push-images helm-dep-update
	@echo "Deploying application in development mode..."
	@scripts/deploy.sh \
		-f deploy/helm/$(PROJECT_NAME)/values-dev.yaml

undeploy:
	@echo "Undeploying application..."
	@helm uninstall $(PROJECT_NAME) --namespace $(NAMESPACE) || echo "Release $(PROJECT_NAME) not found"
	@echo "Cleanup complete"

status:
	@echo "=== Deployment Status ==="
	@helm status $(PROJECT_NAME) --namespace $(NAMESPACE) 2>/dev/null || echo "Release not found"
	@echo ""
	@echo "=== Pod Status ==="
	@oc get pods -n $(NAMESPACE) 2>/dev/null \
		|| kubectl get pods -n $(NAMESPACE) 2>/dev/null \
		|| echo "Cannot access pods"
	@echo ""
	@echo "=== Services ==="
	@oc get svc -n $(NAMESPACE) 2>/dev/null \
		|| kubectl get svc -n $(NAMESPACE) 2>/dev/null \
		|| echo "Cannot access services"
	@echo ""
	@echo "=== Migration Job Status ==="
	@oc get jobs -n $(NAMESPACE) -l app.kubernetes.io/component=migration 2>/dev/null \
		|| kubectl get jobs -n $(NAMESPACE) -l app.kubernetes.io/component=migration 2>/dev/null \
		|| echo "No migration jobs found"
	@echo ""
	@echo "=== Recent Events ==="
	@oc get events -n $(NAMESPACE) --sort-by='.lastTimestamp' --tail=20 2>/dev/null \
		|| kubectl get events -n $(NAMESPACE) --sort-by='.lastTimestamp' --tail=20 2>/dev/null \
		|| echo "Cannot access events"

debug:
	@scripts/debug-deployment.sh

helm-lint: helm-dep-update
	@echo "Linting Helm chart..."
	@helm lint ./deploy/helm/$(PROJECT_NAME)

helm-template: helm-dep-update
	@if [ -f "$(ENV_FILE)" ]; then \
		set -a; source $(ENV_FILE); set +a; \
	fi; \
	CLUSTER_DOMAIN="$${CLUSTER_DOMAIN:-}"; \
	if [ -z "$$CLUSTER_DOMAIN" ]; then \
		CLUSTER_DOMAIN=$$(oc whoami --show-server 2>/dev/null \
			| sed -E 's|https://api\.([^:]+).*|apps.\1|' || echo ""); \
	fi; \
	helm template $(PROJECT_NAME) ./deploy/helm/$(PROJECT_NAME) \
		--set global.imageRegistry=$(REGISTRY) \
		--set global.imageRepository=$(REGISTRY_NS) \
		--set global.imageTag=$(IMAGE_TAG) \
		--set routes.sharedHost="$(PROJECT_NAME)-$(NAMESPACE).$$CLUSTER_DOMAIN" \
		--set secrets.POSTGRES_DB="$${POSTGRES_DB:-}" \
		--set secrets.POSTGRES_USER="$${POSTGRES_USER:-}" \
		--set secrets.POSTGRES_PASSWORD="$${POSTGRES_PASSWORD:-}" \
		--set secrets.DATABASE_URL="$${DATABASE_URL:-}" \
		--set secrets.DEBUG="$${DEBUG:-}" \
		--set secrets.ALLOWED_HOSTS="$${ALLOWED_HOSTS:-}" \
		--set secrets.VITE_API_BASE_URL="$${VITE_API_BASE_URL:-}" \
		--set secrets.VITE_ENVIRONMENT="$${VITE_ENVIRONMENT:-}"

.PHONY: help run run-minimal run-auth run-ai run-obs stop \
        setup dev build test lint lint-hmda clean \
        db-start db-stop db-logs db-upgrade \
        containers-build containers-up containers-down containers-logs \
        build-images push-images smoke \
        create-project helm-dep-update deploy deploy-dev undeploy status debug \
        helm-lint helm-template
