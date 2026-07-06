#!/usr/bin/env bash
# This project was developed with assistance from AI tools.
#
# Test MCP Gateway tool discovery for registered MCP servers.
# Validates the Streamable HTTP protocol: initialize, notify, list tools,
# and optionally call a tool.
#
# Usage:
#   MCP_GATEWAY_URL=https://mcp-broker-mcp-system.apps.example.com scripts/test-mcp-gateway.sh
#   MCP_GATEWAY_URL=https://... CALL_TOOL=true scripts/test-mcp-gateway.sh

set -euo pipefail
#set -x

MCP_GATEWAY_URL="${MCP_GATEWAY_URL:-}"
TIMEOUT="${TIMEOUT:-15}"
CALL_TOOL="${CALL_TOOL:-false}"

PASSED=0
FAILED=0
SESSION_ID=""
HEADER_FILE=$(mktemp)
trap 'rm -f "$HEADER_FILE"' EXIT

if [ -z "$MCP_GATEWAY_URL" ]; then
    echo "Error: MCP_GATEWAY_URL is required"
    echo "Usage: MCP_GATEWAY_URL=https://mcp-broker-mcp-system.apps.example.com $0"
    exit 1
fi

log()  { printf "\033[1;34m[mcp-gateway]\033[0m %s\n" "$*"; }
pass() { printf "\033[1;32m  PASS\033[0m %s\n" "$*"; PASSED=$((PASSED + 1)); }
fail() { printf "\033[1;31m  FAIL\033[0m %s\n" "$*"; FAILED=$((FAILED + 1)); }

mcp_post() {
    local body="$1"
    local extra_args=("${@:2}")
    curl -sk --max-time "$TIMEOUT" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        "${extra_args[@]}" \
        "${MCP_GATEWAY_URL}/mcp" \
        -d "$body" 2>/dev/null
}

# -- Initialize ---------------------------------------------------------------

log "Testing MCP Gateway at ${MCP_GATEWAY_URL}"
echo ""

log "Step 1: Initialize..."
INIT_BODY=$(curl -sk --max-time "$TIMEOUT" -D "$HEADER_FILE" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    "${MCP_GATEWAY_URL}/mcp" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-mcp-gateway","version":"1.0"}}}' 2>/dev/null)

SESSION_ID=$(grep -i "^mcp-session-id:" "$HEADER_FILE" | tr -d '\r' | sed 's/^[^:]*: *//')

SERVER_NAME=$(echo "$INIT_BODY" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['serverInfo']['name'])" 2>/dev/null || echo "")
PROTOCOL=$(echo "$INIT_BODY" | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['protocolVersion'])" 2>/dev/null || echo "")

if [ -n "$SESSION_ID" ] && [ -n "$SERVER_NAME" ]; then
    pass "initialize - server: ${SERVER_NAME}, protocol: ${PROTOCOL}"
else
    fail "initialize - no session ID or server info"
    echo "  Response: $INIT_BODY"
    exit 1
fi
echo ""

# -- Initialized notification -------------------------------------------------

log "Step 2: Send initialized notification..."
NOTIFY_CODE=$(curl -sk --max-time "$TIMEOUT" -o /dev/null -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: ${SESSION_ID}" \
    "${MCP_GATEWAY_URL}/mcp" \
    -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' 2>/dev/null)

if [ "$NOTIFY_CODE" = "202" ] || [ "$NOTIFY_CODE" = "200" ]; then
    pass "initialized notification - HTTP ${NOTIFY_CODE}"
else
    fail "initialized notification - HTTP ${NOTIFY_CODE} (expected 202)"
fi
echo ""

# -- List tools ---------------------------------------------------------------

log "Step 3: List tools..."
TOOLS_RESPONSE=$(curl -sk --max-time "$TIMEOUT" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: ${SESSION_ID}" \
    "${MCP_GATEWAY_URL}/mcp" \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' 2>/dev/null)

TOOL_COUNT=$(echo "$TOOLS_RESPONSE" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['result']['tools']))" 2>/dev/null || echo "0")

if [ "$TOOL_COUNT" -gt 0 ]; then
    pass "tools/list - ${TOOL_COUNT} tools discovered"
    echo ""
    echo "$TOOLS_RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
tools = data['result']['tools']
for t in tools:
    name = t['name']
    desc = t.get('description', '').strip().split(chr(10))[0][:80]
    params = list(t.get('inputSchema', {}).get('properties', {}).keys())
    print(f'    {name}')
    print(f'      {desc}')
    param_str = ', '.join(params)
    print(f'      params: {param_str}')
" 2>/dev/null
else
    fail "tools/list - no tools found"
    echo "  Response: ${TOOLS_RESPONSE:0:200}"
fi
echo ""

# -- Call a tool (optional) ----------------------------------------------------

if [ "$CALL_TOOL" = "true" ] && [ "$TOOL_COUNT" -gt 0 ]; then
    log "Step 4: Call risk_calculate_dti tool..."
    CALL_RESPONSE=$(curl -sk --max-time "$TIMEOUT" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -H "Mcp-Session-Id: ${SESSION_ID}" \
        "${MCP_GATEWAY_URL}/mcp" \
        -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"risk_calculate_dti","arguments":{"monthly_income":8000,"monthly_debts":2400}}}' 2>/dev/null)

    CALL_RESULT=$(echo "$CALL_RESPONSE" | python3 -c "
import json, sys
raw = sys.stdin.read().strip()
# handle SSE format: extract JSON from 'data: {...}' lines
for line in raw.splitlines():
    if line.startswith('data: '):
        raw = line[6:]
        break
data = json.loads(raw)
content = data.get('result', {}).get('content', [{}])
if content:
    print(content[0].get('text', json.dumps(content)))
else:
    print(json.dumps(data.get('result', {})))
" 2>/dev/null || echo "")

    if [ -n "$CALL_RESULT" ] && [ "$CALL_RESULT" != "null" ]; then
        pass "tools/call risk_calculate_dti - ${CALL_RESULT}"
    else
        fail "tools/call risk_calculate_dti"
        echo "  Response: ${CALL_RESPONSE:0:300}"
    fi
    echo ""
fi

# -- Summary -------------------------------------------------------------------

log "Results: ${PASSED} passed, ${FAILED} failed"

if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
