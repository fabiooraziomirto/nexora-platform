![Nexora Logo](nexora.png)

# Nexora

Nexora is a cloud-native IoT platform: microservice-first, Docker/Kubernetes native, event-driven, and designed to preserve OpenStack interoperability where needed.

This README is intentionally detailed to support handover and onboarding of external contributors without prior project context.

## 1) Mission and Scope

- Build a modular IoT control platform that can run independently or integrate with OpenStack ecosystems.
- Replace tightly coupled legacy patterns with service boundaries, explicit contracts, local quality gates, and operational runbooks.
- Keep an architecture that is evolvable: every major capability should be implementable as an adapter or independent service.

## 1.1) Research Contributions

Nexora is also the reference implementation for an academic systems paper
(see [`docs/paper/`](docs/paper/)). Its scientific contributions are:

- **C1 — Inline SLO enforcement.** Per-device service-level objectives are
  evaluated *synchronously on the telemetry-ingest path* and violations are
  persisted atomically as first-class, queryable records (not out-of-band
  alerts). See `services/device-service` and [ADR-0004](docs/adr/).
- **C2 — Reliable edge dispatch.** An explicit execution state machine
  (`queued → dispatched → running → succeeded/failed/timeout/cancelled`) plus a
  Kafka-driven, Redis-backed edge gateway (`nexora-edge`) giving bounded-retry,
  at-least-once command delivery with full latency instrumentation. See
  [ADR-0001](docs/adr/).
- **C3 — Privacy-aware multi-tenancy.** OIDC-based authorization with
  payload masking by tenant/role. See [ADR-0004](docs/adr/).

Edge FaaS (WASM/WASI via `nexora-function-runtime`, [ADR-0005](docs/adr/)) and
declarative infrastructure (Crossplane) are positioned as future work. The
paper draft, related-work comparison, and reproducible benchmark harness live
under [`docs/paper/`](docs/paper/) and [`scripts/perf-eval.py`](scripts/perf-eval.py).

## 2) Current Maturity

- Version: `Nexora`
- Runtime: `Python 3.11+`, `FastAPI`, `Docker Compose`, `Kubernetes`
- Core posture: DB-backed services, health/readiness/metrics endpoints, event contracts, and deployment manifests.
- OpenStack posture: adapter and integration scaffolding present; full production parity with the original legacy platform still requires iterative hardening.

## 3) System Architecture

### Logical View

```mermaid
flowchart LR
    Client[Clients / Operators] --> Gateway[API Gateway]
    Gateway --> Device[device-service]
    Gateway --> Module[module-service]
    Gateway --> Execution[execution-service]
    Gateway --> Network[network-service]
    Gateway --> DNS[dns-service]
    Gateway --> Webservice[webservice-service]
    Gateway --> Fleet[fleet-service]

    Execution -->|dispatch events| Kafka[(Kafka)]
    Kafka -->|consume| LRGateway[edge-gateway]
    LRGateway -->|deliver| Agent[Edge Agent / LR]
    Agent -->|callback| Execution

    Device --> MySQL[(MySQL)]
    Module --> MySQL
    Execution --> MySQL
    Network --> MySQL
    DNS --> MySQL
    Webservice --> MySQL
    Fleet --> MySQL

    Device --> Kafka
    Execution --> Kafka

    Device --> Redis[(Redis)]
```

> **Legacy Edge Agent Parity**: This architecture provides functional equivalence with the legacy control stack. The same operational concepts (board registration, heartbeat, remote command dispatch, result callback) are implemented using HTTP REST APIs and Apache Kafka instead of WAMP/Crossbar.io.

### Complete Architecture (Control + Edge + Ops)

```mermaid
flowchart TB
    %% Users and entrypoints
    subgraph Users["Users and Access"]
      Operator["Operator / Admin"]
      LegacyUser["Legacy Horizon User"]
    end

    subgraph UX["User Experience Layer"]
      Dashboard["dashboard-ui (React + FastAPI)"]
    end

    subgraph Identity["Identity and Access"]
      Keycloak["Keycloak (OIDC)"]
      Rbac["RBAC policy checks"]
    end

    subgraph Control["Control Plane Services"]
      Device["device-service"]
      Module["module-service"]
      Execution["execution-service"]
      Network["network-service"]
      Dns["dns-service"]
      Webservice["webservice-service"]
      Fleet["fleet-service"]
      Gateway["edge-gateway"]
      Runtime["nexora-module-runtime"]
    end

    subgraph Data["Data and Event Backbone"]
      Mysql["MySQL"]
      Redis["Redis"]
      Kafka["Kafka"]
      Zk["Zookeeper"]
    end

    subgraph Edge["Edge Plane"]
      Node1["edge-node-1"]
      Node2["edge-node-2"]
      ReverseTunnel["Reverse tunnel metadata / keepalive"]
      Ssh["SSH access channel (WebSocket bridge)"]
    end

    subgraph AI["Local AI Assistance"]
      Ollama["Ollama local endpoint"]
    end

    subgraph Ops["Observability and Operations"]
      Metrics["/metrics endpoints"]
      Health["/health and /ready"]
      Scripts["scripts/test-all.sh + runbooks"]
    end

    %% Access and auth
    Operator --> Dashboard
    LegacyUser --> LegacyAdapter
    Dashboard --> Keycloak
    LegacyAdapter --> Keycloak
    Dashboard --> Rbac

    %% UI to services
    Dashboard --> Device
    Dashboard --> Module
    Dashboard --> Execution
    Dashboard --> Network
    Dashboard --> Dns
    Dashboard --> Webservice
    Dashboard --> Fleet
    Dashboard --> Gateway
    Dashboard --> Runtime
    Dashboard --> Ollama

    %% Service internals
    Device --> Mysql
    Module --> Mysql
    Execution --> Mysql
    Network --> Mysql
    Dns --> Mysql
    Webservice --> Mysql
    Fleet --> Mysql
    Device --> Redis
    Execution --> Kafka
    Device --> Kafka
    Kafka --> Gateway
    Kafka --> Zk

    %% Edge interactions
    Gateway --> Node1
    Gateway --> Node2
    Node1 --> ReverseTunnel
    Node2 --> ReverseTunnel
    Dashboard --> Ssh
    Ssh --> Node1
    Ssh --> Node2
    Runtime --> Node1
    Runtime --> Node2

    %% Ops
    Device --> Metrics
    Module --> Metrics
    Execution --> Metrics
    Network --> Metrics
    Dns --> Metrics
    Webservice --> Metrics
    Fleet --> Metrics
    Gateway --> Metrics
    Runtime --> Metrics
    Device --> Health
    Module --> Health
    Execution --> Health
    Scripts --> Dashboard
    Scripts --> Execution
    Scripts --> Gateway
```

### Runtime Topology (Local)

- `device-service` -> `http://localhost:8000` (CRUD + agent register/heartbeat)
- `module-service` (plugin-compatible API) -> `http://localhost:8001`
- `execution-service` -> `http://localhost:8002` (command pipeline: queued→dispatched→running→succeeded/failed/timeout)
- `network-service` -> `http://localhost:8003`
- `dns-service` -> `http://localhost:8004`
- `webservice-service` -> `http://localhost:8005`
- `fleet-service` -> `http://localhost:8006`
- `edge-gateway` -> `http://localhost:8007` (Kafka consumer, agent sessions, delivery)
- `nexora-module-runtime` -> `http://localhost:8010` (WASM/WASI execution daemon on board path)
- `mysql` -> `localhost:3306`
- `redis` -> `localhost:6379`
- `kafka` -> `localhost:9092`
- `zookeeper` -> `localhost:2181`

### Request-to-Event Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant G as API Gateway
    participant S as Service
    participant DB as MySQL
    participant K as Kafka

    C->>G: POST /api/v2/<resource>
    G->>S: Forward request
    S->>DB: Persist transaction
    DB-->>S: Commit OK
    S->>K: Publish ResourceEvent(created)
    S-->>G: 201 + payload
    G-->>C: 201 Created
```

## 4) Service Catalog

### Core Services

- `device-service`: device inventory and lifecycle primitives.
- `module-service` (`plugin-service` compatibility name): module metadata lifecycle.
- `execution-service`: command/execution orchestration primitives.
- `network-service`: network port abstractions.
- `dns-service`: DNS record lifecycle.
- `webservice-service`: endpoint publication metadata.
- `fleet-service`: grouping and fleet metadata.

### Shared Libraries

- `libraries/common`: configuration, DB helpers, events, metrics, logging, auth/policy adapters, OpenStack adapters.
- `libraries/sdk`: client-side SDK primitives (REST + evolving gRPC support).

### Platform Assets

- `infrastructure/kubernetes`: deployment manifests, monitoring, policy, gateway, mesh, secrets, progressive rollout assets.
- `scripts`: setup/testing/operations automation.

## 5) API Contract Baseline

All core services expose:

- `GET /health`
- `GET /ready`
- `GET /metrics`

CRUD baseline endpoints:

- `module-service`: `POST/GET/DELETE /api/v2/modules` (legacy `/api/v2/plugins` still supported)
## 5.1) Direct Board Access and Module Runtime

- Direct board access intents are exposed by dashboard backend:
  - `POST /api/boards/{board_id}/access-intent`
  - `GET /api/boards/{board_id}/access-status`
  - `GET /api/access/audit`
- Module runtime orchestration endpoints:
  - `POST /api/modules/run`
  - `GET/POST/DELETE /api/modules/assignments`
  - `GET /api/modules/boards/{board_id}/status`
- Module Studio endpoints:
  - `GET /api/modules/studio`
  - `POST /api/modules/studio/drafts`
  - `POST /api/modules/studio/drafts/{draft_id}/publish`
- Automation and alerts endpoints:
  - `GET/POST/DELETE /api/automation/rules`
  - `GET/POST /api/alerts/rules`
  - `GET /api/alerts/events`
- Feature flags:
  - `NEXORA_MODULES_ENABLED`
  - `NEXORA_DEVICE_ACCESS_ENABLED`
  - `NEXORA_WASM_RUNTIME_ENABLED`
- `execution-service`: `POST/GET/DELETE /api/v2/executions`
- `network-service`: `POST/GET/DELETE /api/v2/ports`
- `dns-service`: `POST/GET/DELETE /api/v2/dns/records`
- `webservice-service`: `POST/GET/DELETE /api/v2/webservices`
- `fleet-service`: `POST/GET/DELETE /api/v2/fleets`

## 6) Data, Events, and Reliability

### Persistence

- Core services run MySQL-backed in Docker/K8s environments.
- Local fallback paths may use SQLite for fast testing.

### Eventing

- Shared event contract in `libraries/common/src/common/events/contracts.py`.
- Contract includes `event_type`, `service`, `resource`, `action`, `resource_id`, `payload`, `occurred_at`.
- Publish retry and structured logging are present on core publishers.

### Reliability Building Blocks

- Idempotency, outbox, and DLQ primitives exist in `libraries/common/src/common/events`.
- Replay tooling exists in `scripts/event-replay.py`.
- Runtime hardening should continue by wiring these primitives into all write/event paths.

## 7) Auth, Policy, and OpenStack Interop

### Current Auth Baseline

- Bearer middleware in core services.
- Dev token fallback is available for local workflows.
- JWT payload checks and write-role guardrail implemented.

### Shared Auth/Policy Modules

- `libraries/common/src/common/auth/oidc.py`
- `libraries/common/src/common/auth/policy_engine.py`

### OpenStack Adapter Layer

- `libraries/common/src/common/openstack/keystone_adapter.py`
- `libraries/common/src/common/openstack/neutron_adapter.py`
- `libraries/common/src/common/openstack/nova_adapter.py`
- `libraries/common/src/common/openstack/glance_cinder_adapter.py`

These adapters provide interoperability hooks while preserving service modularity.

## 8) Local Development Guide

### Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Optional: Poetry, `hey`, kubectl

### Start Stack

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

### Smoke Check

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8001/health
curl -fsS http://localhost:8002/health
curl -fsS http://localhost:8003/health
curl -fsS http://localhost:8004/health
curl -fsS http://localhost:8005/health
curl -fsS http://localhost:8006/health
```

### Stop/Clean

```bash
docker compose -f docker-compose.dev.yml down -v
```

## 9) Validation and Test Entry Points

### Primary Validation Scripts

- Full local baseline: `scripts/test-all.sh`
- Cross-service flow: `scripts/integration-cross-service.sh`
- API contract checks: `scripts/contract-tests-api.py`
- Post-alpha suite: `scripts/postalpha-validation.sh`
- Chaos drill: `scripts/chaos-drill.sh`
- Backup/restore validation: `scripts/backup-restore-validate.sh`
- Performance baseline: `scripts/perf-baseline.sh`
- Load catalog: `scripts/load-profile-catalog.sh`
- DR game day: `scripts/dr-gameday.sh`

### Recommended Validation Sequence (Local)

1. `docker compose -f docker-compose.dev.yml up -d --build`
2. `bash scripts/test-all.sh`
3. `bash scripts/postalpha-validation.sh`
4. targeted script(s) for the component you changed

## 10) Local Validation and Release Discipline

This repository currently uses local validation only (no active CI/CD pipeline in-hosted repository).

Recommended release discipline:

- run service unit tests (`pytest`) for touched services
- run `scripts/test-all.sh` and `scripts/postalpha-validation.sh`
- run targeted integration scripts for changed paths
- tag only after local validation is green
- complete and sign `docs/deployment/go-live-checklist.md`

## 11) Kubernetes/Platform Assets

### Key Areas

- Gateway routing/rate limits: `infrastructure/kubernetes/kong`
- Monitoring/alerts/SLO rules: `infrastructure/kubernetes/monitoring`
- Mesh mTLS baseline: `infrastructure/kubernetes/mesh/istio-mtls.yaml`
- External secrets baseline: `infrastructure/kubernetes/secrets/external-secrets.yaml`
- Policy enforcement baseline: `infrastructure/kubernetes/policies/kyverno-security.yaml`
- Progressive delivery baseline: `infrastructure/kubernetes/progressive-delivery/rollout-device.yaml`
- Schema registry baseline: `infrastructure/kubernetes/kafka/schema-registry.yaml`

### Important Note

Some assets are intentionally baseline-level. They provide a concrete start, but each target environment should enforce stricter secrets, identities, network policies, and rollout criteria.

## 12) Troubleshooting Cheat Sheet

### Service Not Ready

1. Check `/health` then `/ready`.
2. Check MySQL/Kafka/Redis readiness.
3. Verify service logs with `x-trace-id` or `x-correlation-id`.

### Event Publish Missing

1. Verify Kafka connectivity and topic prefix env vars.
2. Confirm producer startup logs.
3. Inspect retry logs for publish failures.

### Migration Failures

1. Check `alembic current` and `alembic history`.
2. Validate DB URL and credentials.
3. Roll back controlled revision if needed, then re-run.

### CI Failures

1. Identify the failing local validation step.
2. Re-run equivalent local script.
3. Reproduce with same env vars/profile.

## 13) Operational Runbooks (Condensed)

### Incident Response

1. Triage impact by service and endpoint.
2. Validate dependencies first (DB/Kafka/Redis).
3. Isolate faulty change.
4. Restart/rollback narrowly.
5. Re-run smoke + integration + contract checks.

### Rollback

1. Select prior stable artifact.
2. Apply rollback via deployment channel.
3. Verify write/read paths and event pipeline.
4. Close only after post-rollback checks pass.

### DB Migration Failure

1. Freeze writes.
2. Inspect revision mismatch.
3. Controlled downgrade or restore path.
4. Re-test in staging before production retry.

## 14) Handover Guide for New Contributors

If you are picking up development from this repository:

1. Read sections 3, 8, 9, and 10 first.
2. Start stack locally and run `scripts/test-all.sh`.
3. Choose one service and trace its full path (API -> DB -> event publish).
4. When adding features:
   - update API contract and tests,
   - preserve observability headers/metrics,
   - keep changes backward-compatible where possible,
   - wire any new dependency into compose and CI.
5. Before pushing:
   - run local validation scripts relevant to your change,
   - record which checks you executed and their outcome.

## 15) Roadmap Reality and Gaps

This repository contains both production-facing implementations and baseline/scaffolding assets.  
When planning next iterations, classify each item as:

- `runtime-wired`: actively used by services in production path
- `platform-baseline`: deployable infra primitive not fully wired end-to-end
- `governance-baseline`: policy/process/workflow ready, needing environment secrets and rollout hardening

This classification prevents “false done” and helps prioritize what still needs runtime closure.

## 16) Security Notes

- Never commit secrets in repository files.
- Prefer secret stores and runtime injection.
- Keep dependencies and images patched.
- Treat CI security scans as release gates.

## 17) License

Apache License 2.0

