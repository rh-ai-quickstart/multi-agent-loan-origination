# DevOps Review -- Pre-Phase 5

**Reviewer:** devops-engineer
**Date:** 2026-02-27
**Scope:** Infrastructure, deployment, configuration, build, dependency management

---

## Findings

### [DO-01] Severity: Critical
**File(s):** `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/templates/api-deployment.yaml`, `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/values.yaml`
**Finding:** The Helm API deployment does not mount the `config/` directory, but the API requires it at runtime. Both `packages/api/src/inference/config.py` (line 25, resolves `config/models.yaml`) and `packages/api/src/agents/registry.py` (line 20, resolves `config/agents/`) use `Path(__file__).resolve().parents[4] / "config"` to locate YAML configuration files. In the compose stack, this is handled by the volume mount `./config:/app/config:ro` (compose.yml line 106), but the Helm deployment has no ConfigMap, volume, or volume mount for these files. The API will crash on startup when deployed to OpenShift because model routing config and agent configs will not be found.
**Recommendation:** Create a ConfigMap (or set of ConfigMaps) containing the contents of `config/models.yaml` and `config/agents/*.yaml`, mount it into the API pod at the expected path, or bake the config directory into the API container image. The Containerfile already COPYs source from `packages/api/` but does not copy `config/`. Either add `COPY config/ /app/config/` to the Containerfile or mount via ConfigMap in the Helm chart.

### [DO-02] Severity: Critical
**File(s):** `/home/jary/redhat/git/mortgage-ai/scripts/deploy.sh`
**Finding:** The deploy script only passes a subset of secrets to Helm. It passes `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `DEBUG`, `ALLOWED_HOSTS`, `VITE_API_BASE_URL`, and `VITE_ENVIRONMENT`. It does NOT pass `COMPLIANCE_DATABASE_URL`, `AUTH_DISABLED`, `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_FAST`, `LLM_MODEL_CAPABLE`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, or `LANGFUSE_HOST`. These are all defined in `values.yaml` secrets and referenced by the API deployment template, but the deploy script never overrides them from environment variables. This means production deployments will use the insecure defaults from `values.yaml` (e.g., `S3_SECRET_KEY: miniosecret`, `POSTGRES_PASSWORD: changeme`).
**Recommendation:** Add `--set secrets.<KEY>="${VAR:-}"` entries to `scripts/deploy.sh` for every secret defined in `values.yaml`. Alternatively, use a Helm values file (`-f production-secrets.yaml`) that operators populate rather than passing secrets via `--set` on the command line (which exposes them in process listings).

### [DO-03] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/Containerfile`
**Finding:** The builder stage installs dev dependencies into the production image. Line 21 runs `uv pip install --system -e .[dev] || uv pip install --system -e .` which means the first attempt always installs `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`, `testcontainers`, and `psycopg2-binary` into the runtime image. The `|| ... -e .` fallback is only reached if the dev install fails, which is unlikely. This bloats the production image with test tooling and adds unnecessary attack surface.
**Recommendation:** Change to `uv pip install --system -e .` (without `[dev]`). If dev dependencies are needed for a separate test image, create a dedicated test stage or a separate Containerfile.

### [DO-04] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/Containerfile`
**Finding:** The base image `python:3.11-slim` is not pinned to a specific patch version or digest. Line 3 uses `FROM python:3.11-slim AS builder` and line 24 uses `FROM python:3.11-slim AS runtime`. While `3.11` is better than `latest`, the image can change between builds when new 3.11.x releases are published, making builds non-deterministic.
**Recommendation:** Pin to a specific version such as `python:3.11.11-slim` or, better, pin to a SHA256 digest for fully reproducible builds. Update the pin periodically as part of a dependency update process.

### [DO-05] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/ui/Containerfile`
**Finding:** Multiple unpinned images. Line 1 uses `FROM node:20-alpine` (no patch version) and line 29 uses `FROM docker.io/nginx:alpine` (no major version at all). The nginx image could jump from 1.x to 2.x without warning.
**Recommendation:** Pin both images to specific versions, e.g. `node:20.11.1-alpine` and `nginx:1.27-alpine`.

### [DO-06] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/ui/Containerfile`
**Finding:** The builder stage copies the entire `packages/` directory (line 13: `COPY packages/ ./packages/`) including the Python API and DB packages, their virtual environments, and all other workspace packages. This significantly inflates the build context sent to the daemon and the builder layer size, even though only the UI package is needed.
**Recommendation:** Copy only what the UI build requires: `COPY packages/ui/ ./packages/ui/` and `COPY packages/configs/ ./packages/configs/`. If other workspace config packages are needed, copy them explicitly rather than using the broad `packages/` glob.

### [DO-07] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/ui/Containerfile`
**Finding:** The pnpm install step uses `--no-frozen-lockfile` (line 23) and includes fallbacks to `npm install` and `yarn install`. This means builds are not deterministic -- different runs may resolve different dependency versions. The fallback to entirely different package managers could produce a fundamentally different `node_modules` tree.
**Recommendation:** Remove the npm/yarn fallbacks. Use `pnpm install --frozen-lockfile` and ensure the `pnpm-lock.yaml` is copied into the build context. The `.dockerignore` does not exclude `pnpm-lock.yaml` so it should already be available if copied at the right stage. Add `COPY pnpm-lock.yaml ./` before the install step.

### [DO-08] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/compose.yml`
**Finding:** The `minio` service (line 212) uses `docker.io/minio/minio:latest` and the `llamastack` service (line 157) uses `docker.io/llamastack/distribution-starter:latest`. Both use the `latest` tag, which violates the principle of deterministic builds and can break the dev stack without warning when upstream publishes a breaking change.
**Recommendation:** Pin both to specific version tags. For MinIO, use a date-based release tag (e.g., `RELEASE.2024-11-07T00-52-20Z`). For LlamaStack, pin to the version being developed against.

### [DO-09] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/values.yaml`
**Finding:** The default `values.yaml` contains actual secret values in plaintext: `POSTGRES_PASSWORD: "changeme"`, `S3_ACCESS_KEY: "minio"`, `S3_SECRET_KEY: "miniosecret"`, `LLM_API_KEY: "not-needed"`, `COMPLIANCE_DATABASE_URL` with embedded password. While these are marked as "should be overridden," having any password-like defaults in version-controlled Helm values means that forgetting to override them results in a deployment with known credentials.
**Recommendation:** Set secret defaults to empty strings (`""`) and add a Helm `required` check or a `_helpers.tpl` validation that fails `helm template` / `helm install` if critical secrets are not provided. At minimum, `POSTGRES_PASSWORD`, `S3_SECRET_KEY`, `DATABASE_URL`, and `COMPLIANCE_DATABASE_URL` should have no usable default.

### [DO-10] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/templates/api-deployment.yaml`
**Finding:** The liveness and readiness probes use the same path (`/health/`), same `initialDelaySeconds` (30), and same `periodSeconds` (10). This means a slow database query in the health check can cause Kubernetes to kill the pod (liveness failure) when the pod is actually running but temporarily unable to connect to a dependency. Liveness should check "is the process alive" (lightweight), while readiness should check "can it serve traffic" (dependency-aware).
**Recommendation:** Differentiate the probes. Use a lightweight endpoint (e.g., `/health/liveness` that returns 200 without checking dependencies) for the liveness probe. Keep `/health/` (which checks the database) for the readiness probe only. Alternatively, increase the `failureThreshold` on the liveness probe and give it a higher `periodSeconds` so transient dependency issues do not trigger a pod restart.

### [DO-11] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/src/core/config.py`, `/home/jary/redhat/git/mortgage-ai/compose.yml`, `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/values.yaml`
**Finding:** Multiple config settings defined in `config.py` are absent from both the compose environment and the Helm values/secrets. Missing from compose: `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_REALM`, `SQLADMIN_USER`, `SQLADMIN_PASSWORD`, `S3_REGION`, `UPLOAD_MAX_SIZE_MB`, `JWKS_CACHE_TTL`, `SAFETY_ENDPOINT`, `SAFETY_API_KEY`. Missing from Helm values: all of those plus `SAFETY_MODEL`. These settings fall back to code defaults, but the lack of explicit configuration in deployment manifests means operators have no visibility into what these values are or how to override them.
**Recommendation:** Add all Settings fields to the compose environment block (with appropriate `${VAR:-default}` syntax) and to the Helm values.yaml secrets section. Even if the defaults are acceptable, making them explicit prevents confusion and makes the deployment self-documenting.

### [DO-12] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/pyproject.toml`
**Finding:** The `python-dotenv` package is imported at runtime by `packages/api/src/inference/config.py` (`from dotenv import load_dotenv`) but is not listed as a dependency in `pyproject.toml`. It is currently pulled in as a transitive dependency (visible in `uv.lock`), but transitive dependencies can be removed at any time when their parent package is updated. This makes the build fragile.
**Recommendation:** Add `python-dotenv>=1.0.0` to the `dependencies` list in `pyproject.toml`.

### [DO-13] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/pyproject.toml`
**Finding:** Production dependencies use broad minimum version pins (e.g., `fastapi>=0.104.0`, `sqlalchemy>=2.0.0`, `langchain>=0.3.0`). While the `uv.lock` file provides reproducibility for local development, the Containerfile installs from `pyproject.toml` directly (`uv pip install --system -e .`), bypassing the lock file. This means container builds can resolve different dependency versions than local development.
**Recommendation:** Either copy `uv.lock` into the container build context and use `uv sync` instead of `uv pip install`, or use `uv pip install --system --require-hashes` with a requirements file generated from the lock. This ensures container builds use the same pinned versions as local development.

### [DO-14] Severity: Warning
**File(s):** `/home/jary/redhat/git/mortgage-ai/compose.yml`
**Finding:** The compose API service uses `host.docker.internal` (line 93) as the default LLM endpoint. This only works with Docker Desktop or specific Docker/Podman configurations that set up this DNS alias. On native Linux with Podman, `host.docker.internal` may not resolve, causing the LLM client to fail silently or with a confusing DNS error. The LlamaStack service has the same issue (line 166).
**Recommendation:** Document this requirement in the README or compose file comments. For Podman on Linux, the equivalent is `host.containers.internal`. Consider adding a compose `extra_hosts` entry or using a network-mode configuration that makes the host reachable. At minimum, add a comment explaining what to set `LLM_BASE_URL` to when using different container runtimes.

### [DO-15] Severity: Warning
**File(s):** (project root)
**Finding:** No `.env.example` file exists. The project has 20+ environment variables across the API, with non-obvious names and relationships (e.g., `COMPLIANCE_DATABASE_URL` vs `DATABASE_URL`, `SAFETY_MODEL` vs `SAFETY_ENDPOINT`). New developers or operators have no reference for which variables exist, which are required, and what valid values look like.
**Recommendation:** Create a `.env.example` file in the project root listing all environment variables with comments explaining their purpose and example values. Use placeholder values (e.g., `POSTGRES_PASSWORD=changeme`) rather than real credentials. This is referenced as expected in `.claude/rules/architecture.md` but does not exist.

### [DO-16] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/Containerfile`
**Finding:** The runtime stage copies `uv` into the production image (line 27: `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv`) but never uses it. All dependencies are already installed in `/usr/local/lib/python3.11/site-packages` from the builder stage, and the CMD runs `uvicorn` directly.
**Recommendation:** Remove the `uv` COPY from the runtime stage to reduce image size and attack surface.

### [DO-16b] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/api/Containerfile`
**Finding:** The `COPY --from=ghcr.io/astral-sh/uv:latest` instruction in both stages is not pinned. This fetches whatever the current `latest` uv release is, which can change between builds.
**Recommendation:** Pin the uv image to a specific version tag (e.g., `ghcr.io/astral-sh/uv:0.5.14`).

### [DO-17] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/templates/api-deployment.yaml`
**Finding:** The API deployment does not include an `initContainer` to wait for the database to be ready, unlike the migration job which has one. If the API pod starts before the database is accepting connections, the SQLAlchemy connection pool initialization or Alembic auto-migration may fail on startup.
**Recommendation:** Either add a `wait-for-database` initContainer similar to the migration job, or ensure the application code handles database connection retries gracefully at startup (which it may already do via SQLAlchemy's pool retry mechanisms, but this should be verified).

### [DO-18] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/values.yaml`, `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/templates/secret.yaml`
**Finding:** All configuration values (including non-sensitive ones like `DEBUG`, `ALLOWED_HOSTS`, `VITE_ENVIRONMENT`, `LLM_BASE_URL`) are stored in a Kubernetes Secret. While this is not harmful, it conflates sensitive credentials with plain configuration, making secret rotation harder and obscuring which values are actually confidential.
**Recommendation:** Split into a ConfigMap for non-sensitive configuration (DEBUG, ALLOWED_HOSTS, VITE_API_BASE_URL, VITE_ENVIRONMENT, LLM_BASE_URL, LLM_MODEL_FAST, LLM_MODEL_CAPABLE, AUTH_DISABLED, KEYCLOAK_URL, KEYCLOAK_REALM, S3_ENDPOINT, S3_BUCKET, LANGFUSE_HOST) and a Secret for actual credentials (POSTGRES_PASSWORD, DATABASE_URL, COMPLIANCE_DATABASE_URL, S3_ACCESS_KEY, S3_SECRET_KEY, LLM_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY).

### [DO-19] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/Chart.yaml`
**Finding:** The Chart metadata contains placeholder URLs and email addresses: `home: https://github.com/example/summit-cap`, `sources: https://github.com/example/summit-cap`, `email: dev@example.com`. These should reference the actual repository.
**Recommendation:** Update to `https://github.com/rh-ai-quickstart/mortgage-ai` (matching the URLs in `pyproject.toml`) and use a real team email or remove the `maintainers` section.

### [DO-20] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/turbo.json`
**Finding:** The Turborepo `test` task has no `dependsOn` configuration. For the API package, `test` should depend on the DB package being built first (since the API imports from `summit-cap-db`). The current configuration may work because `uv run pytest` resolves the editable install at runtime, but it is not explicit about the dependency.
**Recommendation:** Add `"dependsOn": ["^build"]` to the `test` task in `turbo.json` to ensure upstream packages are built before downstream tests run, matching the pattern used by the `build` task.

### [DO-21] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/templates/database-deployment.yaml`
**Finding:** The database deployment uses the `pgvector/pgvector:pg16` image directly from Docker Hub without routing through the Helm `global.imageRegistry` / `global.imageRepository` settings. Line 25: `image: "{{ .Values.database.image.repository }}:{{ .Values.database.image.tag}}"`. In contrast, the API and UI deployments use the `summit-cap.image` helper. This means the database image cannot be pulled from a private/mirrored registry without manually overriding `database.image.repository` with a fully qualified path.
**Recommendation:** Either route the database image through the global registry settings (using a different helper or a conditional prefix) or document that `database.image.repository` must be set to the full path when using a private registry.

### [DO-22] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/packages/ui/package.json`
**Finding:** Multiple packages appear in both `dependencies` and `devDependencies`: `@tanstack/react-router`, `@tanstack/router-devtools`, `@tanstack/router-vite-plugin`, `@tanstack/react-query`, all `@radix-ui/*` packages, `class-variance-authority`, `clsx`, `lucide-react`, `tailwind-merge`, `tailwindcss-animate`, and `zod`. This duplication is confusing and could lead to version drift if only one location is updated.
**Recommendation:** Keep runtime dependencies only in `dependencies` and build/test tooling only in `devDependencies`. Since the UI is bundled by Vite, all of these could be in `devDependencies` (the bundle includes what it needs), but having them in both is unnecessary.

### [DO-23] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/values.yaml`
**Finding:** The migration job requests 1Gi memory and has a 2Gi limit. Running Alembic migrations against PostgreSQL is a lightweight operation that typically uses under 100Mi of memory. These resource allocations are 10x higher than needed and waste cluster resources.
**Recommendation:** Reduce migration resources to `requests.memory: 128Mi`, `limits.memory: 256Mi`, `requests.cpu: 100m`, `limits.cpu: 250m`.

### [DO-24] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/deploy/helm/summit-cap/templates/migration-job.yaml`
**Finding:** The migration job's `initContainer` uses `postgres:16-alpine` (line 28) which is a hardcoded image tag not managed by Helm values. This means it cannot be overridden for air-gapped environments and is not affected by the `global.imagePullPolicy` setting.
**Recommendation:** Either make this image configurable via values or document it as a known external dependency that must be available in the container registry.

### [DO-25] Severity: Suggestion
**File(s):** `/home/jary/redhat/git/mortgage-ai/compose.yml`
**Finding:** The `minio` service is not behind a compose profile -- it runs in every stack configuration including the minimal one (line 212 has no `profiles:` key). While MinIO is needed for document storage, operators running the minimal stack for quick API testing may not need or want the object storage service running.
**Recommendation:** This is acceptable if document upload is considered a core feature even in minimal mode. However, if it is not, consider putting MinIO behind a `storage` profile. The API service already has a hard `depends_on` for MinIO, so this would need to be conditional as well.
