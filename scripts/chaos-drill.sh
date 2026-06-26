#!/usr/bin/env bash
# chaos-drill.sh — Structured fault-injection scenarios for Nexora platform
#
# Exercises 6 chaos scenarios and emits JSONL results to results/chaos-<timestamp>.jsonl
# Requires a running stack: docker compose -f docker-compose.dev.yml --profile dev up -d
#
# Usage:
#   bash scripts/chaos-drill.sh
#   DEVICE_URL=http://localhost:8000 EXEC_URL=http://localhost:8002 bash scripts/chaos-drill.sh

set -euo pipefail

DEVICE_URL="${DEVICE_URL:-http://localhost:8000}"
EXEC_URL="${EXEC_URL:-http://localhost:8002}"
GW_URL="${GW_URL:-http://localhost:8007}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"

RESULTS_DIR="results"
mkdir -p "$RESULTS_DIR"
TIMESTAMP=$(date +%Y%m%dT%H%M%S)
RESULTS_FILE="$RESULTS_DIR/chaos-${TIMESTAMP}.jsonl"

PASS=0
FAIL=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_log() {
    local scenario="$1" status="$2" detail="$3"
    local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    printf '{"ts":"%s","scenario":"%s","status":"%s","detail":%s}\n' \
        "$ts" "$scenario" "$status" "$detail" | tee -a "$RESULTS_FILE"
    if [[ "$status" == "PASS" ]]; then
        PASS=$((PASS + 1))
        echo "  [PASS] $scenario"
    else
        FAIL=$((FAIL + 1))
        echo "  [FAIL] $scenario — $detail"
    fi
}

_assert_http() {
    local label="$1" url="$2" expected_status="$3"
    local actual; actual=$(curl -s -o /dev/null -w "%{http_code}" "$url") || actual="000"
    if [[ "$actual" == "$expected_status" ]]; then
        _log "$label" "PASS" "{\"url\":\"$url\",\"expected\":$expected_status,\"actual\":$actual}"
    else
        _log "$label" "FAIL" "{\"url\":\"$url\",\"expected\":$expected_status,\"actual\":$actual}"
    fi
}

_assert_http_post() {
    local label="$1" url="$2" body="$3" expected_status="$4"
    local actual; actual=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Content-Type: application/json" -d "$body" "$url") || actual="000"
    if [[ "$actual" == "$expected_status" ]]; then
        _log "$label" "PASS" "{\"url\":\"$url\",\"expected\":$expected_status,\"actual\":$actual}"
    else
        _log "$label" "FAIL" "{\"url\":\"$url\",\"expected\":$expected_status,\"actual\":$actual}"
    fi
}

_wait_healthy() {
    local svc="$1" url="$2" retries="${3:-12}" delay="${4:-5}"
    for i in $(seq 1 "$retries"); do
        if curl -fsS "$url" >/dev/null 2>&1; then return 0; fi
        sleep "$delay"
    done
    echo "  [WARN] $svc did not recover at $url after $((retries * delay))s"
    return 1
}

echo "================================================================"
echo " Nexora Chaos Drill — $(date)"
echo " Results → $RESULTS_FILE"
echo "================================================================"

# ---------------------------------------------------------------------------
# Pre-flight: services must be reachable
# ---------------------------------------------------------------------------
echo
echo "--- Pre-flight check ---"
for url in "$DEVICE_URL/health" "$EXEC_URL/health" "$GW_URL/health"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")
    if [[ "$code" != "200" ]]; then
        echo "ABORT: $url returned $code — start the stack first"
        exit 1
    fi
done
echo "  All three services healthy — proceeding"

# Create a test device for scenarios that need one
DEVICE_RESP=$(curl -s -X POST "$DEVICE_URL/api/v2/devices" \
    -H "Content-Type: application/json" \
    -d '{"name":"chaos-test-device","device_type":"chaos"}') || DEVICE_RESP="{}"
DEVICE_ID=$(echo "$DEVICE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
if [[ -z "$DEVICE_ID" ]]; then
    echo "WARN: could not create test device — some scenarios will be skipped"
fi

# ---------------------------------------------------------------------------
# Scenario 1: Kafka broker failure → graceful degradation
# ---------------------------------------------------------------------------
echo
echo "--- Scenario 1: Kafka broker failure ---"

docker compose -f "$COMPOSE_FILE" stop kafka >/dev/null 2>&1 || true
sleep 4

# /health must still return 200 (liveness is not gated on Kafka)
_assert_http "s1_device_health_during_kafka_down" "$DEVICE_URL/health" "200"
_assert_http "s1_exec_health_during_kafka_down" "$EXEC_URL/health" "200"
_assert_http "s1_gw_health_during_kafka_down" "$GW_URL/health" "200"

# /ready on execution-service: KAFKA_REQUIRED=false → still 200
_assert_http "s1_exec_ready_kafka_required_false" "$EXEC_URL/ready" "200"

# Creating an execution while Kafka is down must still succeed (KAFKA_REQUIRED=false)
if [[ -n "$DEVICE_ID" ]]; then
    _assert_http_post "s1_create_execution_kafka_down" \
        "$EXEC_URL/api/v2/executions" \
        "{\"device_id\":\"$DEVICE_ID\",\"command\":\"chaos-noop\"}" \
        "201"
fi

# Restore Kafka
docker compose -f "$COMPOSE_FILE" start kafka >/dev/null 2>&1 || true
echo "  Waiting for Kafka to recover..."
sleep 15
_wait_healthy "kafka-dependent-exec" "$EXEC_URL/ready" 12 5 || true

_assert_http "s1_exec_ready_after_kafka_recovery" "$EXEC_URL/ready" "200"
_assert_http "s1_gw_ready_after_kafka_recovery" "$GW_URL/ready" "200"

# ---------------------------------------------------------------------------
# Scenario 2: Redis failure → gateway falls back to in-memory store
# ---------------------------------------------------------------------------
echo
echo "--- Scenario 2: Redis failure → in-memory fallback ---"

docker compose -f "$COMPOSE_FILE" stop redis >/dev/null 2>&1 || true
sleep 3

# Gateway /health must stay 200 (Redis is not a liveness gate)
_assert_http "s2_gw_health_redis_down" "$GW_URL/health" "200"

# Session register must still work (in-memory fallback)
SESS_RESP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$GW_URL/api/v2/agents/sessions/register" \
    -H "Content-Type: application/json" \
    -d '{"device_id":"chaos-fallback-device"}') || SESS_RESP="000"
if [[ "$SESS_RESP" == "201" ]]; then
    _log "s2_session_register_redis_down" "PASS" \
        "{\"note\":\"in-memory fallback active\",\"http\":$SESS_RESP}"
else
    _log "s2_session_register_redis_down" "FAIL" \
        "{\"note\":\"expected 201 via fallback\",\"http\":$SESS_RESP}"
fi

# Heartbeat must also work via in-memory store
HB_RESP=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "$GW_URL/api/v2/agents/sessions/chaos-fallback-device/heartbeat") || HB_RESP="000"
if [[ "$HB_RESP" == "200" ]]; then
    _log "s2_heartbeat_redis_down" "PASS" "{\"http\":$HB_RESP}"
else
    _log "s2_heartbeat_redis_down" "FAIL" "{\"http\":$HB_RESP}"
fi

# Restore Redis
docker compose -f "$COMPOSE_FILE" start redis >/dev/null 2>&1 || true
echo "  Waiting for Redis to recover..."
sleep 8
_wait_healthy "redis" "$GW_URL/ready" 6 4 || true

_assert_http "s2_gw_ready_after_redis_recovery" "$GW_URL/ready" "200"

# ---------------------------------------------------------------------------
# Scenario 3: Delivery retry exhaustion (no agent session)
# ---------------------------------------------------------------------------
echo
echo "--- Scenario 3: Delivery exhaustion — no active session ---"

# Create + dispatch an execution for a device that has no registered session
ORPHAN_EXEC=$(curl -s -X POST "$EXEC_URL/api/v2/executions" \
    -H "Content-Type: application/json" \
    -d '{"device_id":"orphan-device-chaos","command":"chaos-orphan"}') || ORPHAN_EXEC="{}"
ORPHAN_ID=$(echo "$ORPHAN_EXEC" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

if [[ -n "$ORPHAN_ID" ]]; then
    # Dispatch it
    curl -s -X POST "$EXEC_URL/api/v2/executions/$ORPHAN_ID/dispatch" >/dev/null 2>&1 || true
    # Attempt delivery — should fail with 502 after retry exhaustion
    sleep 1
    DELIVER_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        "$GW_URL/api/v2/deliver/$ORPHAN_ID") || DELIVER_CODE="000"
    if [[ "$DELIVER_CODE" == "502" || "$DELIVER_CODE" == "404" ]]; then
        _log "s3_delivery_exhaustion_no_session" "PASS" \
            "{\"execution_id\":\"$ORPHAN_ID\",\"http\":$DELIVER_CODE,\"note\":\"expected 502 or 404\"}"
    else
        _log "s3_delivery_exhaustion_no_session" "FAIL" \
            "{\"execution_id\":\"$ORPHAN_ID\",\"http\":$DELIVER_CODE}"
    fi
else
    _log "s3_delivery_exhaustion_no_session" "FAIL" \
        "{\"note\":\"could not create orphan execution\"}"
fi

# ---------------------------------------------------------------------------
# Scenario 4: Execution rate limit (>MAX_EXECUTIONS_PER_DEVICE)
# ---------------------------------------------------------------------------
echo
echo "--- Scenario 4: Per-device execution rate limit (MAX=32) ---"

if [[ -n "$DEVICE_ID" ]]; then
    # Dispatch 32 executions to saturate the device's active slot
    SATURATE_IDS=()
    for i in $(seq 1 32); do
        EX=$(curl -s -X POST "$EXEC_URL/api/v2/executions" \
            -H "Content-Type: application/json" \
            -d "{\"device_id\":\"$DEVICE_ID\",\"command\":\"sat-$i\"}") || EX="{}"
        EID=$(echo "$EX" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
        [[ -n "$EID" ]] && SATURATE_IDS+=("$EID")
    done
    echo "  Saturated device with ${#SATURATE_IDS[@]} queued executions"

    # The 33rd must be rejected with 429
    RATE_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$EXEC_URL/api/v2/executions" \
        -H "Content-Type: application/json" \
        -d "{\"device_id\":\"$DEVICE_ID\",\"command\":\"over-limit\"}") || RATE_CODE="000"
    if [[ "$RATE_CODE" == "429" ]]; then
        _log "s4_rate_limit_429" "PASS" \
            "{\"device_id\":\"$DEVICE_ID\",\"queued\":${#SATURATE_IDS[@]},\"http\":$RATE_CODE}"
    else
        _log "s4_rate_limit_429" "FAIL" \
            "{\"device_id\":\"$DEVICE_ID\",\"queued\":${#SATURATE_IDS[@]},\"http\":$RATE_CODE}"
    fi

    # Clean up: cancel all saturating executions
    for eid in "${SATURATE_IDS[@]}"; do
        curl -s -X POST "$EXEC_URL/api/v2/executions/$eid/cancel" >/dev/null 2>&1 || true
    done
else
    _log "s4_rate_limit_429" "FAIL" "{\"note\":\"no test device available\"}"
fi

# ---------------------------------------------------------------------------
# Scenario 5: Idempotency key deduplication under concurrent submissions
# ---------------------------------------------------------------------------
echo
echo "--- Scenario 5: Idempotency key deduplication ---"

IDEM_KEY="chaos-idem-$(date +%s)"
BODY="{\"command\":\"idem-test\",\"idempotency_key\":\"$IDEM_KEY\"}"

# First submission → 201
FIRST_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$EXEC_URL/api/v2/executions" \
    -H "Content-Type: application/json" -d "$BODY") || FIRST_CODE="000"

# Second identical submission → 200 (deduplicated)
SECOND_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$EXEC_URL/api/v2/executions" \
    -H "Content-Type: application/json" -d "$BODY") || SECOND_CODE="000"

if [[ "$FIRST_CODE" == "201" && "$SECOND_CODE" == "200" ]]; then
    _log "s5_idempotency_dedup" "PASS" \
        "{\"key\":\"$IDEM_KEY\",\"first_http\":$FIRST_CODE,\"second_http\":$SECOND_CODE}"
else
    _log "s5_idempotency_dedup" "FAIL" \
        "{\"key\":\"$IDEM_KEY\",\"first_http\":$FIRST_CODE,\"second_http\":$SECOND_CODE}"
fi

# ---------------------------------------------------------------------------
# Scenario 6: Invalid state-machine transition (dispatch already-dispatched)
# ---------------------------------------------------------------------------
echo
echo "--- Scenario 6: Invalid execution state transition ---"

EX6=$(curl -s -X POST "$EXEC_URL/api/v2/executions" \
    -H "Content-Type: application/json" \
    -d '{"command":"double-dispatch"}') || EX6="{}"
EID6=$(echo "$EX6" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

if [[ -n "$EID6" ]]; then
    # First dispatch → should succeed
    curl -s -X POST "$EXEC_URL/api/v2/executions/$EID6/dispatch" >/dev/null 2>&1 || true
    # Second dispatch of same execution → must return 409 (invalid transition)
    CODE6=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        "$EXEC_URL/api/v2/executions/$EID6/dispatch") || CODE6="000"
    if [[ "$CODE6" == "409" ]]; then
        _log "s6_invalid_state_transition" "PASS" \
            "{\"execution_id\":\"$EID6\",\"http\":$CODE6}"
    else
        _log "s6_invalid_state_transition" "FAIL" \
            "{\"execution_id\":\"$EID6\",\"http\":$CODE6}"
    fi
else
    _log "s6_invalid_state_transition" "FAIL" "{\"note\":\"could not create execution\"}"
fi

# ---------------------------------------------------------------------------
# Cleanup: delete test device
# ---------------------------------------------------------------------------
if [[ -n "$DEVICE_ID" ]]; then
    curl -s -X DELETE "$DEVICE_URL/api/v2/devices/$DEVICE_ID" >/dev/null 2>&1 || true
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
TOTAL=$((PASS + FAIL))
echo
echo "================================================================"
echo " Chaos Drill Summary"
printf " Scenarios: %d  |  PASS: %d  |  FAIL: %d\n" "$TOTAL" "$PASS" "$FAIL"
echo " Results:   $RESULTS_FILE"
echo "================================================================"

_log "SUMMARY" "$([ "$FAIL" -eq 0 ] && echo PASS || echo FAIL)" \
    "{\"total\":$TOTAL,\"pass\":$PASS,\"fail\":$FAIL}"

[[ "$FAIL" -eq 0 ]]
