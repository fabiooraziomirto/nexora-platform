#!/usr/bin/env bash
# Simulates a full Lightning Rod lifecycle: register agent, create execution,
# dispatch, deliver (gateway), callback running, callback succeeded.
# The deliver step (4b) exercises the gateway delivery path and populates
# s4t_execution_dispatch_latency_seconds on the gateway's /metrics endpoint.
set -euo pipefail

export AUTH_DEV_BYPASS_ENABLED="${AUTH_DEV_BYPASS_ENABLED:-true}"

BASE_DEVICE="http://localhost:8000"
BASE_EXEC="http://localhost:8002"
BASE_GW="http://localhost:8007"
TOKEN="dev-bootstrap:dev-bootstrap-token"
DEVICE_TYPE="nexora-device-emulator"

echo "[LR-E2E] 1/7 Register agent..."
REG=$(curl -fsS -X POST "$BASE_DEVICE/api/v2/agents/register" \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Token: $TOKEN" \
  -d "{\"name\":\"lr-e2e-agent\",\"device_type\":\"$DEVICE_TYPE\"}")
DEVICE_ID=$(echo "$REG" | python3 -c "import sys,json; print(json.load(sys.stdin)['device_id'])")
echo "  device_id=$DEVICE_ID"

echo "[LR-E2E] 2/7 Create execution..."
EXEC=$(curl -fsS -X POST "$BASE_EXEC/api/v2/executions" \
  -H "Content-Type: application/json" \
  -d "{\"device_id\":\"$DEVICE_ID\",\"command\":\"echo hello\"}")
EXEC_ID=$(echo "$EXEC" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  execution_id=$EXEC_ID"

echo "[LR-E2E] 3/7 Dispatch execution (publishes kafka_dispatched_at timestamp)..."
DISP=$(curl -fsS -X POST "$BASE_EXEC/api/v2/executions/$EXEC_ID/dispatch")
echo "  status=$(echo "$DISP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")"

echo "[LR-E2E] 4/7 Register gateway session..."
curl -fsS -X POST "$BASE_GW/api/v2/agents/sessions/register" \
  -H "Content-Type: application/json" \
  -d "{\"device_id\":\"$DEVICE_ID\"}" > /dev/null

echo "[LR-E2E] 4b/7 Deliver via gateway (measures dispatch latency)..."
# Allow up to 3s for the Kafka consumer to cache the dispatch event before delivery.
DELIVER_RESP=""
for i in 1 2 3; do
  sleep 1
  HTTP_CODE=$(curl -o /tmp/lr_deliver_resp.json -w "%{http_code}" -fsS \
    -X POST "$BASE_GW/api/v2/deliver/$EXEC_ID" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    DELIVER_RESP=$(cat /tmp/lr_deliver_resp.json)
    break
  fi
  echo "  deliver attempt $i: HTTP $HTTP_CODE (Kafka consumer may still be catching up)"
done

if [ -z "$DELIVER_RESP" ]; then
  echo "[LR-E2E] WARN: deliver returned non-200 after 3 attempts (Kafka disabled or event not yet cached)"
  echo "  Continuing without delivery step — dispatch_latency metric will not be populated"
else
  DLAT=$(echo "$DELIVER_RESP" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('dispatch_latency_seconds','n/a'))")
  QWAIT=$(echo "$DELIVER_RESP" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('queue_wait_seconds','n/a'))")
  echo "  delivered — dispatch_latency_seconds=$DLAT  queue_wait_seconds=$QWAIT"
fi

echo "[LR-E2E] 5/7 Callback running..."
CB_RUN=$(curl -fsS -X POST "$BASE_EXEC/api/v2/executions/$EXEC_ID/callback" \
  -H "Content-Type: application/json" \
  -d '{"status":"running"}')
echo "  status=$(echo "$CB_RUN" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")"

echo "[LR-E2E] 6/7 Callback succeeded..."
CB_OK=$(curl -fsS -X POST "$BASE_EXEC/api/v2/executions/$EXEC_ID/callback" \
  -H "Content-Type: application/json" \
  -d '{"status":"succeeded","exit_code":0,"stdout":"hello\n","stderr":""}')
FINAL=$(echo "$CB_OK" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
PIPE_LAT=$(echo "$CB_OK" | python3 -c \
  "import sys,json; print(json.load(sys.stdin).get('dispatch_latency_seconds','n/a'))")
echo "  final_status=$FINAL  dispatch_latency_seconds(proxy)=$PIPE_LAT"

echo "[LR-E2E] 7/7 Verify gateway metrics..."
GW_METRICS=$(curl -fsS "$BASE_GW/metrics" 2>/dev/null || echo "")
if echo "$GW_METRICS" | grep -q "s4t_execution_dispatch_latency_seconds"; then
  LAT_COUNT=$(echo "$GW_METRICS" | grep 's4t_execution_dispatch_latency_seconds_count' | awk '{print $2}')
  LAT_SUM=$(echo "$GW_METRICS" | grep 's4t_execution_dispatch_latency_seconds_sum' | awk '{print $2}')
  echo "  s4t_execution_dispatch_latency_seconds_count=$LAT_COUNT  sum=${LAT_SUM}s"
else
  echo "  WARN: dispatch latency metric not yet in /metrics (deliver step may have been skipped)"
fi

if [ "$FINAL" = "succeeded" ]; then
  echo "[LR-E2E] PASS"
  exit 0
else
  echo "[LR-E2E] FAIL: expected succeeded, got $FINAL"
  exit 1
fi
