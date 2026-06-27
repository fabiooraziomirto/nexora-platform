# Investor Evidence Pack

## Purpose
Package Nexora for pre-seed conversations and paid-pilot conversion. The pack should prove that the product is not only technically broad, but demoable, measurable, and commercially focused.

## One-Sentence Positioning
Nexora is a control plane for regulated edge and IoT operations: onboard, govern, and execute actions on distributed fleets with audit, guardrails, and rollout control.

## Included Artifacts
- Architecture one-pager: `docs/go-to-market/19-architecture-one-pager.md`
- Security/RBAC one-pager: `docs/go-to-market/20-security-rbac-one-pager.md`
- Pilot SOW template: `docs/go-to-market/21-paid-pilot-sow-template.md`
- Demo reliability gate: `scripts/demo-reliability-gate.sh`
- KPI baseline: `docs/go-to-market/baseline-kpi-latest.json`
- Demo runbook: `docs/go-to-market/06-demo-flow-10-min-runbook.md`

## Investor Narrative
- Problem: edge operations are fragmented, manual, and hard to audit.
- Why now: edge fleets are becoming production-critical and regulated buyers need governance.
- Solution: Nexora unifies pairing, execution, fleet health, audit, SSO/RBAC, and AI/SLO assistance.
- Evidence: repeatable local stack, Keycloak login, audited execution flow, benchmarked dispatch path.
- Commercial wedge: paid 30-day pilot for audited remote execution on 10-25 devices.

## Metrics to Refresh Before Every Pitch
- Container health startup success.
- Synthetic onboarding elapsed time.
- Execution success rate.
- Dispatch latency p95.
- Audit evidence completeness.
- Number of discovery calls, demos, pilot conversations, and signed pilots.

## Red Flags to Avoid
- Pitching Nexora as a generic IoT platform.
- Showing more features than the buyer can remember.
- Running a live demo without the reliability gate first.
- Offering unpaid PoCs before testing willingness to pay.
