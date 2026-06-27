# Security and RBAC One-Pager

## Security Story
Nexora is designed for operations teams that need controlled remote actions on distributed devices. The security posture focuses on identity, tenant-aware authorization, audit evidence, and operator-visible guardrails.

## Current Controls
- Keycloak OIDC login in the dev stack.
- Realm roles: `platform-admin`, `tenant-admin`, `operator`, `viewer`.
- UI write actions are role-aware.
- Backend services emit audit events for key resource changes and execution actions.
- Bootstrap token flow exists for agent/device registration.
- Execution service validates lifecycle transitions and rejects invalid state changes.

## Evidence for Buyers
- Login and tenant identity can be shown live in the dashboard.
- Audit page shows action, resource, actor, tenant, outcome, and timestamp.
- Audit evidence can be exported for procurement review.
- Runbook-backed demo proves an execution can be traced from request to terminal status.

## Paid Pilot Defaults
- Use Keycloak realm `nxr` for pilot access.
- Use separate tenant/group per customer pilot.
- Export audit bundle at weekly review.
- Do not run destructive commands in demo mode.

## Remaining Hardening Before Enterprise Sale
- Service-to-service mTLS.
- Advanced RBAC and four-eyes approvals.
- Central policy engine coverage across all write paths.
- Secret rotation runbook and production Keycloak configuration.
