# Guardrails Policy Engine v1

## Status
Implemented in execution-service (create + dispatch enforcement).

## What It Does
- Blocks execution creation when policy denies command prefix.
- Blocks execution creation when policy denies execution type.
- Re-checks policy at dispatch time, so previously queued executions can still be blocked if policy changes.

## Configuration (Environment Variables)
- `GUARDRAILS_ENABLED` (default: `false`)
- `GUARDRAILS_DENY_COMMAND_PREFIXES` (csv, lowercase match on command prefix)
- `GUARDRAILS_BLOCKED_EXECUTION_TYPES` (csv, lowercase match)

Example:
```bash
GUARDRAILS_ENABLED=true
GUARDRAILS_DENY_COMMAND_PREFIXES=rm ,shutdown,reboot
GUARDRAILS_BLOCKED_EXECUTION_TYPES=function.invoke
```

## API Behavior
- Endpoint: `POST /api/v2/executions`
  - returns `403` when denied by guardrails policy
- Endpoint: `POST /api/v2/executions/{execution_id}/dispatch`
  - returns `403` when denied by guardrails policy

Response detail examples:
- `command blocked by policy (prefix 'rm ')`
- `execution type 'function.invoke' blocked by policy`

## Current Scope (v1)
- Prefix-based command deny list.
- Execution-type deny list.
- No per-tenant or per-device exceptions yet.

## Next Iteration (v1.1)
- Add allow-list mode and policy priority.
- Add per-tenant and per-device policy scopes.
- Add audit event reason codes for policy denials.
- Add UI policy management page.
