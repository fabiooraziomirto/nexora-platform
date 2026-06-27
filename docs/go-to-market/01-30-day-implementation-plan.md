# Nexora Go-To-Market 30-Day Implementation Plan

## Objective
Move from engineering-ready to startup-ready, with measurable pilot traction, repeatable onboarding, and low delivery risk.

## Success Criteria at Day 30
- Device onboarding median time <= 15 minutes
- End-to-end flow success rate >= 95% (pairing, execution, audit)
- P95 dispatch latency <= 2 seconds
- No open critical security findings
- 2 qualified design-partner opportunities in pipeline
- 1 live pilot negotiation with clear commercial scope
- Defined pricing hypothesis for Starter/Pro/Enterprise

## Strategic Track
- Startup product track reference: `docs/go-to-market/08-startup-product-track.md`
- Founder weekly board (4 settimane): `docs/go-to-market/09-founder-weekly-operating-board.md`
- Feature priority matrix (impatto/sforzo): `docs/go-to-market/10-feature-priority-matrix.md`

## Week 1 - Reliability Baseline
### Outcomes
- Stable baseline and reproducible tests for core flows.

### Tasks
- Run and stabilize full smoke and contract test suite.
- Define KPI queries and baseline report for onboarding, latency, success rate.
- Close all P0 and P1 defects impacting demo and onboarding.
- Freeze pilot MVP scope (top 3 use cases).

### Deliverables
- Baseline KPI report.
- Updated bug list with P0/P1 = 0.
- Signed-off pilot scope document.

### Execution Assets (Implemented)
- KPI collector script: `scripts/gtm-baseline-kpi.py`
- Baseline output artifact: `docs/go-to-market/baseline-kpi-latest.json`
- Week 1 baseline report: `docs/go-to-market/07-week1-baseline-report-2026-06-27.md`
- P0/P1 operational checklist: `docs/go-to-market/05-week1-p0-p1-checklist.md`
- 10-minute demo runbook: `docs/go-to-market/06-demo-flow-10-min-runbook.md`

### Week 1 Command Set
```bash
# Generate/update baseline KPI JSON (includes synthetic onboarding probe)
python3 scripts/gtm-baseline-kpi.py --out-json docs/go-to-market/baseline-kpi-latest.json

# Optional: collect only observed metrics (no synthetic announce/claim)
python3 scripts/gtm-baseline-kpi.py --skip-synthetic --out-json docs/go-to-market/baseline-kpi-latest.json

# End-to-end technical validation path for the demo environment
./scripts/nexora-device-emulator-e2e.sh
```

## Week 2 - Security and Tenant Safety
### Outcomes
- Pilot-safe controls for auth and tenant isolation.

### Tasks
- Validate tenant isolation with explicit negative tests.
- Disable development bypasses in pilot profile.
- Review token lifecycle, secret handling, and audit coverage.
- Produce one-page security summary for customer review.

### Deliverables
- Tenant isolation test evidence.
- Security one-pager.
- Pilot profile configuration checklist.

## Week 3 - Product UX and Packaging
### Outcomes
- Operator can complete first value flow without engineering help.

### Tasks
- Polish first-run flow: pair device, approve, execute command, verify output.
- Convert technical errors into operator-friendly messages.
- Finalize plan packaging: Starter, Pro, Enterprise (pilot mapped to one plan).
- Create and rehearse 10-minute live demo with fallback path.

### Deliverables
- First-value UX flow checklist.
- Pricing and packaging matrix.
- Demo script and talk track.

## Week 4 - Pilot Readiness and Selling Motion
### Outcomes
- Ready to run paid or structured pilot with clear support model.

### Tasks
- Target and qualify 5 prospects using scorecard.
- Prepare pilot SOW, onboarding plan, and support runbook.
- Execute two incident simulations and confirm runbook quality.
- Run final Go/No-Go review.

### Deliverables
- Prospect shortlist and qualification notes.
- Pilot execution pack.
- Go/No-Go decision document.

## Weekly Cadence
- Monday: plan and owner assignment.
- Wednesday: KPI checkpoint and risk burn-down.
- Friday: demo, status review, and scope adjustment.

## Risks and Mitigation
- Security gaps discovered late: run security checks in Week 2 only after Week 1 stabilization.
- Demo instability: keep a fixed demo environment and frozen dataset.
- Scope creep: enforce pilot MVP scope lock after Week 1.
