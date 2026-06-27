# Onboarding Wizard v1

## Status
Implemented in Nexora UI.

## Goal
Reduce time-to-first-value with a guided flow for first onboarding success.

## User Flow
1. Select pending discovery from queue.
2. Approve device with production-ready name.
3. Dispatch first command.
4. Verify execution reaches terminal status.
5. Jump to Devices, Executions, or Audit views.

## Implementation
- New page: `services/nexora-ui/src/pages/OnboardingWizard.tsx`
- Route: `/onboarding`
- Sidebar navigation entry: `Onboarding`
- API integration:
  - `listPendingDevices`
  - `claimPendingDevice`
  - `createExecution`
  - `dispatchExecution`
  - `getExecution` (new API client method)

## Acceptance Criteria
- Wizard page is reachable from sidebar and route `/onboarding`.
- Approval action creates a new device from pending discovery.
- First command can be dispatched from wizard.
- Execution status is polled and visible until terminal state.
- Read-only users see clear permission message and disabled actions.

## Verification Evidence
- Static/type validation: no editor errors in modified files.
- Build verification: `npm run build` succeeded in `services/nexora-ui`.

## Next Iteration
- Add optional auto-refresh for pending queue.
- Add action history timeline with audit correlation IDs.
- Add pre-flight checks (device online capability, command policy hints).
