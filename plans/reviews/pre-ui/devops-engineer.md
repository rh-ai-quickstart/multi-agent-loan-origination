# DevOps Engineer Review -- Pre-UI

Scope: `compose.yml`, `deploy/`, `packages/*/Containerfile`, `scripts/`, `Makefile`

Items already in `known-deferred.md` (W-31 through W-36, S-32, S-33, D17) are skipped.

---

## Critical

### DO-01: API Containerfile installs dev dependencies in production image

**File:** `packages/api/Containerfile:21`

```dockerfile
RUN uv pip install --system -e .[dev] || uv pip install --system -e .
```

The builder stage attempts to install the `[dev]` extras first and only falls back to the runtime extras if that fails. In practice, `uv pip install -e .[dev]` will succeed, so test frameworks, linters, and other dev tooling (pytest, ruff, etc.) are installed into every production image. The fallback pattern also hides the error rather than failing the build explicitly, making future dependency changes harder to reason about.

**Fix:** Remove the `|| uv pip install --system -e .` fallback. Use a distinct extras group for production-only dependencies (`[runtime]` or just the base install), or build with the optional extras listed explicitly:
```dockerfile
RUN uv pip install --system -e ".[dev]"  # builder stage only
```
And in the runtime stage, reinstall from the lock file without dev extras:
```dockerfile
RUN uv pip install --system -e .
```
Or copy the already-installed site-packages from builder (as currently done) and strip dev tooling, or restructure to use a `uv sync --no-dev` equivalent.

---

### DO-02: Helm database init ConfigMap embeds hardcoded role passwords

**File:** `deploy/helm/summit-cap/templates/database-configmap.yaml:22-24`

```sql
CREATE ROLE lending_app WITH LOGIN PASSWORD 'lending_pass';
CREATE ROLE compliance_app WITH LOGIN PASSWORD 'compliance_pass';
```

The HMDA isolation roles are created with static passwords baked into the ConfigMap template, not sourced from the Helm secret. The `COMPLIANCE_DATABASE_URL` secret contains `compliance_pass`, but the role creation that sets that password is hardcoded in plain text in the ConfigMap (which is not encrypted at rest in Kubernetes by default). If an operator rotates the secret value, the actual database role password remains `compliance_pass`.

**Fix:** Either (a) accept these as known demo credentials with a comment, or (b) pass the passwords as environment variables into the init script via secretKeyRef and reference them in the psql block using `ALTER ROLE ... PASSWORD '$ENV_VAR'` -- though this requires careful quoting in shell heredoc. At minimum, document that these passwords must match `COMPLIANCE_DATABASE_URL` in a comment.

---

## Warning

### DO-03: UI Containerfile uses `pnpm@latest` with corepack -- non-deterministic build

**File:** `packages/ui/Containerfile:19`

```dockerfile
RUN corepack enable && corepack prepare pnpm@latest --activate || npm install -g pnpm
```

`pnpm@latest` resolves at build time to whatever version is current. Combined with `--no-frozen-lockfile` on line 23, this means the pnpm version and dependency resolution are both non-deterministic across builds. The fallback to `npm install` or `yarn install` further undermines reproducibility -- a future build could silently use a different package manager.

**Fix:** Pin the pnpm version to match what developers use locally (check `package.json` `engines.pnpm` or `.npmrc`). Remove the fallback chain:
```dockerfile
RUN corepack enable && corepack prepare pnpm@9.x.x --activate
RUN pnpm install --frozen-lockfile
```
If a lockfile is missing in context, that's a build-time signal that something went wrong -- fail fast rather than silently regenerating.

---

### DO-04: API Containerfile copies entire `/usr/local/bin` from builder stage

**File:** `packages/api/Containerfile:37`

```dockerfile
COPY --from=builder /usr/local/bin /usr/local/bin
```

Copying the entire `/usr/local/bin` from the builder brings in every binary that was in that directory in the `python:3.11-slim` builder image plus any installed by `uv pip install`. This can include unexpected binaries from dev packages (e.g., `py.test`, `ruff`, `black`) that have no place in the runtime image. It also re-introduces `uv` by this path (installed in builder layer 6) unnecessarily.

**Fix:** Copy only the binaries actually needed at runtime:
```dockerfile
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /usr/local/bin/alembic /usr/local/bin/alembic
```
Or use a more surgical approach to avoid importing dev tooling binaries.

---

### DO-05: `summit-cap-api` in compose.yml has no dependency on Keycloak when auth profile is active

**File:** `compose.yml:83-87`

```yaml
depends_on:
  summit-cap-db:
    condition: service_healthy
  minio:
    condition: service_healthy
```

When started with `--profile auth` or `--profile full`, the API starts before Keycloak is healthy. On first boot, Keycloak can take 60-90 seconds. The API may start, attempt to fetch JWKS, fail, and then silently fall back to unauthenticated behavior or log repeated errors until Keycloak is ready.

**Fix:** Add a conditional dependency using a profile-aware pattern, or document in comments that the API is expected to log JWKS fetch errors at startup when Keycloak is starting. A more robust fix is to add retry logic to JWKS fetching (which is an app concern), or add the dependency:
```yaml
depends_on:
  summit-cap-db:
    condition: service_healthy
  minio:
    condition: service_healthy
  # Add when using auth profile:
  # keycloak:
  #   condition: service_healthy
```
Note: compose profiles make this dependency tricky -- the service must exist in the same profile or `always` for the `depends_on` condition to be evaluated. This likely needs a comment explaining the startup ordering concern.

---

### DO-06: `langfuse-worker` has no liveness or readiness probes in Helm chart

**File:** `deploy/helm/summit-cap/templates/langfuse.yaml:197-347`

The `langfuse-web` deployment has liveness/readiness probes (`/api/public/health`) but `langfuse-worker` has neither. Kubernetes cannot detect if the worker process has stalled or crashed; it will only restart it if the container exits. A hung worker that is not processing traces will appear healthy.

**Fix:** Add probes to `langfuse-worker`. LangFuse worker typically exposes a health endpoint or can be checked with a process existence probe:
```yaml
livenessProbe:
  exec:
    command: ["node", "-e", "process.exit(0)"]  # or appropriate health check
  initialDelaySeconds: 30
  periodSeconds: 30
```
Check LangFuse worker documentation for the appropriate health endpoint.

---

### DO-07: `langfuse.yaml` embeds database credentials in plain-text env value (not from secret)

**File:** `deploy/helm/summit-cap/templates/langfuse.yaml:55, 223`

```yaml
- name: DATABASE_URL
  value: "postgresql://{{ .Values.secrets.POSTGRES_USER }}:{{ .Values.secrets.POSTGRES_PASSWORD }}@{{ $dbName }}:5432/langfuse"
```

The Langfuse `DATABASE_URL` is constructed as a plain `value:` by interpolating secret values directly into the template string. This means the credentials appear in the rendered manifest in plaintext, visible via `kubectl get deploy langfuse-web -o yaml`. The same pattern is used for `CLICKHOUSE_MIGRATION_URL`.

**Fix:** Either construct the URL in a Kubernetes Secret and reference it via `secretKeyRef`, or accept this as an MVP limitation (the values are already in the Secret object, this is a secondary exposure). A clean fix adds `LANGFUSE_DATABASE_URL` to the secret:
```yaml
LANGFUSE_DATABASE_URL: {{ printf "postgresql://%s:%s@%s:5432/langfuse" .Values.secrets.POSTGRES_USER .Values.secrets.POSTGRES_PASSWORD .Values.database.name | b64enc | quote }}
```

---

### DO-08: `minio` in Helm chart has no security context -- runs as root

**File:** `deploy/helm/summit-cap/templates/minio.yaml:20-23`

The MinIO deployment has no `securityContext` set at either pod or container level. The global `securityContext` in values.yaml (`runAsNonRoot: true`, `allowPrivilegeEscalation: false`) is applied to API and UI deployments via `{{- toYaml .Values.securityContext | nindent 12 }}` but is absent from the MinIO deployment template. MinIO will run as root by default.

**Fix:** Apply a container security context to MinIO (it supports non-root since RELEASE.2022-05-08):
```yaml
securityContext:
  runAsUser: 1000
  runAsGroup: 1000
  runAsNonRoot: true
  allowPrivilegeEscalation: false
```
Or add `{{- toYaml .Values.securityContext | nindent 12 }}` to the container spec and verify MinIO starts correctly under the global security context.

---

### DO-09: Keycloak deployed with `start-dev` in Helm/production

**File:** `deploy/helm/summit-cap/templates/keycloak.yaml:33-35`

```yaml
args:
  - start-dev
  - --import-realm
```

`start-dev` is Keycloak's development mode: it uses an embedded H2 database (ignoring any external DB configuration), disables caching, and enables verbose development logging. This is appropriate for local compose but not for the Helm chart which is intended for OpenShift deployment. A Helm-deployed Keycloak started with `start-dev` will lose all realm/user data on pod restart since H2 is non-persistent.

**Fix:** For Helm/OpenShift deployment, use `start --optimized` or `start` with appropriate database configuration (or accept that Keycloak is demo-only and document this limitation prominently). At minimum, add a comment:
```yaml
# NOTE: start-dev uses embedded H2 storage. Keycloak data is not persisted.
# For production use, replace with 'start' and configure KC_DB_* env vars.
```

---

### DO-10: `deploy.sh` passes empty string values for unset env vars to `helm --set`

**File:** `scripts/deploy.sh:55-91`

```bash
--set secrets.POSTGRES_DB="${POSTGRES_DB:-}" \
```

When `POSTGRES_DB` is not set in the environment, this passes `--set secrets.POSTGRES_DB=` to helm, setting the secret value to an empty string. Helm will render this as an empty string in the Secret, and the API will start with `DATABASE_URL=""` or similar. The fallback values in `values.yaml` are never used when a `--set` argument explicitly provides an empty string, because `--set` overrides values.yaml entirely.

This means a `make deploy` without a populated `.env` will create a broken deployment with empty critical secrets rather than using the sensible defaults from `values.yaml`.

**Fix:** Skip the `--set` argument when the env var is empty, so `values.yaml` defaults are honored:
```bash
${POSTGRES_DB:+--set secrets.POSTGRES_DB="$POSTGRES_DB"} \
```
Or document that `.env` is required before running `make deploy` and add a guard:
```bash
if [ -z "$POSTGRES_DB" ] && [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL must be set. Copy .env.example to .env and configure."
    exit 1
fi
```

---

### DO-11: `smoke-test.sh` compose detection prefers docker over podman

**File:** `scripts/smoke-test.sh:15`

```bash
COMPOSE="${COMPOSE:-$(docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "podman-compose")}"
```

The smoke test script detects `docker compose` first, falling back to `podman-compose`. This is the opposite preference from the Makefile, which detects `podman-compose` first. On a machine with both installed (e.g., a developer who also has Docker Desktop), the smoke test could run against a different compose runtime than `make run`, leading to inconsistent behavior or port conflicts.

**Fix:** Align the detection order with the Makefile:
```bash
COMPOSE="${COMPOSE:-$(command -v podman-compose >/dev/null 2>&1 && echo "podman-compose" || echo "docker compose")}"
```

---

### DO-12: `redis` in Helm uses unqualified image name (no registry prefix)

**File:** `deploy/helm/summit-cap/templates/redis.yaml:26`

```yaml
image: redis:7-alpine
```

This is a hardcoded image reference bypassing the global `imageRegistry` configuration in values.yaml. All other service images pull from `docker.io` explicitly or use the `summit-cap.image` helper with `global.imageRegistry`. In air-gapped or registry-mirror environments (common on OpenShift AI), this will fail to pull because the default DockerHub pull-through may be restricted. The `clickhouse` template has the same issue (`clickhouse/clickhouse-server:24` on line 29).

**Fix:** Add registry prefix to match compose.yml and document that these are upstream images:
```yaml
image: "docker.io/redis:7-alpine"
```
Or better, add values.yaml entries for these images like other services so operators can override the registry.

---

## Suggestion

### DO-13: API Containerfile healthcheck uses Python subprocess -- prefer curl/wget

**File:** `packages/api/Containerfile:62-63`

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/')" || exit 1
```

The Containerfile health check spawns a full Python interpreter to make an HTTP request. This is heavier than necessary (adds ~100ms overhead per check, forks a process, imports urllib). The `python:3.11-slim` image includes `wget` or can be made to include `curl`. The compose healthcheck already uses this pattern, making the Containerfile inconsistent.

**Fix:** Install `curl` in the runtime stage and use it:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -sf http://localhost:8000/health/ || exit 1
```

---

### DO-14: No `.containerignore` / `.dockerignore` for tests directory

**File:** `.dockerignore`

The `.dockerignore` excludes `plans/`, `.claude/`, `.github/`, and `deploy/` but does not exclude the `scripts/` directory or test files (`tests/`, `*.test.ts`). The API Containerfile copies `packages/api/src/` explicitly so this does not cause the API image to bloat, but the UI Containerfile copies all of `packages/` including test files and config packages, which are then available in the builder layer unnecessarily.

**Fix:** Add to `.dockerignore`:
```
scripts/
packages/*/tests/
packages/*/*.test.ts
packages/*/*.test.tsx
packages/*/*.spec.ts
packages/*/*.stories.tsx
packages/*/.storybook/
```

---

### DO-15: Helm chart has no `failureThreshold` or `timeoutSeconds` on API/UI readiness probes

**File:** `deploy/helm/summit-cap/templates/api-deployment.yaml:228-233`

```yaml
readinessProbe:
  httpGet:
    path: {{ .Values.api.healthCheck.path }}
    port: http
  initialDelaySeconds: {{ .Values.api.healthCheck.initialDelaySeconds }}
  periodSeconds: {{ .Values.api.healthCheck.periodSeconds }}
```

The API and UI probes omit `failureThreshold` and `timeoutSeconds`. Kubernetes defaults are `failureThreshold: 3` and `timeoutSeconds: 1`. With `periodSeconds: 10`, the API pod will be marked not-ready after 30 seconds of failed checks, and requests will time out after 1 second. The API, which does LLM inference and DB queries, could take longer than 1 second to respond to health checks during load. These values are also not configurable via values.yaml.

**Fix:** Add explicit values and expose them in `values.yaml`:
```yaml
healthCheck:
  enabled: true
  path: /health/
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 6
```

---

### DO-16: `make helm-template` only passes a subset of secrets; rendered output will have empty values

**File:** `Makefile:251-263`

The `helm-template` target passes `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `DEBUG`, `ALLOWED_HOSTS`, `VITE_API_BASE_URL`, and `VITE_ENVIRONMENT` but omits the remaining ~25 secrets (LLM, S3, Keycloak, LangFuse, etc.). Running `make helm-template` produces a template with empty strings for most secrets. This makes the target useful only for partial rendering inspection, not for validating the full manifest.

**Fix:** Either (a) document the limitation in the `make help` output, or (b) have `helm-template` also source `.env` the same way `deploy.sh` does and pass all secrets. The `deploy.sh` script already has the full set; `helm-template` could delegate to it with `--dry-run=client`:
```makefile
helm-template: helm-dep-update
	@scripts/deploy.sh --dry-run=client
```
