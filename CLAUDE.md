# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Nexora is a cloud-native IoT device management platform built as Python/FastAPI microservices. It is a rewrite/replacement of a legacy Nxr/OpenStack-based system, preserving wire compatibility with legacy clients where needed. All services are Docker/Kubernetes native.

## Commands

### Start the full stack locally
```bash
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml down -v   # teardown + volumes
```

### Run tests for a single service
```bash
cd services/<service-name>
PYTHONPATH=src pytest tests/
# Example with coverage:
PYTHONPATH=src pytest tests/ --cov=src --cov-report=term-missing
```

Tests use SQLite + `KAFKA_ENABLED=false` overrides — no running infrastructure needed for unit tests.

### Linting and formatting
```bash
black --line-length=100 .
ruff check . --fix
ruff format .
mypy .
bandit -r . -x tests/,alembic/
```

Pre-commit hooks run all of the above automatically on commit (configured in `.pre-commit-config.yaml`).

### Validation scripts (require running stack)
```bash
bash scripts/test-all.sh                    # full local baseline (structure + syntax + Docker smoke)
bash scripts/postalpha-validation.sh        # post-alpha checklist
bash scripts/integration-cross-service.sh   # cross-service flow
python3 scripts/contract-tests-api.py       # API contract assertions
bash scripts/nexora-device-emulator-e2e.sh             # NexoraEdge edge E2E
bash scripts/chaos-drill.sh                 # chaos/fault injection
bash scripts/perf-baseline.sh               # performance baseline
```

### DB migrations (per service)
```bash
cd services/<service-name>
alembic upgrade head
alembic current
alembic history
```

## Architecture

### Service layout and ports

| Service | Port | Purpose |
|---|---|---|
| `device-service` | 8000 | Device inventory, registration, heartbeat |
| `plugin-service` (module-service) | 8001 | Module/plugin metadata lifecycle |
| `execution-service` | 8002 | Command dispatch pipeline |
| `network-service` | 8003 | Network port abstractions |
| `dns-service` | 8004 | DNS record lifecycle |
| `webservice-service` | 8005 | Endpoint publication metadata |
| `fleet-service` | 8006 | Fleet grouping metadata |
| `nexora-edge` (edge-gateway) | 8007 | Kafka consumer, edge agent sessions |

All core services expose `/health`, `/ready`, and `/metrics` (Prometheus format).

### Two service implementation patterns

There are two patterns in use across services — be aware of which one you're working in:

1. **Structured pattern** (`device-service`, `plugin-service`): Uses `src/<service_name>/` package layout with `core/config.py`, `core/database.py`, `core/events.py`, `core/metrics.py`, and `api/` submodule. Uses `structlog` and `lifespan` context manager. Depends on `libraries/common`.

2. **Flat pattern** (most other services: `execution-service`, `fleet-service`, `dns-service`, etc.): Single `main.py` file with all models, routes, middleware, and startup logic inlined. Uses standard `logging` and `@app.on_event("startup")`.

### Event flow

Write operations follow: API request → persist to MySQL → publish Kafka event. Kafka topic names follow `{KAFKA_TOPIC_PREFIX}.{service}.{action}` (default prefix: `nxr`). The `execution-service` additionally implements a dispatch pipeline with explicit state machine transitions (`queued → dispatched → running → succeeded/failed/timeout/cancelled`).

### Shared libraries

- `libraries/common/src/common/`: Auth (OIDC + policy engine), database helpers, event bus, idempotency, outbox, DLQ, metrics, health, logging, OpenStack adapters (Keystone, Neutron, Nova, Glance/Cinder), tenancy, config/settings.
- `libraries/sdk/src/sdk/`: REST client (`api/client.py`) and gRPC client (`grpc/client.py`) for external consumers.

The common library is imported by services as `from common.X import Y` with `PYTHONPATH=libraries/common/src`.

### Auth model

All services check `AUTH_ENABLED` env var. When enabled: Bearer token → JWT decode (no signature verification in dev) → expiry check → issuer check against `KEYCLOAK_ISSUER` → write-role enforcement (`AUTH_WRITE_ROLE`) for mutating methods. Dev bypass: any request with `AUTH_DEV_TOKEN` value passes. `/health`, `/ready`, `/metrics` are always exempt.

### Kafka configuration

`KAFKA_ENABLED` (default `true`) gates whether events are published. `KAFKA_REQUIRED` (default `false`) controls whether startup fails if Kafka is unreachable. For tests, always set `KAFKA_ENABLED=false`.

### Database

Services default to `sqlite:///./service_name.db` when `DATABASE_URL` is unset — enables local dev and tests without MySQL. Production uses MySQL via the `DATABASE_URL` env var. Migrations live in `services/<name>/alembic/versions/`. Some flat-pattern services also have a `_ensure_<entity>_columns()` runtime migration fallback for ALTER TABLE.

### Legacy compatibility


## Release discipline

No CI pipeline — all validation is local. Before tagging a release:
1. Run `scripts/test-all.sh` and `scripts/postalpha-validation.sh`
2. Run targeted integration scripts for changed paths
3. Complete `docs/deployment/release-checklist-mvp.md`
