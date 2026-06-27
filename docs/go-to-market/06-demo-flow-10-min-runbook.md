# Demo Flow Runbook (10 Minutes)

## Objective
Show clear customer value in one uninterrupted path:
- device pairing
- operator approval
- command execution
- audit visibility

## Preconditions
- Local stack up:
  - docker compose -f docker-compose.dev.yml --profile dev up -d --build
- Dashboard reachable at http://localhost:8080
- Device-side pairing UI reachable at http://localhost:8091

## Demo Script (Speaker + Action)

### Minute 0-1: Context
- Open Dashboard page.
- Explain: one control plane for device onboarding and remote execution.

### Minute 1-3: Device Requests Pairing
- Open http://localhost:8091
- Fill device fields or keep defaults.
- Click Request Pairing.
- Read out user_code to audience.

Expected result:
- discovery_id and user_code shown in device UI.

### Minute 3-5: Operator Approves
- Go to Dashboard -> Devices.
- In pending section, find hardware_id/user_code.
- Click Approve and set device name.

Expected result:
- Pending item disappears.
- New device appears in registered list.

### Minute 5-7: Execute a Command
- Go to Executions.
- Create a command for the approved device.
- Dispatch execution.

Expected result:
- Status transitions queued -> dispatched -> running -> succeeded.

### Minute 7-9: Show Evidence
- Open Dashboard charts and point to status updates.
- Open Audit page and show corresponding events.

Expected result:
- Action trace available in audit stream.

### Minute 9-10: Commercial Close
- Recap quantified outcomes: onboarding speed, execution reliability, auditability.
- Propose pilot success criteria and timeline.

## Fallback Path
- If UI issue occurs, run API checks:
  - curl -sS http://localhost:8080/api/v2/devices/pending
  - curl -sS 'http://localhost:8080/api/v2/executions?page=1&page_size=20'
  - curl -sS 'http://localhost:8080/api/v2/audit/events?page=1&page_size=20'

## Post-Demo Capture
- Record blockers and objections.
- Score prospect using scorecard.
- Send pilot next-step email within 24h.
