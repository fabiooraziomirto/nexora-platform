# SLO Assistant v1

## Status
Implemented in device-service and validated with live API smoke tests.

## New Endpoint
- `GET /api/v2/devices/{device_id}/slos/assistant`

## Purpose
Provide actionable reliability guidance from recent SLO violations so operators can prioritize remediation without deep troubleshooting expertise.

## Query Parameters
- `hours` (default 24, min 1, max 720): time window for violation analysis
- `limit` (default 200, min 1, max 2000): max violations inspected

## Response
- `device_id`
- `hours`
- `total_violations`
- `status`:
  - `healthy` when no recent violations
  - `attention_required` when violations exist
- `top_metrics[]`:
  - `metric`
  - `violations`
  - `latest_observed_value`
  - `threshold`
  - `operator`
  - `severity` (`low`/`medium`/`high`)
  - `recommendation`
- `recommendations[]`: plain-language action hints
- `suggested_runbook_steps[]`: runbook-friendly command steps

## Validation Evidence (Live)
Environment: local dev stack (`docker compose --profile dev`).

Violation scenario:
- Device: `cb55c22c-7c73-4ace-a221-04c8eb60492d`
- SLO: `temperature lt 30`
- Samples: `35`, `36`

Observed output:
- `/slos/violations` returned 2 violations for metric `temperature`
- `/slos/assistant?hours=24` returned:
  - `status=attention_required`
  - `total_violations=2`
  - one top metric (`temperature`) with `severity=medium`
  - actionable recommendation and runbook steps (`diagnose-temperature`, `verify-slo-stability`)

Healthy scenario:
- Device: `6e780439-4f54-45b5-bdb1-22926af1a900`
- SLO: `temperature lt 30`
- Sample: `25`

Observed output:
- `/slos/assistant?hours=24` returned:
  - `status=healthy`
  - `total_violations=0`
  - no top metrics
  - no-action recommendation (`Keep current thresholds and monitor trend weekly`)

## Automated Tests Added
- `test_slo_assistant_returns_recommendations`
- `test_slo_assistant_healthy_without_violations`

## Bugfix Included During Validation
- Telemetry ingest now commits generated SLO violations after evaluation.
- This ensures `/slos/violations` and `/slos/assistant` are consistent across requests.

## Next Iteration
- Add trend-aware recommendations using violation rates and recovery windows.
- Add per-metric remediation templates (network, CPU, memory, thermal).
- Add endpoint support for fleet-wide SLO assistant summaries.
- Add UI card in device details with one-click runbook execution.
