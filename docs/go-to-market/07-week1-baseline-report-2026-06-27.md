# Week 1 Baseline Report - 2026-06-27

## Scope
Operational baseline after end-to-end demo validation and synthetic onboarding check.

## Evidence Executed
- E2E script: `scripts/nexora-device-emulator-e2e.sh`
- KPI collector: `scripts/gtm-baseline-kpi.py --out-json docs/go-to-market/baseline-kpi-latest.json`
- Dispatch round-trip benchmark: `python3 scripts/perf-dispatch-roundtrip.py --n-runs 10`

## KPI Snapshot
Source: `docs/go-to-market/baseline-kpi-latest.json`

- timestamp_utc: 2026-06-27T14:45:50.295881+00:00
- registered_devices: 3
- online_devices: 0
- offline_devices: 3
- pending_pairings: 0
- executions_sampled: 2
- terminal_executions: 2
- execution_success_rate_percent: 100.0
- dispatch_latency_p50_ms: 0.0
- dispatch_latency_p95_ms: 0.0
- synthetic_onboarding_status: approved
- synthetic_onboarding_elapsed_ms: 62.36

## Dispatch Latency Baseline (Second Pass)
Source: `docs/paper/results/perf-dispatch-kafka-20260627_170025.json`

- dispatch_latency_ms: p50=1503.4, p95=1504.3, p99=1504.3, stdev=1.7, n=10
- kafka_ingestion_ms: p50=1.2, p95=1.7, p99=1.7, stdev=1.2, n=10
- queue_wait_ms: p50=1502.1, p95=1503.0, p99=1503.0, stdev=0.6, n=10
- timeouts: 0

## Dispatch Latency Confidence Run (Third Pass)
Source: `docs/paper/results/perf-dispatch-kafka-20260627_170232.json`

- dispatch_latency_ms: p50=1503.6, p95=1504.6, p99=1504.6, stdev=366.3, n=30
- kafka_ingestion_ms: p50=1.3, p95=1.5, p99=1.6, stdev=0.2, n=30
- queue_wait_ms: p50=1502.3, p95=1503.1, p99=1503.3, stdev=366.2, n=30
- timeouts: 0
- notable outlier: max dispatch_latency_ms=3509.7 (single spike), while p95 remained ~1.5s

## n=10 vs n=30 Comparison (Dispatch E2E)
- p50: 1503.4 ms -> 1503.6 ms
- p95: 1504.3 ms -> 1504.6 ms
- p99: 1504.3 ms -> 1504.6 ms
- stability note: percentile band is stable, but mean/stdev increased due to one long-tail spike.

## E2E Outcome
- Result: PASSED (10/10 steps)
- Validated chain: registration -> plugin activation -> function install -> function invoke -> network attach -> webservice register

## Commercial Readout
- Demo readiness: Green
- Onboarding readiness: Green
- Reliability signal: Good (all sampled terminal executions succeeded)

## Week 1 Actions (Next 48h)
- Keep checklist `05-week1-p0-p1-checklist.md` at zero-open and review new blockers daily.
- Execute one dry-run of the 10-minute demo using `06-demo-flow-10-min-runbook.md` with sales observer.
- Investigate and mitigate long-tail dispatch spike (max 3509.7 ms) with targeted tracing on gateway queue wait path.

## Delta Update (Same Day)
- P1-01 closed: explicit permission hints added for disabled write actions in UI pages `Devices` and `Executions`.
