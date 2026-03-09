#!/usr/bin/env bash
# This project was developed with assistance from AI tools.
#
# Smoke test: start the minimal compose stack, wait for health checks,
# hit a few endpoints, then tear down. Run before demos to catch
# container misconfigs.
#
# Usage:
#   make smoke
#   scripts/smoke-test.sh                   # uses auto-detected compose
#   COMPOSE="podman-compose" scripts/smoke-test.sh

set -euo pipefail

COMPOSE="${COMPOSE:-$(docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "podman-compose")}"
API_URL="http://localhost:8000"
UI_URL="http://localhost:3000"
TIMEOUT=120
PASSED=0
FAILED=0

# -- Helpers -----------------------------------------------------------------

log()  { printf "\033[1;34m[smoke]\033[0m %s\n" "$*"; }
pass() { printf "\033[1;32m  PASS\033[0m %s\n" "$*"; PASSED=$((PASSED + 1)); }
fail() { printf "\033[1;31m  FAIL\033[0m %s\n" "$*"; FAILED=$((FAILED + 1)); }

cleanup() {
    log "Tearing down containers..."
    $COMPOSE down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_for_healthy() {
    local service="$1"
    local elapsed=0

    log "Waiting for $service to become healthy (timeout: ${TIMEOUT}s)..."
    while [ $elapsed -lt $TIMEOUT ]; do
        local health
        health=$($COMPOSE ps --format json 2>/dev/null \
            | python3 -c "
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    svc = json.loads(line)
    if svc.get('Service') == '$service' or svc.get('Name','').startswith('$service'):
        print(svc.get('Health','unknown'))
        break
" 2>/dev/null || echo "unknown")

        if [ "$health" = "healthy" ]; then
            return 0
        fi
        sleep 3
        elapsed=$((elapsed + 3))
    done
    return 1
}

check_endpoint() {
    local label="$1"
    local url="$2"
    local expect_status="${3:-200}"

    local status
    status=$(curl -sf -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    if [ "$status" = "$expect_status" ]; then
        pass "$label -> $status"
    else
        fail "$label -> $status (expected $expect_status)"
    fi
}

check_json_field() {
    local label="$1"
    local url="$2"
    local jq_expr="$3"

    local result
    result=$(curl -sf "$url" 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
# simple dotted path eval
val = data
for key in '$jq_expr'.split('.'):
    if key == '':
        continue
    if isinstance(val, list):
        val = val[int(key)]
    else:
        val = val[key]
print(val)
" 2>/dev/null || echo "ERROR")

    if [ "$result" != "ERROR" ] && [ -n "$result" ]; then
        pass "$label -> $result"
    else
        fail "$label (could not extract $jq_expr)"
    fi
}

# -- Main --------------------------------------------------------------------

log "Starting minimal compose stack..."
$COMPOSE up -d

if wait_for_healthy "mortgage-ai-db"; then
    pass "mortgage-ai-db healthy"
else
    fail "mortgage-ai-db did not become healthy within ${TIMEOUT}s"
fi

if wait_for_healthy "mortgage-ai-api"; then
    pass "mortgage-ai-api healthy"
else
    fail "mortgage-ai-api did not become healthy within ${TIMEOUT}s"
fi

if wait_for_healthy "mortgage-ai-ui"; then
    pass "mortgage-ai-ui healthy"
else
    fail "mortgage-ai-ui did not become healthy within ${TIMEOUT}s"
fi

log "Running endpoint checks..."

# API health
check_endpoint "GET /health/" "$API_URL/health/"
check_json_field "API health status" "$API_URL/health/" "0.status"

# API root
check_endpoint "GET /" "$API_URL/"

# Public endpoints (no auth)
check_endpoint "GET /api/public/products" "$API_URL/api/public/products"
check_endpoint "POST /api/public/calculate-affordability" \
    "$API_URL/api/public/calculate-affordability" "422"
    # 422 expected: no body sent, validation error confirms the route is live

# Applications (AUTH_DISABLED=true in compose, so dev-user admin)
check_endpoint "GET /api/applications/" "$API_URL/api/applications/"

# UI serves HTML
check_endpoint "GET UI root" "$UI_URL/"

# -- Summary -----------------------------------------------------------------

echo ""
log "Results: $PASSED passed, $FAILED failed"

if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
