# Drift Detection v1

## Status
Implemented in execution-service and validated with live API smoke tests.

## New Endpoint
- `POST /api/v2/drift/analyze`

## Purpose
Detect runtime drift between expected plugin installs and observed execution history on device/fleet scope.

## Request
One target selector is required:
- `fleet_id` OR
- `device_ids` (non-empty list)

Expected baseline:
- `expected_plugins` (non-empty list)
  - supports string form: `"plugin-id"`
  - supports object form:
    - `plugin_id` (required)
    - `max_last_install_age_hours` (optional)

## Response
- `total_devices`
- `devices_with_drift`
- `summary`:
  - `missing_installs`
  - `stale_installs`
  - `failed_latest_installs`
- `devices[]` with:
  - `drift_score` (0-100)
  - issue list (`missing_install`, `stale_install`, `latest_install_failed`)

## Scoring Model (v1)
- missing install: +60
- stale install: +25
- latest failed install: +20
- capped at 100

## Validation Evidence (Live)
Environment: local dev stack (`docker compose --profile dev`).

Success call:
- `fleet_id = e414c09e-48c0-4c0b-9a7d-acffe53f62d1`
- `expected_plugins = ["1e9decba-7b51-48f6-a281-bc4a473ce72b"]`

Observed result:
- `total_devices=3`
- `devices_with_drift=3`
- `summary.missing_installs=3`
- each device returned with `missing_install` issue and drift score 60

Validation error call:
- missing both `fleet_id` and `device_ids`
- response detail: `provide fleet_id or non-empty device_ids`

## Automated Tests Added
- `test_drift_analyze_for_fleet`
- `test_drift_analyze_requires_target`

## Next Iteration
- Add baseline profiles persisted per fleet.
- Add comparison against plugin versions and capability expectations.
- Add drift trend history and remediation suggestions.
- Add UI page with filterable drift table and export.
