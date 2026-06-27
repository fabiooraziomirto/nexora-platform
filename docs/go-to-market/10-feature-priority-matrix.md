# Feature Priority Matrix (Impact vs Effort)

## Objective
Prioritize software features that maximize pilot conversion, reduce operational risk, and improve expansion revenue.

## Scoring Model
- Impact: 1 (low) to 5 (very high)
- Effort: S (1 sprint), M (2-3 sprints), L (4+ sprints)
- Priority score: Impact x Weight
- Weight:
  - Revenue/Pilot conversion: 0.45
  - Risk reduction/procurement: 0.35
  - Retention/expansion: 0.20

## Priority Backlog (Top 8)
| Rank | Feature | Impact | Effort | Why now | Commercial effect | Suggested window |
|---|---|---:|---|---|---|---|
| 1 | Policy Engine Guardrails | 5 | M | Blocks fear of unsafe remote actions | Faster procurement, higher trust | 30 days |
| 2 | Onboarding Wizard (TTFV) | 5 | S | Improves demo to pilot conversion | More demos convert to pilots | 30 days |
| 3 | Canary/Ring Rollout | 5 | M | Safe progressive deploys | Pro/Enterprise upsell anchor | 30-60 days |
| 4 | Runbook Automation v1 | 4 | M | Turns platform into repeatable operations | Higher retention, lower toil | 30-60 days |
| 5 | Audit Evidence Export Bundle | 4 | S | Compliance-ready evidence for customers | Unlocks regulated buyers | 30 days |
| 6 | Drift Detection (config/version) | 4 | M | Detects silent config drift | Expands after pilot | 60 days |
| 7 | SLO Assistant (actionable alerts) | 3 | M | Ops guidance without deep expertise | Better reliability story | 60-90 days |
| 8 | RBAC Advanced + 4-eyes approvals | 5 | L | Enterprise hardening requirement | Enables larger contracts | 90 days |

## Build Sequence (30-60-90)
### 0-30 days
1. Onboarding Wizard (TTFV) - v1 implemented (`docs/go-to-market/12-onboarding-wizard-v1.md`)
2. Policy Engine Guardrails (core rules) - v1 implemented (`docs/go-to-market/11-guardrails-policy-engine-v1.md`)
3. Audit Evidence Export v1

### 31-60 days
1. Canary/Ring Rollout - v1 implemented (`docs/go-to-market/13-canary-ring-rollout-v1.md`)
2. Runbook Automation v1 - implemented (`docs/go-to-market/14-runbook-automation-v1.md`)
3. Drift Detection v1 - implemented (`docs/go-to-market/15-drift-detection-v1.md`)

### 61-90 days
1. SLO Assistant - v1 implemented (`docs/go-to-market/16-slo-assistant-v1.md`)
2. RBAC Advanced + 4-eyes approvals

## Sprint-Level Definition of Done
- Feature has API + UI + audit trail.
- Feature is covered by e2e path in demo runbook.
- Feature has one measurable KPI delta (conversion, reliability, or cycle time).
- Feature has packaging position (Starter/Pro/Enterprise).

## KPI Mapping
| Feature | KPI moved | Target delta |
|---|---|---|
| Onboarding Wizard | Time-to-first-value | <= 10 min median |
| Guardrails | Pilot risk incidents | 0 critical incidents |
| Canary Rollout | Failed deployments | -50% rollback events |
| Runbook Automation | Operator cycle time | -30% for repeated tasks |
| Audit Export | Procurement turnaround | -25% time to security review |
| Drift Detection | Configuration incidents | -40% drift-related tickets |
| SLO Assistant | Alert MTTR | -20% MTTR |
| RBAC Advanced | Enterprise objections | Remove top-3 security objections |

## Owner Template
- Product owner:
- Engineering owner:
- Target sprint:
- Risk:
- Dependency:
- Rollout plan:
