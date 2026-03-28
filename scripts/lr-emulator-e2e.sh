#!/usr/bin/env bash
# Simulates a full Lightning Rod lifecycle: register agent, create execution,
# dispatch, deliver, callback running, callback succeeded.
set -euo pipefail

BASE_DEVICE="http://localhost:8000"
BASE_EXEC="http://localhost:8002"
BASE_GW="http://localhost:8007"
TOKEN="dev-bootstrap:dev-bootstrap-token"
DEVICE_TYPE="lr-emulator"

echo "[LR-E2E] 1/6 Register agent..."
REG=$(curl -fsS -X POST "$BASE_DEVICE/api/v2/agents/register" \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Token: $TOKEN" \
  -d "{\"name\":\"lr-e2e-agent\",\"device_type\":\"$DEVICE_TYPE\"}")
DEVICE_ID=$(echo "$REG" | python3 -c "import sys,json; print(json.load(sys.stdin)['device_id'])")
echo "  device_id=$DEVICE_ID"

echo "[LR-E2E] 2/6 Create execution..."
EXEC=$(curl -fsS -X POST "$BASE_EXEC/api/v2/executions" \
  -H "Content-Type: application/json" \
  -d "{\"device_id\":\"$DEVICE_ID\",\"command\":\"echo hello\"}")
EXEC_ID=$(echo "$EXEC" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  execution_id=$EXEC_ID"

echo "[LR-E2E] 3/6 Dispatch execution..."
DISP=$(curl -fsS -X POST "$BASE_EXEC/api/v2/executions/$EXEC_ID/dispatch")
echo "  status=$(echo "$DISP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")"

echo "[LR-E2E] 4/6 Register gateway session..."
curl -fsS -X POST "$BASE_GW/api/v2/agents/sessions/register" \
  -H "Content-Type: application/json" \
  -d "{\"device_id\":\"$DEVICE_ID\"}" > /dev/null

echo "[LR-E2E] 5/6 Callback running..."
CB_RUN=$(curl -fsS -X POST "$BASE_EXEC/api/v2/executions/$EXEC_ID/callback" \
  -H "Content-Type: application/json" \
  -d '{"status":"running"}')
echo "  status=$(echo "$CB_RUN" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")"

echo "[LR-E2E] 6/6 Callback succeeded..."
CB_OK=$(curl -fsS -X POST "$BASE_EXEC/api/v2/executions/$EXEC_ID/callback" \
  -H "Content-Type: application/json" \
  -d '{"status":"succeeded","exit_code":0,"stdout":"hello\n","stderr":""}')
FINAL=$(echo "$CB_OK" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
echo "  final_status=$FINAL"

if [ "$FINAL" = "succeeded" ]; then
  echo "[LR-E2E] PASS"
  exit 0
else
  echo "[LR-E2E] FAIL: expected succeeded, got $FINAL"
  exit 1
fi
