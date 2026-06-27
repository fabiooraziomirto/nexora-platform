# Runbook Automation v1

## Status
Implemented in execution-service and validated with live API smoke test.

## New Endpoint
- `POST /api/v2/runbooks/execute`

## Purpose
Execute ordered operational steps on a target device through the existing execution pipeline.

## Payload
- `name` (optional)
- `device_id` (required)
- `stop_on_failure` (default `true`)
- `steps` (required non-empty list)

Per-step fields:
- `name` (optional)
- `execution_type` (`command` default, supports `function.install`, `function.invoke`)
- `command` (required for command steps)
- `plugin_id` (required for function steps)
- `args` (optional)
- `mode` (default `async`)

## Response
- `runbook_id`
- `device_id`
- `total_steps`, `completed_steps`
- `dispatched`, `failed`
- `status` (`running` or `stopped_on_failure`)
- `results[]` with per-step execution IDs and status

## Validation Evidence (Live)
Environment: local dev stack (`docker compose --profile dev`).

Executed request:
- Name: `postalpha-smoke`
- Device: `bce0a818-15e0-455a-9306-54e96b08f097`
- Steps:
  1. `echo backup`
  2. `echo verify`

Observed response:
- `total_steps=2`
- `completed_steps=2`
- `dispatched=2`
- `failed=0`
- execution IDs returned for both steps

Execution list verification:
- `70cc8252-55ab-43f5-a505-92620c600eec` with command `echo backup` in `dispatched`
- `85bdfc9e-d1c0-4832-bfc2-6fc7c6809616` with command `echo verify` in `dispatched`

## Automated Tests Added
- `test_runbook_execute_success`
- `test_runbook_execute_requires_non_empty_steps`

## Next Iteration
- Add reusable runbook templates and catalog endpoint.
- Add conditional steps and retry policy per step.
- Add runbook execution timeline with audit correlation links.
- Add fleet-level runbook mode with ring-aware progression.
