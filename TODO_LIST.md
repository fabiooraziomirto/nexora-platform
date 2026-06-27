# Nxr v2.0 — TODO e stato corrente

Legenda: `[ ]` da fare · `[~]` parziale · `[x]` completato e verificato

---

## Stato del repository (filesystem)

**Data controllo:** 2026-03-28 · **Path:** `/home/lucadag/nxr_v2.0`

> **Nota:** Parità funzionale vs IoTronic/Lightning Rod, **non** parità di
> protocollo WAMP.  I concetti sono mappati (board→device, session→agent,
> RPC call→execution dispatch/callback) usando HTTP REST + Apache Kafka.

### Servizi implementati

| Servizio | Porta | Stato | File chiave |
|----------|-------|-------|-------------|
| device-service | 8000 | [x] CRUD + agent register/heartbeat/bootstrap | `api/devices.py`, `schemas.py`, `device_service.py` |
| plugin-service | 8001 | [x] CRUD | `main.py` |
| execution-service | 8002 | [x] Pipeline completa (queued→dispatched→running→succeeded/failed/timeout/cancelled) | `main.py` |
| network-service | 8003 | [x] CRUD | `main.py` |
| dns-service | 8004 | [x] CRUD | `main.py` |
| webservice-service | 8005 | [x] CRUD | `main.py` |
| fleet-service | 8006 | [x] CRUD | `main.py` |
| nexora-edge | 8007 | [x] Kafka consumer, agent sessions, deliver+retry | `main.py` |

### Funzionalità execution-service

- [x] Idempotency key
- [x] Per-device queue limit (429)
- [x] State machine (transition validation, 409)
- [x] Dispatch endpoint (queued→dispatched + Kafka envelope)
- [x] Callback endpoint (strict field validation, running/succeeded/failed)
- [x] Cancel endpoint
- [x] Timeout background loop (dispatched/running → timeout)
- [x] Correlation ID + tenant ID
- [x] Audit logging

### Funzionalità device-service (IoTronic parity)

- [x] Agent register (`POST /agents/register`) — bootstrap token auth
- [x] Agent heartbeat (`POST /agents/{id}/heartbeat`) — liveness
- [x] Bootstrap token validation (id:secret:expiry, revocation list)
- [x] CRUD devices completo

### Funzionalità nexora-edge (Lightning Rod parity)

- [x] Kafka consumer su `nxr.execution.dispatched`
- [x] Agent session management (register, heartbeat, get)
- [x] Delivery with retry + backoff
- [x] Delivery failure → Kafka event `delivery_failed`
- [x] Prometheus metrics (sessions, pending, delivery attempts/failures)

---

## Script e strumenti

- [x] `scripts/test-all.sh` — test struttura + sintassi + compose smoke
- [x] `scripts/contract-tests-api.py` — positive + negative contract checks
- [x] `scripts/nexora-device-emulator-e2e.sh` — full lifecycle emulation
- [x] `scripts/replay_execution_outbox.py` — DLQ replay utility
- [x] `scripts/integration-cross-service.sh`

## Documentazione

- [x] `docs/deployment/nexora-parity-matrix.md` — concept mapping legacy→v2.0
- [x] `docs/deployment/execution-pipeline-runbook.md` — operator runbook
- [x] `docs/deployment/release-checklist-mvp.md`
- [x] `docs/adr/0001-nexoraedge-and-execution-pipeline.md`

## Infrastruttura

- [x] `infrastructure/sre/prometheus-rules-nxr.yaml` — alert rules
- [x] `docker-compose.dev.yml` — tutti gli 8 servizi + gateway

## Test unitari

- [x] `execution-service/tests/` — 9 test (CRUD, lifecycle, idempotency, 429, 409, timeout, cancel, unknown fields)
- [x] `device-service/tests/` — CRUD + 7 agent tests (register, heartbeat, token validation)

---

## Backlog rimanente

### Priorità alta

- [ ] Outbox pattern generalizzato su tutti i write path (non solo execution)
- [ ] OpenStack: test su cloud reale, mapping Keystone/tenant, pilot endpoint
- [ ] Sicurezza: authz uniforme Keycloak, mTLS service-to-service
- [ ] CI/CD: GitHub Actions pipeline per test + build + deploy

### Priorità media

- [ ] Test avanzati: chaos, load/soak, CI compose deterministico
- [ ] Profilo compatibilità mixed-deployment (legacy IoTronic + v2.0)
- [ ] Guide complete: rbac/keycloak/crossplane, plugin developer guide
- [ ] OpenAPI spec per tutti i servizi (solo plugin + execution presenti)
- [ ] Secret rotation runbook

### Priorità bassa

- [ ] Staging sign-off + tag RC
- [ ] Canary rollout playbook
- [ ] DR game-day + backup drill
- [ ] Elenco feature legacy esplicitamente droppate

---

## Milestones

- **M1** [x] Runtime LR + execution pipeline funzionante
- **M2** [~] Affidabilità + sicurezza (timeout/queue OK, mTLS/outbox da completare)
- **M3** [ ] OpenStack + governance

---

## Go-To-Market Execution (30 giorni)

- [x] Piano operativo 30 giorni: `docs/go-to-market/01-30-day-implementation-plan.md`
- [x] Template operativo settimanale: `docs/go-to-market/02-weekly-operating-template.md`
- [x] Pitch template 6 slide: `docs/go-to-market/03-pitch-6-slide-template.md`
- [x] Scorecard prospect: `docs/go-to-market/04-prospect-scorecard.md`
- [x] Checklist P0/P1 Week 1: `docs/go-to-market/05-week1-p0-p1-checklist.md`
- [x] Runbook demo 10 minuti: `docs/go-to-market/06-demo-flow-10-min-runbook.md`
- [x] Script KPI baseline + output iniziale: `scripts/gtm-baseline-kpi.py`, `docs/go-to-market/baseline-kpi-latest.json`
- [x] Report baseline Week 1 (2026-06-27): `docs/go-to-market/07-week1-baseline-report-2026-06-27.md`
- [x] Second baseline dispatch latency (real Kafka): `docs/paper/results/perf-dispatch-kafka-20260627_170025.json`
- [x] Confidence run dispatch latency n=30: `docs/paper/results/perf-dispatch-kafka-20260627_170232.json`
- [x] Startup product track (90 giorni): `docs/go-to-market/08-startup-product-track.md`
- [x] Founder weekly operating board (4 settimane): `docs/go-to-market/09-founder-weekly-operating-board.md`
- [x] Feature priority matrix (impatto/sforzo): `docs/go-to-market/10-feature-priority-matrix.md`
- [x] Guardrails Policy Engine v1 (execution-service): `docs/go-to-market/11-guardrails-policy-engine-v1.md`
- [x] Onboarding Wizard v1 (nexora-ui): `docs/go-to-market/12-onboarding-wizard-v1.md`
- [x] Canary/Ring Rollout v1 (execution-service): `docs/go-to-market/13-canary-ring-rollout-v1.md`
- [x] Runbook Automation v1 (execution-service): `docs/go-to-market/14-runbook-automation-v1.md`
- [x] Drift Detection v1 (execution-service): `docs/go-to-market/15-drift-detection-v1.md`
- [x] SLO Assistant v1 (device-service): `docs/go-to-market/16-slo-assistant-v1.md`
- [x] Plugin SBOM/Security Scan v1 (plugin-service): `docs/go-to-market/17-plugin-sbom-security-scan-v1.md`

---

*Aggiornato dopo implementazione e verifica su filesystem il 2026-03-28.*
