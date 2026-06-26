#!/usr/bin/env bash
# perf-dispatch-latency.sh — parametric dispatch latency benchmark
#
# Runs N_BOARDS emulator processes for DURATION_SECONDS, then scrapes
# Prometheus metrics and writes a JSONL result file.
#
# Usage:
#   N_BOARDS=10 POLL_SECONDS=2 DURATION=60 bash scripts/perf-dispatch-latency.sh
#
# Output:
#   results/perf-dispatch-<N_BOARDS>boards-poll<POLL_SECONDS>s-<timestamp>.jsonl

set -euo pipefail

N_BOARDS="${N_BOARDS:-5}"
POLL_SECONDS="${POLL_SECONDS:-4}"
FAIL_RATE="${FAIL_RATE:-0.0}"
DELAY_MS="${DELAY_MS:-0}"
DURATION="${DURATION:-60}"
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8007}"
EMULATOR="${EMULATOR:-services/lr-board-emulator/emulator.py}"

TIMESTAMP=$(date +%Y%m%dT%H%M%S)
RESULTS_DIR="results"
OUT_FILE="${RESULTS_DIR}/perf-dispatch-${N_BOARDS}boards-poll${POLL_SECONDS}s-${TIMESTAMP}.jsonl"

mkdir -p "$RESULTS_DIR"

echo "=== perf-dispatch-latency ==="
echo "  N_BOARDS    = $N_BOARDS"
echo "  POLL_SECONDS= $POLL_SECONDS"
echo "  FAIL_RATE   = $FAIL_RATE"
echo "  DELAY_MS    = $DELAY_MS"
echo "  DURATION    = ${DURATION}s"
echo "  OUTPUT      = $OUT_FILE"
echo ""

echo '{"event":"run_start","ts":"'"$TIMESTAMP"'","n_boards":'"$N_BOARDS"',"poll_seconds":'"$POLL_SECONDS"',"fail_rate":'"$FAIL_RATE"',"delay_ms":'"$DELAY_MS"',"duration_s":'"$DURATION"'}' >> "$OUT_FILE"

N_BOARDS="$N_BOARDS" \
POLL_SECONDS="$POLL_SECONDS" \
FAIL_RATE="$FAIL_RATE" \
DELAY_MS="$DELAY_MS" \
BOARD_NAME_PREFIX="perf-board" \
  python3 "$EMULATOR" >> "$OUT_FILE" 2>&1 &
EMULATOR_PID=$!
echo "[run] emulator PID=$EMULATOR_PID"

sleep "$DURATION"

kill "$EMULATOR_PID" 2>/dev/null || true
wait "$EMULATOR_PID" 2>/dev/null || true
echo "[run] emulator stopped"

echo "[run] scraping metrics from $GATEWAY_URL/metrics"
METRICS=$(curl -sf "$GATEWAY_URL/metrics" 2>/dev/null || echo "# metrics unavailable")

python3 - <<PYEOF >> "$OUT_FILE"
import re, json, time

raw = """$METRICS"""

def extract_histogram_sum_count(raw, metric_name):
    s = re.search(rf'{metric_name}_sum\\{{[^}}]*\\}} ([0-9.e+\\-]+)', raw)
    c = re.search(rf'{metric_name}_count\\{{[^}}]*\\}} ([0-9.e+\\-]+)', raw)
    total = float(s.group(1)) if s else None
    count = float(c.group(1)) if c else None
    mean = round(total / count, 6) if total and count and count > 0 else None
    return {"sum": total, "count": count, "mean_s": mean}

summary = {
    "event": "metrics_snapshot",
    "ts": round(time.time(), 3),
    "dispatch_latency": extract_histogram_sum_count(raw, "s4t_execution_dispatch_latency_seconds"),
    "kafka_ingestion_latency": extract_histogram_sum_count(raw, "s4t_lr_kafka_ingestion_latency_seconds"),
    "queue_wait": extract_histogram_sum_count(raw, "s4t_lr_queue_wait_seconds"),
    "delivery_attempts": None,
    "delivery_failures": None,
}

m = re.search(r's4t_lr_delivery_attempts_total\\{[^}]*\\} ([0-9.e+\\-]+)', raw)
summary["delivery_attempts"] = float(m.group(1)) if m else None

m = re.search(r's4t_lr_delivery_failures_total\\{[^}]*\\} ([0-9.e+\\-]+)', raw)
summary["delivery_failures"] = float(m.group(1)) if m else None

print(json.dumps(summary))
PYEOF

echo '{"event":"run_end","ts":"'"$(date +%Y%m%dT%H%M%S)"'"}' >> "$OUT_FILE"
echo ""
echo "=== Results written to $OUT_FILE ==="
cat "$OUT_FILE" | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        r = json.loads(line)
        if r.get('event') == 'metrics_snapshot':
            dl = r.get('dispatch_latency', {})
            print(f\"  dispatch_latency  mean={dl.get('mean_s')}s  count={dl.get('count')}\")
            ki = r.get('kafka_ingestion_latency', {})
            print(f\"  kafka_ingestion   mean={ki.get('mean_s')}s  count={ki.get('count')}\")
            qw = r.get('queue_wait', {})
            print(f\"  queue_wait        mean={qw.get('mean_s')}s  count={qw.get('count')}\")
            print(f\"  delivery_attempts={r.get('delivery_attempts')}  failures={r.get('delivery_failures')}\")
    except Exception:
        pass
"
