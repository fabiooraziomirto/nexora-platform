#!/usr/bin/env bash
# nexora-device-emulator-e2e.sh
#
# End-to-end test: plugin dispatch + port management on a board.
#
# Exercises the full flow:
#   1. Board registers (via emulator.py) → session on nexora-edge
#   2. Plugin created in plugin-service → activated
#   3. function.install dispatched (Kafka → nexora-edge → emulator → WASM runtime)
#   4. function.invoke dispatched → result collected
#   5. Network port created + attached (network-service)
#   6. Webservice registered + enabled (webservice-service)
#
# Usage:
#   bash scripts/nexora-device-emulator-e2e.sh
#
# Prerequisites:
#   docker compose -f docker-compose.dev.yml --profile smoke --profile emulator up -d
#
# Environment overrides (optional):
#   DEVICE_URL, EXEC_URL, GW_URL, PLUGIN_URL, NET_URL, WS_URL, RUNTIME_URL
#   TOKEN, BOOTSTRAP_TOKEN, EMULATOR_POLL_SECONDS

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────

DEVICE_URL="${DEVICE_URL:-http://localhost:8000}"
PLUGIN_URL="${PLUGIN_URL:-http://localhost:8001}"
EXEC_URL="${EXEC_URL:-http://localhost:8002}"
NET_URL="${NET_URL:-http://localhost:8003}"
WS_URL="${WS_URL:-http://localhost:8005}"
GW_URL="${GW_URL:-http://localhost:8007}"
RUNTIME_URL="${RUNTIME_URL:-http://localhost:9000}"

TOKEN="${TOKEN:-dev-token}"
BOOTSTRAP_TOKEN="${BOOTSTRAP_TOKEN:-dev-bootstrap:dev-bootstrap-token}"
EMULATOR_POLL_SECONDS="${EMULATOR_POLL_SECONDS:-2}"

PASS=0
FAIL=0
EMULATOR_PID=""
EMULATOR_LOG=""

# ── Colours ───────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC}  $*"; PASS=$((PASS+1)); }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAIL=$((FAIL+1)); }
info() { echo -e "${YELLOW}[..]${NC}  $*"; }

# ── JSON helper (requires python3) ────────────────────────────────────────────

jq_get() {
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$1','') or '')" 2>/dev/null
}

# ── HTTP helpers ──────────────────────────────────────────────────────────────

_get() {
    curl -sf -H "Authorization: Bearer $TOKEN" "$@"
}

_post() {
    local url=$1; shift
    curl -sf -X POST -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" -d "$@" "$url"
}

_patch() {
    local url=$1; shift
    curl -sf -X PATCH -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" -d "$@" "$url"
}

# ── Poll until execution status matches ───────────────────────────────────────

poll_status() {
    local exec_id=$1
    local want=${2:-succeeded}
    local timeout=${3:-40}
    local t=0
    while [ $t -lt $timeout ]; do
        local s
        s=$(_get "$EXEC_URL/api/v2/executions/$exec_id" | jq_get status)
        if [ "$s" = "$want" ]; then return 0; fi
        if [ "$s" = "failed" ]  && [ "$want" != "failed" ]; then
            echo "  execution $exec_id failed (status=failed)"; return 1
        fi
        sleep 2; t=$((t+2))
    done
    echo "  timeout waiting for $exec_id to reach $want (last=$s)"
    return 2
}

# ── Cleanup on exit ───────────────────────────────────────────────────────────

cleanup() {
    if [ -n "$EMULATOR_PID" ] && kill -0 "$EMULATOR_PID" 2>/dev/null; then
        kill "$EMULATOR_PID" 2>/dev/null || true
    fi
    [ -n "$EMULATOR_LOG" ] && rm -f "$EMULATOR_LOG"
}
trap cleanup EXIT

# ── Step 0: Sanity checks ─────────────────────────────────────────────────────

echo ""
echo "Nexora Device Emulator E2E Test"
echo "================================"
echo ""
info "Sanity check — verifying services are healthy..."

for svc_url in "$DEVICE_URL/health" "$PLUGIN_URL/health" "$EXEC_URL/health" \
               "$NET_URL/health" "$WS_URL/health" "$GW_URL/health"; do
    if ! curl -sf "$svc_url" > /dev/null 2>&1; then
        fail "Service not healthy: $svc_url"
        echo ""
        echo "Start the stack with:"
        echo "  docker compose -f docker-compose.dev.yml --profile smoke --profile emulator up -d"
        exit 1
    fi
done

# nexora-function-runtime is optional but needed for function.install/invoke
RUNTIME_OK=false
if curl -sf "$RUNTIME_URL/health" > /dev/null 2>&1; then
    RUNTIME_OK=true
    ok "Sanity check: all services healthy (runtime available)"
else
    ok "Sanity check: core services healthy (runtime NOT available — function steps will be skipped)"
fi
echo ""

# ── Step 1: Generate WASM artifact + copy into runtime container ──────────────

WASM_FILE="/tmp/nxr-e2e-test.wasm"
RUNTIME_CONTAINER="${RUNTIME_CONTAINER:-nexora-function-runtime}"
RUNTIME_WASM_PATH="/tmp/nxr-e2e-test.wasm"

info "Generating WASM artifact..."
python3 -c "
# Minimal valid WASM: (module (func (export '_start'))) — 36 bytes
b = bytes([
    0x00,0x61,0x73,0x6D,0x01,0x00,0x00,0x00,
    0x01,0x04,0x01,0x60,0x00,0x00,
    0x03,0x02,0x01,0x00,
    0x07,0x0a,0x01,0x06,0x5f,0x73,0x74,0x61,0x72,0x74,0x00,0x00,
    0x0a,0x04,0x01,0x02,0x00,0x0b,
])
open('$WASM_FILE','wb').write(b)
print(f'Written {len(b)} bytes to $WASM_FILE')
"
ARTIFACT_CHECKSUM=$(python3 -c "import hashlib; print('sha256:'+hashlib.sha256(open('$WASM_FILE','rb').read()).hexdigest())")

if [ "$RUNTIME_OK" = "true" ]; then
    # Copy WASM into the runtime container so it can use file:// URI
    docker cp "$WASM_FILE" "${RUNTIME_CONTAINER}:${RUNTIME_WASM_PATH}" 2>/dev/null || {
        info "docker cp failed — runtime container '${RUNTIME_CONTAINER}' not found; skipping function steps"
        RUNTIME_OK=false
    }
fi

ARTIFACT_URI="file://${RUNTIME_WASM_PATH}"
ok "WASM artifact ready (checksum=${ARTIFACT_CHECKSUM:0:20}...)"
echo ""

# ── Step 2: Start emulator in background ─────────────────────────────────────

info "Starting emulator (1 board, POLL=${EMULATOR_POLL_SECONDS}s)..."
EMULATOR_LOG=$(mktemp /tmp/nxr-e2e-emulator.XXXXXX.log)

DEVICE_URL="$DEVICE_URL" \
EXEC_URL="$EXEC_URL" \
GW_URL="$GW_URL" \
RUNTIME_URL="$RUNTIME_URL" \
BOOTSTRAP_TOKEN="$BOOTSTRAP_TOKEN" \
POLL_SECONDS="$EMULATOR_POLL_SECONDS" \
python3 services/nexora-device-emulator/emulator.py \
    --board-name-prefix "e2e-board" \
    > "$EMULATOR_LOG" 2>&1 &
EMULATOR_PID=$!

# Wait for registration log line
info "Waiting for board registration..."
DEVICE_ID=""
for i in $(seq 1 20); do
    if ! kill -0 "$EMULATOR_PID" 2>/dev/null; then
        fail "Emulator process died. Log:"
        cat "$EMULATOR_LOG"
        exit 1
    fi
    DEVICE_ID=$(grep -m1 '"registered"' "$EMULATOR_LOG" 2>/dev/null \
        | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('device_id',''))" 2>/dev/null || true)
    [ -n "$DEVICE_ID" ] && break
    sleep 1
done

if [ -z "$DEVICE_ID" ]; then
    fail "Board did not register within 20s. Emulator log:"
    cat "$EMULATOR_LOG"
    exit 1
fi
ok "Board registered: $DEVICE_ID"
echo ""

# ── Step 3: Create + activate plugin ─────────────────────────────────────────

info "Creating plugin in plugin-service..."
PLUGIN_RESP=$(_post "$PLUGIN_URL/api/v2/plugins" "{
  \"name\": \"e2e-test-function\",
  \"version\": \"1.0.0\",
  \"module_type\": \"function\",
  \"artifact_uri\": \"$ARTIFACT_URI\",
  \"artifact_checksum\": \"$ARTIFACT_CHECKSUM\",
  \"runtime_type\": \"wasm-wasi\",
  \"entrypoint\": \"_start\",
  \"timeout_seconds\": 10,
  \"memory_limit_mb\": 16,
  \"permissions\": []
}")
PLUGIN_ID=$(echo "$PLUGIN_RESP" | jq_get id)
PLUGIN_STATUS=$(echo "$PLUGIN_RESP" | jq_get status)

if [ -z "$PLUGIN_ID" ]; then
    fail "Plugin creation failed. Response: $PLUGIN_RESP"
    exit 1
fi
ok "Plugin created: $PLUGIN_ID (status=$PLUGIN_STATUS)"

info "Activating plugin..."
ACTIVATE_RESP=$(_patch "$PLUGIN_URL/api/v2/plugins/$PLUGIN_ID/activate" '{}')
PLUGIN_STATUS=$(echo "$ACTIVATE_RESP" | jq_get status)
if [ "$PLUGIN_STATUS" != "active" ]; then
    fail "Plugin activation failed (status=$PLUGIN_STATUS)"
else
    ok "Plugin activated (status=active)"
fi
echo ""

# ── Step 4: function.install dispatch ────────────────────────────────────────

if [ "$RUNTIME_OK" = "true" ]; then
    info "Creating function.install execution..."
    INSTALL_EXEC=$(_post "$EXEC_URL/api/v2/executions" "{
      \"device_id\": \"$DEVICE_ID\",
      \"execution_type\": \"function.install\",
      \"plugin_id\": \"$PLUGIN_ID\",
      \"command\": \"function.install:$PLUGIN_ID\"
    }")
    INSTALL_ID=$(echo "$INSTALL_EXEC" | jq_get id)

    if [ -z "$INSTALL_ID" ]; then
        fail "function.install execution creation failed. Response: $INSTALL_EXEC"
    else
        info "Dispatching function.install: $INSTALL_ID"
        _post "$EXEC_URL/api/v2/executions/$INSTALL_ID/dispatch" '{}' > /dev/null

        if poll_status "$INSTALL_ID" "succeeded" 40; then
            INSTALL_RESULT=$(_get "$EXEC_URL/api/v2/executions/$INSTALL_ID")
            EXIT_CODE=$(echo "$INSTALL_RESULT" | jq_get exit_code)
            ok "function.install succeeded (exit_code=$EXIT_CODE)"
        else
            fail "function.install did not succeed within timeout"
        fi
    fi
    echo ""

    # ── Step 5: function.invoke dispatch ──────────────────────────────────────

    info "Creating function.invoke execution..."
    INVOKE_EXEC=$(_post "$EXEC_URL/api/v2/executions" "{
      \"device_id\": \"$DEVICE_ID\",
      \"execution_type\": \"function.invoke\",
      \"plugin_id\": \"$PLUGIN_ID\",
      \"command\": \"function.invoke:$PLUGIN_ID\",
      \"args\": {\"e2e\": true}
    }")
    INVOKE_ID=$(echo "$INVOKE_EXEC" | jq_get id)

    if [ -z "$INVOKE_ID" ]; then
        fail "function.invoke execution creation failed. Response: $INVOKE_EXEC"
    else
        info "Dispatching function.invoke: $INVOKE_ID"
        _post "$EXEC_URL/api/v2/executions/$INVOKE_ID/dispatch" '{}' > /dev/null

        if poll_status "$INVOKE_ID" "succeeded" 40; then
            INVOKE_RESULT=$(_get "$EXEC_URL/api/v2/executions/$INVOKE_ID")
            FUNC_RESULT=$(echo "$INVOKE_RESULT" | python3 -c \
                "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('function_result')))" 2>/dev/null || echo "null")
            ok "function.invoke succeeded: function_result=$FUNC_RESULT"
        else
            fail "function.invoke did not succeed within timeout"
        fi
    fi
    echo ""
else
    info "Skipping function.install / function.invoke (nexora-function-runtime not running)"
    info "Start it with: docker compose -f docker-compose.dev.yml --profile emulator up -d nexora-function-runtime"
    echo ""
fi

# ── Step 6: Network port ──────────────────────────────────────────────────────

info "Creating network port for device..."
PORT_RESP=$(_post "$NET_URL/api/v2/ports" "{
  \"device_id\": \"$DEVICE_ID\",
  \"network_id\": \"e2e-net\",
  \"status\": \"created\",
  \"ip_address\": \"10.99.1.1\"
}")
PORT_ID=$(echo "$PORT_RESP" | jq_get id)

if [ -z "$PORT_ID" ]; then
    fail "Port creation failed. Response: $PORT_RESP"
else
    ok "Port created: $PORT_ID (status=created)"

    info "Attaching port..."
    ATTACH_RESP=$(_patch "$NET_URL/api/v2/ports/$PORT_ID" '{"status":"attached"}')
    PORT_STATUS=$(echo "$ATTACH_RESP" | jq_get status)
    if [ "$PORT_STATUS" = "attached" ]; then
        ok "Port attached: $PORT_ID"
    else
        fail "Port attach failed (status=$PORT_STATUS)"
    fi
fi
echo ""

# ── Step 7: Webservice ────────────────────────────────────────────────────────

info "Registering webservice on device..."
WS_RESP=$(_post "$WS_URL/api/v2/webservices" "{
  \"device_id\": \"$DEVICE_ID\",
  \"port\": 8080,
  \"status\": \"enabled\",
  \"hostname\": \"e2e-board.local\",
  \"tls_enabled\": false
}")
WS_ID=$(echo "$WS_RESP" | jq_get id)

if [ -z "$WS_ID" ]; then
    fail "Webservice creation failed. Response: $WS_RESP"
else
    WS_STATUS=$(_get "$WS_URL/api/v2/webservices/$WS_ID" | jq_get status)
    if [ "$WS_STATUS" = "enabled" ]; then
        ok "Webservice registered: $WS_ID (status=enabled, hostname=e2e-board.local:8080)"
    else
        fail "Webservice status unexpected: $WS_STATUS"
    fi
fi
echo ""

# ── Summary ───────────────────────────────────────────────────────────────────

TOTAL=$((PASS+FAIL))
echo "──────────────────────────────────────────"
if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}=== E2E PASSED ($PASS/$TOTAL steps) ===${NC}"
    EXIT_CODE=0
else
    echo -e "${RED}=== E2E FAILED ($FAIL/$TOTAL steps failed) ===${NC}"
    EXIT_CODE=1
fi
echo ""
exit $EXIT_CODE
