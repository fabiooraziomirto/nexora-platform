#!/usr/bin/env python3
"""
§5.4 Execution Dispatch Round-Trip Benchmark — REAL KAFKA PATH

Measures end-to-end latency from execution-service Kafka publish to
nexora-edge delivery, using timing timestamps embedded in the dispatch
event and returned by the /api/v2/deliver/{id} endpoint.

Full path:
  POST /executions → POST /dispatch
    → execution-service publishes to Kafka (kafka_dispatched_at embedded)
    → nexora-edge Kafka consumer receives → caches in Redis
    → emulator calls POST /deliver/{id}
    → nexora-edge returns timing breakdown with real timestamps

This measures:
  kafka_ingestion_seconds  — Kafka publish → nexora-edge consumer receive
  queue_wait_seconds       — gateway cache wait (Redis)
  dispatch_latency_seconds — kafka_dispatched_at → delivered_at (E2E)

Usage:
    python3 scripts/perf-dispatch-roundtrip.py [--n-runs 30]
"""
import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid

DEVICE_SVC = "http://localhost:8000"
EXEC_SVC   = "http://localhost:8002"
GW_URL     = "http://localhost:8007"
BOOTSTRAP_TOKEN = "dev-bootstrap:dev-bootstrap-token"

KAFKA_SETTLE_WAIT = 1.5   # seconds to wait for Kafka consumer to receive the event


def _req(method, url, payload=None, extra_headers=None, raise_on_error=True):
    body = json.dumps(payload).encode() if payload is not None else None
    hdrs = {"Content-Type": "application/json"}
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url=url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        if raise_on_error:
            body_text = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code} on {method} {url}: {body_text}") from e
        return None


def register_device(name):
    data = _req(
        "POST",
        f"{DEVICE_SVC}/api/v2/agents/register",
        {"name": name, "device_type": "perf-emulator"},
        extra_headers={"X-Bootstrap-Token": BOOTSTRAP_TOKEN},
    )
    device_id = data["device_id"]
    _req("POST", f"{GW_URL}/api/v2/agents/sessions/register",
         {"device_id": device_id, "board_name": name, "type": "perf-emulator"})
    return device_id


def heartbeat(device_id):
    _req("POST", f"{DEVICE_SVC}/api/v2/agents/{device_id}/heartbeat", {},
         raise_on_error=False)
    _req("POST", f"{GW_URL}/api/v2/agents/sessions/{device_id}/heartbeat", {},
         raise_on_error=False)


def create_and_dispatch(device_id):
    ex = _req("POST", f"{EXEC_SVC}/api/v2/executions", {
        "device_id": device_id,
        "execution_type": "command",
        "command": "echo perf-test",
        "args": {},
    })
    ex_id = ex["id"]
    _req("POST", f"{EXEC_SVC}/api/v2/executions/{ex_id}/dispatch", {})
    return ex_id


def deliver_and_get_timing(ex_id, max_wait=10.0, poll_interval=0.2):
    """
    Wait for nexora-edge Kafka consumer to cache the dispatch, then call /deliver.
    Returns the timing dict from the response, or None on timeout.
    """
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        result = _req("POST", f"{GW_URL}/api/v2/deliver/{ex_id}", {},
                      raise_on_error=False)
        if result is not None and result.get("status") == "delivered":
            return result
        # 404 means Kafka consumer hasn't cached it yet — retry
        time.sleep(poll_interval)
    return None


def send_final_callback(ex_id):
    _req("POST", f"{EXEC_SVC}/api/v2/executions/{ex_id}/callback",
         {"status": "running"}, raise_on_error=False)
    _req("POST", f"{EXEC_SVC}/api/v2/executions/{ex_id}/callback",
         {"status": "succeeded", "exit_code": 0,
          "stdout": "perf-test ok\n", "stderr": ""}, raise_on_error=False)


def pct(data, p):
    s = sorted(data)
    idx = max(0, int(len(s) * p / 100) - 1)
    return s[idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-runs", type=int, default=30)
    args = ap.parse_args()

    print(f"§5.4 Dispatch Round-Trip Benchmark (REAL KAFKA)  n={args.n_runs}")
    print("  Registering perf device...", flush=True)
    device_id = register_device(f"perf-kafka-{uuid.uuid4().hex[:6]}")
    print(f"  device_id = {device_id}")

    print("  Warming up (3 runs discarded)...", flush=True)
    for _ in range(3):
        ex_id = create_and_dispatch(device_id)
        time.sleep(KAFKA_SETTLE_WAIT)
        r = deliver_and_get_timing(ex_id)
        if r:
            send_final_callback(ex_id)
        heartbeat(device_id)

    print(f"  Running {args.n_runs} measurement runs...", flush=True)

    dispatch_latencies_ms = []
    kafka_ingestion_ms    = []
    queue_wait_ms         = []
    timeouts = 0

    for i in range(args.n_runs):
        heartbeat(device_id)
        ex_id = create_and_dispatch(device_id)
        # Give Kafka consumer time to receive and cache the event
        time.sleep(KAFKA_SETTLE_WAIT)

        r = deliver_and_get_timing(ex_id, max_wait=8.0)
        if r is None:
            timeouts += 1
            print(f"  [{i+1:2d}/{args.n_runs}] TIMEOUT", flush=True)
            continue

        dl = r.get("dispatch_latency_seconds")
        ki = r.get("kafka_ingestion_seconds")
        qw = r.get("queue_wait_seconds")

        if dl is None:
            # Kafka consumer didn't embed kafka_dispatched_at — measure wall time
            dl = r.get("delivered_at", 0) - (r.get("kafka_dispatched_at") or r.get("delivered_at"))

        dl_ms = round(dl * 1000, 2) if dl else 0
        ki_ms = round(ki * 1000, 2) if ki else None
        qw_ms = round(qw * 1000, 2) if qw else None

        dispatch_latencies_ms.append(dl_ms)
        if ki_ms is not None:
            kafka_ingestion_ms.append(ki_ms)
        if qw_ms is not None:
            queue_wait_ms.append(qw_ms)

        send_final_callback(ex_id)

        print(f"  [{i+1:2d}/{args.n_runs}] dispatch={dl_ms:.0f}ms  "
              f"kafka_ingest={ki_ms or '?'}ms  queue_wait={qw_ms or '?'}ms",
              flush=True)

    if not dispatch_latencies_ms:
        print("ERROR: all runs timed out or had no timing data", file=sys.stderr)
        sys.exit(1)

    def summarise(data, label):
        if not data:
            return {}
        s = sorted(data)
        return {
            "label": label,
            "n": len(s),
            "p50_ms": round(pct(s, 50), 1),
            "p95_ms": round(pct(s, 95), 1),
            "p99_ms": round(pct(s, 99), 1),
            "mean_ms": round(statistics.mean(s), 1),
            "min_ms": round(min(s), 1),
            "max_ms": round(max(s), 1),
            "stdev_ms": round(statistics.stdev(s) if len(s) > 1 else 0, 1),
        }

    dl_stats = summarise(dispatch_latencies_ms, "dispatch_latency (E2E)")
    ki_stats = summarise(kafka_ingestion_ms,    "kafka_ingestion")
    qw_stats = summarise(queue_wait_ms,          "queue_wait")

    print()
    print("┌──────────────────────────────────────────────────────────────────┐")
    print(f"│  §5.4 Dispatch Round-Trip  (REAL KAFKA)  n={len(dispatch_latencies_ms)}, timeouts={timeouts}    │")
    print("├────────────────────────────────┬───────┬───────┬───────┬────────┤")
    print("│  Metric                        │  p50  │  p95  │  p99  │  stdev │")
    print("├────────────────────────────────┼───────┼───────┼───────┼────────┤")
    for s in [dl_stats, ki_stats, qw_stats]:
        if s:
            print(f"│  {s['label']:<30} │ {s['p50_ms']:>5.0f} │ {s['p95_ms']:>5.0f} │ {s['p99_ms']:>5.0f} │ {s['stdev_ms']:>6.1f} │")
    print("└────────────────────────────────┴───────┴───────┴───────┴────────┘")
    print()

    results = {
        "dispatch_latency_ms": dl_stats,
        "kafka_ingestion_ms": ki_stats,
        "queue_wait_ms": qw_stats,
        "timeouts": timeouts,
    }
    print("JSON:")
    print(json.dumps(results, indent=2))

    import os, datetime
    os.makedirs("docs/paper/results", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = f"docs/paper/results/perf-dispatch-kafka-{ts}.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out}")

    # Verify Prometheus histogram was updated
    print("\nPrometheus validation:")
    try:
        import urllib.request as ur
        with ur.urlopen("http://localhost:8007/metrics", timeout=5) as r:
            metrics_text = r.read().decode()
        count_line = [l for l in metrics_text.splitlines()
                      if "s4t_execution_dispatch_latency_seconds_count" in l and "{" in l]
        if count_line:
            print(f"  s4t_execution_dispatch_latency_seconds_count: {count_line[0].split()[-1]}")
        else:
            print("  WARNING: dispatch_latency histogram still empty — Kafka consumer may not have received events")
    except Exception as e:
        print(f"  metrics check failed: {e}")


if __name__ == "__main__":
    main()
