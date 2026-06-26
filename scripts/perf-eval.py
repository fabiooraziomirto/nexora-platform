#!/usr/bin/env python3
"""Nexora Platform — Experimental Evaluation Benchmark (Paper §V).

Measures the three key performance indicators cited in the paper:
  1. Telemetry ingest latency (p50/p95/p99) under varying batch sizes
  2. SLO detection latency — time from ingest call to violation count in response
  3. Fleet analytics aggregation latency across fleet sizes (N=10, 50, 100 mock devices)

Usage (requires a running stack):
    python3 scripts/perf-eval.py [--base-url http://localhost:8000] [--fleet-url http://localhost:8006]

Output: JSON results to stdout + human-readable table to stderr.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from uuid import uuid4

import httpx

DEFAULT_DEVICE_URL = "http://localhost:8000"
DEFAULT_FLEET_URL = "http://localhost:8006"
RUNS_PER_SCENARIO = 30


async def create_device(client: httpx.AsyncClient, base: str, name: str) -> str:
    r = await client.post(f"{base}/api/v2/devices", json={"name": name, "device_type": "sensor"})
    r.raise_for_status()
    return r.json()["id"]


async def create_fleet(client: httpx.AsyncClient, fleet_url: str, name: str) -> str:
    r = await client.post(f"{fleet_url}/api/v2/fleets", json={"name": name})
    r.raise_for_status()
    return r.json()["id"]


async def add_member(client: httpx.AsyncClient, fleet_url: str, fleet_id: str, device_id: str):
    r = await client.post(f"{fleet_url}/api/v2/fleets/{fleet_id}/members", json={"device_id": device_id})
    r.raise_for_status()


async def bench_ingest_latency(base: str) -> dict:
    """Measure ingest latency for batch sizes 1, 10, 50, 100, 500."""
    results = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        device_id = await create_device(client, base, f"bench-ingest-{uuid4().hex[:8]}")
        for batch_size in [1, 10, 50, 100, 500]:
            samples = [{"metric": "temperature", "value": 22.0 + i * 0.1} for i in range(batch_size)]
            latencies = []
            for _ in range(RUNS_PER_SCENARIO):
                t0 = time.perf_counter()
                r = await client.post(
                    f"{base}/api/v2/devices/{device_id}/telemetry",
                    json={"samples": samples},
                )
                elapsed = (time.perf_counter() - t0) * 1000  # ms
                assert r.status_code == 202, f"Unexpected {r.status_code}: {r.text}"
                latencies.append(elapsed)
            latencies.sort()
            results[batch_size] = {
                "p50_ms": round(statistics.median(latencies), 2),
                "p95_ms": round(latencies[int(len(latencies) * 0.95)], 2),
                "p99_ms": round(latencies[int(len(latencies) * 0.99)], 2),
                "mean_ms": round(statistics.mean(latencies), 2),
                "runs": RUNS_PER_SCENARIO,
            }
    return results


async def bench_slo_detection_latency(base: str) -> dict:
    """Measure the overhead introduced by SLO evaluation during ingest.

    Compares ingest latency with 0 SLOs vs 1, 5, 10 enabled SLOs.
    The delta is the SLO evaluation overhead attributable to the engine.
    """
    results = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        device_id = await create_device(client, base, f"bench-slo-{uuid4().hex[:8]}")
        for n_slos in [0, 1, 5, 10]:
            # Create the SLOs
            for i in range(n_slos):
                await client.post(
                    f"{base}/api/v2/devices/{device_id}/slos",
                    json={"metric": f"metric_{i}", "operator": "lt", "threshold": 30.0},
                )
            samples = [{"metric": f"metric_{i}", "value": 35.0} for i in range(max(n_slos, 1))]
            latencies = []
            for _ in range(RUNS_PER_SCENARIO):
                t0 = time.perf_counter()
                r = await client.post(
                    f"{base}/api/v2/devices/{device_id}/telemetry",
                    json={"samples": samples},
                )
                elapsed = (time.perf_counter() - t0) * 1000
                assert r.status_code == 202
                latencies.append(elapsed)
            latencies.sort()
            results[n_slos] = {
                "p50_ms": round(statistics.median(latencies), 2),
                "p95_ms": round(latencies[int(len(latencies) * 0.95)], 2),
                "mean_ms": round(statistics.mean(latencies), 2),
                "violations_per_call": r.json()["violations"],
                "runs": RUNS_PER_SCENARIO,
            }
    return results


async def bench_fleet_analytics(base: str, fleet_url: str) -> dict:
    """Measure fleet health aggregation latency for fleet sizes 5, 20, 50."""
    results = {}
    async with httpx.AsyncClient(timeout=60.0) as client:
        for fleet_size in [5, 20, 50]:
            fleet_id = await create_fleet(client, fleet_url, f"bench-fleet-{fleet_size}-{uuid4().hex[:8]}")
            device_ids = []
            for i in range(fleet_size):
                did = await create_device(client, base, f"fleet-dev-{fleet_size}-{i}-{uuid4().hex[:6]}")
                device_ids.append(did)
                await add_member(client, fleet_url, fleet_id, did)

            latencies = []
            for _ in range(min(RUNS_PER_SCENARIO, 10)):  # fewer runs for large fleets
                t0 = time.perf_counter()
                r = await client.get(f"{fleet_url}/api/v2/fleets/{fleet_id}/health")
                elapsed = (time.perf_counter() - t0) * 1000
                assert r.status_code == 200
                latencies.append(elapsed)
            latencies.sort()
            n = len(latencies)
            results[fleet_size] = {
                "p50_ms": round(statistics.median(latencies), 2),
                "p95_ms": round(latencies[int(n * 0.95)], 2),
                "mean_ms": round(statistics.mean(latencies), 2),
                "fleet_size": fleet_size,
                "runs": n,
            }
    return results


def print_table(title: str, rows: list[tuple], headers: list[str]):
    col_w = [max(len(h), max(len(str(r[i])) for r in rows)) for i, h in enumerate(headers)]
    sep = "+-" + "-+-".join("-" * w for w in col_w) + "-+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_w) + " |"
    print(f"\n{title}", file=sys.stderr)
    print(sep, file=sys.stderr)
    print(fmt.format(*headers), file=sys.stderr)
    print(sep, file=sys.stderr)
    for row in rows:
        print(fmt.format(*[str(v) for v in row]), file=sys.stderr)
    print(sep, file=sys.stderr)


async def main():
    parser = argparse.ArgumentParser(description="Nexora Platform Performance Evaluation")
    parser.add_argument("--base-url", default=DEFAULT_DEVICE_URL)
    parser.add_argument("--fleet-url", default=DEFAULT_FLEET_URL)
    parser.add_argument("--skip-fleet", action="store_true", help="Skip fleet analytics bench (needs fleet-service)")
    args = parser.parse_args()

    print("Running Nexora Platform Evaluation Benchmark...", file=sys.stderr)
    print(f"  device-service: {args.base_url}", file=sys.stderr)
    print(f"  fleet-service:  {args.fleet_url}", file=sys.stderr)
    print(f"  runs per scenario: {RUNS_PER_SCENARIO}", file=sys.stderr)

    results = {}

    print("\n[1/3] Telemetry ingest latency...", file=sys.stderr)
    ingest = await bench_ingest_latency(args.base_url)
    results["telemetry_ingest_latency_ms"] = ingest
    print_table(
        "Telemetry Ingest Latency (ms)",
        [(bs, v["p50_ms"], v["p95_ms"], v["p99_ms"], v["mean_ms"]) for bs, v in ingest.items()],
        ["batch_size", "p50", "p95", "p99", "mean"],
    )

    print("\n[2/3] SLO detection overhead...", file=sys.stderr)
    slo = await bench_slo_detection_latency(args.base_url)
    results["slo_detection_overhead_ms"] = slo
    baseline = slo[0]["p50_ms"]
    print_table(
        "SLO Detection Overhead (ms, 1-sample ingest)",
        [(n, v["p50_ms"], v["p95_ms"], round(v["p50_ms"] - baseline, 2)) for n, v in slo.items()],
        ["n_slos", "p50", "p95", "overhead_vs_0slos"],
    )

    if not args.skip_fleet:
        print("\n[3/3] Fleet analytics aggregation latency...", file=sys.stderr)
        fleet = await bench_fleet_analytics(args.base_url, args.fleet_url)
        results["fleet_analytics_latency_ms"] = fleet
        print_table(
            "Fleet Health Aggregation Latency (ms)",
            [(fs, v["p50_ms"], v["p95_ms"], v["mean_ms"]) for fs, v in fleet.items()],
            ["fleet_size", "p50", "p95", "mean"],
        )
    else:
        print("\n[3/3] Fleet analytics bench skipped.", file=sys.stderr)

    print("\nJSON results:", file=sys.stderr)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
