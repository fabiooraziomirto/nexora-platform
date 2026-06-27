#!/usr/bin/env python3
"""Week-1 GTM baseline KPI collector.

Collects pilot readiness KPIs from local Nexora APIs and optionally runs a
synthetic onboarding cycle (announce -> claim -> poll approved).

Usage:
  python3 scripts/gtm-baseline-kpi.py
  python3 scripts/gtm-baseline-kpi.py --out-json docs/go-to-market/baseline-kpi-latest.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from uuid import uuid4


def _http_json(method: str, url: str, payload: dict | None = None) -> dict | list:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, method=method, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = int((len(values) - 1) * q)
    return values[idx]


def synthetic_onboarding(device_base: str) -> dict:
    hw = f"gtm-kpi-{uuid4().hex[:10]}"
    announce_start = time.perf_counter()
    announce = _http_json(
        "POST",
        f"{device_base}/api/v2/devices/announce",
        {
            "hardware_id": hw,
            "device_type": "nexoraedge-emulator",
            "firmware_version": "1.0.0",
        },
    )
    discovery_id = announce["discovery_id"]
    device_code = announce["device_code"]

    _http_json(
        "POST",
        f"{device_base}/api/v2/devices/{discovery_id}/claim",
        {"name": f"kpi-{hw[-6:]}"},
    )

    encoded = urllib.parse.quote(device_code, safe="")
    poll = _http_json("GET", f"{device_base}/api/v2/devices/announce/poll?device_code={encoded}")
    elapsed_ms = (time.perf_counter() - announce_start) * 1000.0
    return {
        "hardware_id": hw,
        "status": poll.get("status", "unknown"),
        "elapsed_ms": round(elapsed_ms, 2),
        "approved": poll.get("status") == "approved",
    }


def collect(device_base: str, exec_base: str, include_synthetic: bool) -> dict:
    devices_resp = _http_json("GET", f"{device_base}/api/v2/devices?page=1&page_size=200")
    pending_resp = _http_json("GET", f"{device_base}/api/v2/devices/pending")
    exec_resp = _http_json("GET", f"{exec_base}/api/v2/executions?page=1&page_size=200")

    devices = devices_resp.get("items", [])
    pending = pending_resp if isinstance(pending_resp, list) else []
    executions = exec_resp.get("items", [])

    online = sum(1 for d in devices if d.get("status") == "online")
    offline = sum(1 for d in devices if d.get("status") == "offline")
    unknown = sum(1 for d in devices if d.get("status") == "unknown")

    terminal = [e for e in executions if e.get("status") in {"succeeded", "failed", "timeout", "cancelled"}]
    succeeded = sum(1 for e in terminal if e.get("status") == "succeeded")
    success_rate = (succeeded / len(terminal) * 100.0) if terminal else 0.0

    dispatch_ms = [
        float(e.get("dispatch_latency_seconds", 0.0)) * 1000.0
        for e in executions
        if e.get("dispatch_latency_seconds") is not None
    ]

    now = datetime.now(timezone.utc)
    pending_age_sec = []
    for p in pending:
        ts_raw = p.get("announced_at")
        if not ts_raw:
            continue
        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        pending_age_sec.append(max(0.0, (now - ts).total_seconds()))

    out = {
        "timestamp_utc": now.isoformat(),
        "kpis": {
            "registered_devices": len(devices),
            "online_devices": online,
            "offline_devices": offline,
            "unknown_devices": unknown,
            "pending_pairings": len(pending),
            "executions_sampled": len(executions),
            "terminal_executions": len(terminal),
            "execution_success_rate_percent": round(success_rate, 2),
            "dispatch_latency_p95_ms": round(_quantile(dispatch_ms, 0.95), 2),
            "dispatch_latency_p50_ms": round(_quantile(dispatch_ms, 0.50), 2),
            "pending_age_p50_seconds": round(_quantile(pending_age_sec, 0.50), 2),
        },
    }

    if include_synthetic:
        try:
            out["synthetic_onboarding"] = synthetic_onboarding(device_base)
        except Exception as exc:
            out["synthetic_onboarding"] = {
                "approved": False,
                "status": "error",
                "error": str(exc),
            }

    return out


def print_summary(report: dict) -> None:
    k = report["kpis"]
    print("Nexora GTM Baseline KPI")
    print("=======================")
    print(f"timestamp_utc:               {report['timestamp_utc']}")
    print(f"registered_devices:          {k['registered_devices']}")
    print(f"online/offline/unknown:      {k['online_devices']}/{k['offline_devices']}/{k['unknown_devices']}")
    print(f"pending_pairings:            {k['pending_pairings']}")
    print(f"execution_success_rate_%:    {k['execution_success_rate_percent']}")
    print(f"dispatch_latency_p50_ms:     {k['dispatch_latency_p50_ms']}")
    print(f"dispatch_latency_p95_ms:     {k['dispatch_latency_p95_ms']}")
    print(f"pending_age_p50_seconds:     {k['pending_age_p50_seconds']}")
    if "synthetic_onboarding" in report:
        s = report["synthetic_onboarding"]
        print(f"synthetic_onboarding_status: {s.get('status')}")
        if "elapsed_ms" in s:
            print(f"synthetic_onboarding_ms:     {s.get('elapsed_ms')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Week-1 GTM KPI baseline")
    parser.add_argument("--device-url", default="http://localhost:8000")
    parser.add_argument("--execution-url", default="http://localhost:8002")
    parser.add_argument("--skip-synthetic", action="store_true")
    parser.add_argument("--out-json", default="")
    args = parser.parse_args()

    report = collect(args.device_url.rstrip("/"), args.execution_url.rstrip("/"), not args.skip_synthetic)
    print_summary(report)

    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nSaved: {args.out_json}")


if __name__ == "__main__":
    main()
