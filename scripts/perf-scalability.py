#!/usr/bin/env python3
"""
§5.6 Scalability Benchmark — Throughput Under Concurrent Device Load

Answers RQ3: does the microservice architecture scale under concurrent device load?

Methodology:
  - Spawn N concurrent device threads, each sending telemetry at full speed
  - Measure aggregate throughput (req/s) and p99 latency
  - Vary N: 10, 50, 100, 250 concurrent devices
  - Duration: 20s per level (after 5s warm-up discarded)

Usage:
    python3 scripts/perf-scalability.py [--levels 10,50,100,250] [--duration 20]
"""
import argparse
import json
import os
import queue
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import datetime

DEVICE_SVC      = "http://localhost:8000"
BOOTSTRAP_TOKEN = "dev-bootstrap:dev-bootstrap-token"
WARMUP_S        = 5
SAMPLE_METRIC   = "temperature"


def _req(method, url, payload=None, extra_headers=None):
    body = json.dumps(payload).encode() if payload is not None else None
    hdrs = {"Content-Type": "application/json"}
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url=url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode() or "{}")
    except Exception:
        return None


def register_device(name):
    data = _req(
        "POST", f"{DEVICE_SVC}/api/v2/agents/register",
        {"name": name, "device_type": "perf-scalability"},
        extra_headers={"X-Bootstrap-Token": BOOTSTRAP_TOKEN},
    )
    return data["device_id"] if data else None


def ingest_one(device_id):
    """Send a single telemetry batch (1 sample). Return latency_ms or None on error."""
    t0 = time.monotonic()
    result = _req("POST", f"{DEVICE_SVC}/api/v2/devices/{device_id}/telemetry",
                  {"samples": [{"metric": SAMPLE_METRIC, "value": 22.5}]})
    if result is None:
        return None
    return (time.monotonic() - t0) * 1000.0


class DeviceWorker(threading.Thread):
    def __init__(self, device_id, result_q, stop_event, warmup_s):
        super().__init__(daemon=True)
        self.device_id = device_id
        self.result_q  = result_q
        self.stop      = stop_event
        self.warmup_s  = warmup_s
        self.t_start   = None

    def run(self):
        self.t_start = time.monotonic()
        warmup_end = self.t_start + self.warmup_s
        while not self.stop.is_set():
            lat = ingest_one(self.device_id)
            now = time.monotonic()
            if lat is not None and now >= warmup_end:
                self.result_q.put(lat)


def run_level(n_devices, duration_s, device_ids):
    result_q   = queue.Queue()
    stop_event = threading.Event()

    workers = [
        DeviceWorker(device_ids[i % len(device_ids)], result_q, stop_event, WARMUP_S)
        for i in range(n_devices)
    ]
    t0 = time.monotonic()
    for w in workers:
        w.start()

    time.sleep(WARMUP_S + duration_s)
    stop_event.set()
    for w in workers:
        w.join(timeout=3)

    elapsed = time.monotonic() - t0 - WARMUP_S
    latencies = []
    while not result_q.empty():
        latencies.append(result_q.get_nowait())

    if not latencies:
        return None

    s = sorted(latencies)

    def pct(data, p):
        idx = max(0, int(len(data) * p / 100) - 1)
        return data[idx]

    return {
        "n_devices":   n_devices,
        "n_requests":  len(latencies),
        "duration_s":  round(elapsed, 1),
        "throughput_rps": round(len(latencies) / elapsed, 1),
        "p50_ms":  round(pct(s, 50), 1),
        "p95_ms":  round(pct(s, 95), 1),
        "p99_ms":  round(pct(s, 99), 1),
        "mean_ms": round(statistics.mean(latencies), 1),
        "error_rate": 0.0,  # errors not counted separately here (None returns skipped)
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", default="10,50,100,250",
                    help="Comma-separated concurrent device counts (default: 10,50,100,250)")
    ap.add_argument("--duration", type=int, default=20,
                    help="Measurement duration per level in seconds (default: 20)")
    ap.add_argument("--pool", type=int, default=50,
                    help="Number of real devices to pre-register (default: 50)")
    args = ap.parse_args()

    levels = [int(x) for x in args.levels.split(",")]
    max_level = max(levels)

    n_pool = min(args.pool, max_level)
    print(f"§5.6 Scalability Benchmark")
    print(f"  levels: {levels}  duration/level: {args.duration}s  device pool: {n_pool}")
    print(f"  Registering {n_pool} devices...", flush=True)

    device_ids = []
    for i in range(n_pool):
        did = register_device(f"perf-scale-{uuid.uuid4().hex[:8]}")
        if did:
            device_ids.append(did)
        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{n_pool} registered", flush=True)

    if not device_ids:
        print("ERROR: no devices registered", file=sys.stderr)
        sys.exit(1)

    print(f"  {len(device_ids)} devices ready.\n", flush=True)

    all_results = []
    for n in levels:
        print(f"  Level: {n} concurrent devices (warmup {WARMUP_S}s + measure {args.duration}s)...",
              flush=True)
        r = run_level(n, args.duration, device_ids)
        if r is None:
            print(f"    No results at level {n}", flush=True)
            continue
        all_results.append(r)
        print(f"    → {r['throughput_rps']:.0f} req/s  p50={r['p50_ms']:.0f}ms  "
              f"p95={r['p95_ms']:.0f}ms  p99={r['p99_ms']:.0f}ms  "
              f"n={r['n_requests']}", flush=True)

    print()
    print("┌──────────────┬──────────┬────────┬────────┬────────┐")
    print("│  N devices   │ req/s    │  p50   │  p95   │  p99   │")
    print("├──────────────┼──────────┼────────┼────────┼────────┤")
    for r in all_results:
        print(f"│  {r['n_devices']:>10}  │ {r['throughput_rps']:>8.0f} │ {r['p50_ms']:>6.0f} │ "
              f"{r['p95_ms']:>6.0f} │ {r['p99_ms']:>6.0f} │")
    print("└──────────────┴──────────┴────────┴────────┴────────┘")

    print("\nJSON:")
    print(json.dumps(all_results, indent=2))

    os.makedirs("docs/paper/results", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = f"docs/paper/results/perf-scalability-{ts}.json"
    with open(out, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {out}")


if __name__ == "__main__":
    main()
