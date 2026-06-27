# Canary/Ring Rollout v1

## Status
Implemented in execution-service and validated with live API smoke test.

## New Endpoint
- `POST /api/v2/fleets/{fleet_id}/executions/rollout`

## Purpose
Roll out command/function executions across a fleet in progressive rings to reduce blast radius.

## Payload (v1)
- `execution_type` (`command` default, supports `function.install` and `function.invoke`)
- `command` (required for command rollouts)
- `plugin_id` (required for function rollouts)
- `args` (optional)
- `mode` (default `async`)
- `ring_size` (default `1`)
- `ring_sizes` (optional explicit list, overrides `ring_size`)
- `max_rings` (optional cap)
- `stop_on_failure` (default `true`)

## Response (v1)
- `rollout_id`
- `fleet_id`
- `planned_rings`, `completed_rings`
- `dispatched`, `failed`
- `status` (`rolling_out` or `stopped_on_failure`)
- `rings[]` with ring-level execution results

## Validation Evidence (Live)
Environment: local dev stack (`docker compose --profile dev`).

Executed flow:
1. Rebuilt and restarted execution-service with new code.
2. Created temporary fleet.
3. Added 3 real devices as members.
4. Called rollout endpoint with `ring_size=2`.

Observed result:
- `total=3`
- `planned_rings=2`
- `completed_rings=2`
- `dispatched=3`
- `failed=0`
- ring sizes returned: `[2, 1]`

## Notes
- v1 is synchronous ring progression in a single request.
- v1 does not yet include pause windows, health gates, or rollback automation.

## Next Iteration
- Add `pause_seconds_between_rings` + abort controls.
- Add health-gated progression (error budget/SLO checks).
- Add rollback policy and ring retry controls.
- Add UI rollout wizard and deployment timeline view.
