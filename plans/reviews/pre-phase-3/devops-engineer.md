# DevOps / Infrastructure Review -- Pre-Phase 3

**Reviewer:** DevOps Engineer
**Date:** 2026-02-26
**Scope:** compose.yml, Containerfiles, Makefile, Helm chart, build system, scripts, environment configuration

---

## OPS-01: API Containerfile installs dev dependencies in production image
**Severity:** Warning
**Location:** `packages/api/Containerfile:21`
**Description:** The builder stage runs `uv pip install --system -e .[dev] || uv pip install --system -e .`. The first attempt installs the `[dev]` extras (pytest, ruff, mypy, testcontainers, etc.) into the builder's site-packages, which are then copied into the runtime image at line 36. This means the production container ships with test frameworks and dev tooling, bloating the image by ~100MB+ and increasing the attack surface.
**Recommendation:** Install only production dependencies in the builder: `uv pip install --system -e .` (no `[dev]`). If dev extras are ever needed (e.g., for a separate test image), create a dedicated build target or a separate Containerfile.

## OPS-02: Unpinned base images use `latest` tag
**Severity:** Warning
**Location:** `compose.yml:159`, `compose.yml:212`
**Description:** Two services use unpinned `latest` tags:
- `llamastack`: `docker.io/llamastack/distribution-starter:latest` (line 159)
- `minio`: `docker.io/minio/minio:latest` (line 212)

These can break without warning when upstream pushes a new version. Other services already pin versions (e.g., `pgvector:pg16`, `keycloak:26.0`, `redis:7-alpine`, `nginx:alpine`).
**Recommendation:** Pin both to specific version tags. For MinIO, use a dated release tag (e.g., `RELEASE.2024-01-01T00-00-00Z`). For LlamaStack, pin to the version that has been tested locally.

## OPS-03: No `.env.example` file
**Severity:** Warning
**Location:** Project root
**Description:** The `.gitignore` excludes `.env` files, and there is no `.env.example` or `.env.template` committed to the repo. The `compose.yml` references several env vars with `${VAR:-default}` syntax (e.g., `AUTH_DISABLED`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_FAST`, `LLM_MODEL_CAPABLE`, `SAFETY_MODEL`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST`). A developer cloning this repo has no single reference for which environment variables exist or what they do.
**Recommendation:** Add a `.env.example` at the root listing all supported environment variables with placeholder/documentation values and inline comments explaining each.

## OPS-04: Makefile auto-detects Docker over Podman despite project mandate
**Severity:** Warning
**Location:** `Makefile:15`
**Description:** The Makefile's COMPOSE auto-detection prefers `docker compose` over `podman-compose`:
```
COMPOSE ?= $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "podman-compose")
```
The project memory and CLAUDE.md both mandate "Always use podman-compose / podman, NOT docker-compose / docker." The current detection order contradicts this: on a system with both installed, Docker wins.
**Recommendation:** Reverse the detection order so `podman-compose` is tried first:
```
COMPOSE ?= $(shell command -v podman-compose >/dev/null 2>&1 && echo "podman-compose" || echo "docker compose")
```
Similarly, `CONTAINER_CLI` at line 19 correctly prefers podman already, so this is an inconsistency between the two detection blocks.

## OPS-05: Helm values.yaml has default passwords in committed file
**Severity:** Warning
**Location:** `deploy/helm/summit-cap/values.yaml:14-17`
**Description:** The Helm `values.yaml` includes default secrets:
```yaml
POSTGRES_PASSWORD: "changeme"
DATABASE_URL: "postgresql+asyncpg://user:changeme@summit-cap-db:5432/summit-cap"
```
While `values.yaml` defaults are normal, "changeme" passwords can easily be deployed if the operator forgets to override them. The `deploy.sh` script passes `--set secrets.POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"` which falls back to empty string, but Helm then uses the `values.yaml` default of "changeme."
**Recommendation:** Set the default values for sensitive fields to empty strings and add a pre-deploy validation step (or Helm `required` function in the template) that fails if secrets are not provided.

## OPS-06: Health check path mismatch between Helm and FastAPI
**Severity:** Warning
**Location:** `deploy/helm/summit-cap/values.yaml:62`, `packages/api/src/main.py:50`
**Description:** The Helm `values.yaml` sets `api.healthCheck.path: /health`, but the FastAPI app registers the health router at prefix `/health` with endpoint `/`, making the actual path `/health/` (with trailing slash). FastAPI will 307 redirect `/health` to `/health/`, which will cause Kubernetes liveness/readiness probes to fail (the probe follows the redirect as a non-2xx response by default depending on the HTTP client).
**Recommendation:** Change the Helm health check path to `/health/` (with trailing slash), or configure the FastAPI health router to handle both `/health` and `/health/`.

## OPS-07: compose.yml port 9000 conflict between ClickHouse and Keycloak health
**Severity:** Warning
**Location:** `compose.yml:148`, `compose.yml:202`
**Description:** The Keycloak health check connects to port 9000 internally (`/dev/tcp/localhost/9000`), and ClickHouse exposes native port 9000 on the host (`ports: - "9000:9000"`). While these are on different containers and don't conflict at the container level, they both expose port 9000 to the host. If both `auth` and `observability` profiles are active simultaneously (as in `full` profile), ClickHouse claims host port 9000. This is not a direct conflict since Keycloak's health check is internal, but the host port 9000 exposure for ClickHouse's native protocol is unnecessary for local development and could confuse developers.
**Recommendation:** Remove the host port mapping for ClickHouse's native port 9000 (keep only 8123 for the HTTP interface) or remap it to a different host port (e.g., `9002:9000`).

## OPS-08: UI Containerfile uses `pnpm@latest` instead of pinned version
**Severity:** Warning
**Location:** `packages/ui/Containerfile:19`
**Description:** The UI build stage runs `corepack prepare pnpm@latest --activate`. The root `package.json` specifies `"packageManager": "pnpm@9.0.0"`, but the Containerfile ignores this and uses the latest version available. This creates a reproducibility gap between local development and container builds.
**Recommendation:** Pin the version to match `package.json`: `corepack prepare pnpm@9.0.0 --activate`. Even better, use `corepack enable` alone since the `packageManager` field in `package.json` already specifies the version.

## OPS-09: UI Containerfile COPY brings all packages including Python API
**Severity:** Warning
**Location:** `packages/ui/Containerfile:13-14`
**Description:** `COPY packages/ ./packages/` copies the entire `packages/` directory including `packages/api/` and `packages/db/` (Python packages) into the Node.js builder stage. This is wasteful -- the UI build only needs `packages/ui/` and `packages/configs/`. While `.dockerignore` excludes `.venv` and `__pycache__`, the Python source files and `pyproject.toml` files are still copied unnecessarily.
**Recommendation:** Use selective COPY:
```dockerfile
COPY packages/ui/ ./packages/ui/
COPY packages/configs/ ./packages/configs/
```

## OPS-10: API Containerfile copies `uv` into runtime stage unnecessarily
**Severity:** Info
**Location:** `packages/api/Containerfile:27`
**Description:** The runtime stage copies `uv` from the builder (`COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv`), but `uv` is not used at runtime -- the application runs with `uvicorn` directly. This adds ~30MB to the final image for no purpose.
**Recommendation:** Remove the `uv` COPY from the runtime stage.

## OPS-11: No lockfile used in API Containerfile
**Severity:** Warning
**Location:** `packages/api/Containerfile:21`
**Description:** The API build uses `uv pip install --system -e .` without a lockfile (`uv.lock`). This means every build resolves dependencies fresh, making builds non-deterministic. If an upstream package pushes a breaking minor/patch release, the container build breaks or behaves differently than the developer's local environment.
**Recommendation:** Generate a `uv.lock` file locally (`uv lock`), commit it, and use `uv pip install --system -r uv.lock` in the Containerfile for deterministic builds.

## OPS-12: UI Containerfile uses triple fallback for package install
**Severity:** Info
**Location:** `packages/ui/Containerfile:23`
**Description:** `RUN pnpm install --no-frozen-lockfile || npm install || yarn install` is a triple fallback chain. This masks failures -- if `pnpm install` fails for a real reason (bad dependency, network issue), it silently falls through to `npm install` which produces a different lockfile format and dependency tree. The comment says "lockfiles may not exist in container builds" but a `pnpm-lock.yaml` should be committed.
**Recommendation:** Commit `pnpm-lock.yaml` and use `pnpm install --frozen-lockfile` in the Containerfile. Remove the npm/yarn fallbacks.

## OPS-13: Helm chart missing MinIO, Keycloak, LLM, and LangFuse services
**Severity:** Warning
**Location:** `deploy/helm/summit-cap/`
**Description:** The Helm chart only defines deployments for API, UI, and PostgreSQL. The compose.yml includes MinIO, Keycloak, LlamaStack, Redis, ClickHouse, LangFuse-web, and LangFuse-worker. For OpenShift deployment, these supporting services have no Helm manifests. The API deployment also does not inject environment variables for MinIO, LLM, Keycloak, or LangFuse connections.
**Recommendation:** Either add Helm templates for supporting services (or reference existing Helm charts as dependencies), or document that these services must be provisioned separately in OpenShift. At minimum, the API deployment template needs env vars for `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `LLM_BASE_URL`, `KEYCLOAK_URL`, `LANGFUSE_*`, and `COMPLIANCE_DATABASE_URL`.

## OPS-14: Helm API deployment missing env vars for Phase 2 services
**Severity:** Warning
**Location:** `deploy/helm/summit-cap/templates/api-deployment.yaml:31-48`
**Description:** The API deployment only injects `DATABASE_URL`, `DEBUG`, and `ALLOWED_HOSTS`. But the API requires many more env vars at runtime (see `packages/api/src/core/config.py`): `COMPLIANCE_DATABASE_URL`, `AUTH_DISABLED`/`KEYCLOAK_URL`, `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL_FAST`/`LLM_MODEL_CAPABLE`, `S3_ENDPOINT`/`S3_ACCESS_KEY`/`S3_SECRET_KEY`/`S3_BUCKET`, `LANGFUSE_*`, `SAFETY_MODEL`, etc. Deploying to OpenShift with the current chart will result in an API that cannot connect to MinIO, the LLM, or LangFuse.
**Recommendation:** Add all required environment variables to both `values.yaml` secrets and the API deployment template, grouped by service (storage, auth, LLM, observability).

## OPS-15: VITE_* env vars injected at runtime have no effect on static build
**Severity:** Warning
**Location:** `deploy/helm/summit-cap/templates/ui-deployment.yaml:32-41`
**Description:** The UI deployment injects `VITE_API_BASE_URL` and `VITE_ENVIRONMENT` as runtime environment variables into the nginx container. However, Vite bakes `import.meta.env.VITE_*` values at build time (during `vite build`). The nginx container serves pre-built static files -- runtime env vars have no effect on the bundled JavaScript. The API URL will be whatever was set during the Docker build, not the runtime value.
**Recommendation:** Either (a) implement a runtime config injection strategy (e.g., generate a `config.js` file at container startup from env vars that the SPA loads), or (b) pass the build-time env vars as build args in the Containerfile and document that images must be rebuilt per environment.

## OPS-16: init-databases.sh does not grant schema permissions
**Severity:** Warning
**Location:** `config/postgres/init-databases.sh:9-12`
**Description:** The script creates `lending_app` and `compliance_app` roles with `LOGIN` and `CONNECT` privileges, but does not grant schema-level permissions (`USAGE`, `SELECT`, `INSERT`, `UPDATE` on schemas/tables). These roles will be able to connect but not actually query any tables until Alembic migrations or manual grants add the permissions.
**Recommendation:** Either add the necessary `GRANT` statements in this init script (e.g., `GRANT USAGE ON SCHEMA public TO lending_app;`), or document that Alembic migrations handle the fine-grained grants and verify this is actually the case.

## OPS-17: Smoke test script relies on python3 for JSON parsing
**Severity:** Info
**Location:** `scripts/smoke-test.sh:42-52`
**Description:** The `wait_for_healthy` and `check_json_field` functions use inline Python3 for JSON parsing. While Python3 is commonly available, this creates an implicit dependency that is not documented. `jq` would be the more standard choice for shell-based JSON processing.
**Recommendation:** Either document the Python3 dependency in the script header, or switch to `jq` which is more conventional for shell scripts and lighter weight.

## OPS-18: compose.yml shares single PostgreSQL instance across app and LangFuse
**Severity:** Info
**Location:** `compose.yml:18`, `compose.yml:61`
**Description:** LangFuse uses `postgresql://user:password@summit-cap-db:5432/langfuse` and the app uses `postgresql+asyncpg://user:password@summit-cap-db:5432/summit-cap`. Both share the same PostgreSQL container with the same superuser credentials (`user/password`). While the databases are separate (`langfuse` vs `summit-cap`), sharing the same PG instance means LangFuse could theoretically access the application database, and the shared user has superuser privileges across both databases.
**Recommendation:** For local dev this is acceptable, but document this as a known limitation. For production/OpenShift, the Helm chart should use separate database instances or at minimum separate credentials with restricted privileges.

## OPS-19: Root `package.json` scripts hardcode `podman-compose` while Makefile auto-detects
**Severity:** Info
**Location:** `package.json:20-23`
**Description:** The root `package.json` hardcodes `podman-compose` in its compose scripts:
```json
"compose:up": "podman-compose up -d",
"compose:down": "podman-compose down",
"compose:logs": "podman-compose logs -f",
"containers:build": "podman-compose build"
```
But the Makefile auto-detects the compose tool and may use `docker compose`. This creates inconsistent behavior: `make run` might use docker-compose while `pnpm compose:up` always uses podman-compose.
**Recommendation:** Either standardize on one entrypoint (Makefile preferred since it auto-detects), or update the package.json scripts to delegate to the Makefile targets.

## OPS-20: API container health check differs between compose.yml and Containerfile
**Severity:** Info
**Location:** `compose.yml:108`, `packages/api/Containerfile:59-60`
**Description:** The health check definitions differ:
- **compose.yml**: interval=10s, timeout=5s, retries=5, start_period=30s
- **Containerfile HEALTHCHECK**: interval=30s, timeout=10s, start_period=40s, retries=3

The compose.yml health check overrides the Containerfile's HEALTHCHECK directive, so the Containerfile values are only used when running the container outside of compose (e.g., `podman run` directly). The discrepancy is confusing.
**Recommendation:** Remove the HEALTHCHECK from the Containerfile (let the orchestrator define it), or align the values.

## OPS-21: Helm chart appVersion is "latest" instead of a real version
**Severity:** Info
**Location:** `deploy/helm/summit-cap/Chart.yaml:7`
**Description:** `appVersion: "latest"` provides no useful information about which application version the chart deploys. Combined with `global.imagePullPolicy: Always` and `imageTag: latest` in values.yaml, this means deployments are non-reproducible.
**Recommendation:** Set `appVersion` to match the actual application version (from `package.json` or a git tag). In CI, override `imageTag` with the git SHA or semver tag.

## OPS-22: Nginx config in UI Containerfile is embedded as inline string
**Severity:** Info
**Location:** `packages/ui/Containerfile:40-56`
**Description:** The nginx configuration is embedded as a multi-line `echo` string inside a `RUN` command. This is fragile -- hard to read, hard to modify, and difficult to lint/validate. Adding new location blocks (e.g., for API proxying, security headers, or gzip) will make this increasingly unwieldy.
**Recommendation:** Create a `config/nginx/default.conf` file in the repo and COPY it into the image:
```dockerfile
COPY config/nginx/default.conf /etc/nginx/conf.d/default.conf
```

## OPS-23: No resource limits on compose services
**Severity:** Info
**Location:** `compose.yml` (all services)
**Description:** No compose service defines resource limits (`deploy.resources.limits`). On a developer workstation, the full profile starts 9+ containers (postgres, api, ui, keycloak, llamastack, redis, clickhouse, minio, langfuse-web, langfuse-worker). ClickHouse and LangFuse in particular can consume significant memory.
**Recommendation:** Add `deploy.resources.limits` to memory-hungry services (ClickHouse, LangFuse, PostgreSQL) so they don't starve the developer's machine.

## OPS-24: `make stop` only tears down with `--profile full`
**Severity:** Info
**Location:** `Makefile:114`
**Description:** `make stop` runs `$(COMPOSE) --profile full down`. If the user started with `make run-minimal` (no profiles), the `--profile full` flag means compose may not match the running services correctly. In podman-compose specifically, profile filtering during `down` can behave differently than in Docker Compose v2.
**Recommendation:** Use `$(COMPOSE) down --remove-orphans` without a profile flag to ensure all containers are stopped regardless of which profile was used to start them. Or run `$(COMPOSE) --profile full --profile auth --profile ai --profile observability down` to cover all profiles.
