# Stack4Things v2.0 — Deployment Documentation

## Contents

- [IoTronic / Lightning Rod Parity Matrix](iotronic-parity-matrix.md) — concept mapping from legacy to v2.0
- [Execution Pipeline Runbook](execution-pipeline-runbook.md) — operator troubleshooting guide
- [Release Checklist (MVP)](release-checklist-mvp.md) — pre-release verification steps
- [IoTronic UI Adapter Deploy](iotronic-ui-adapter-deploy.md) — how to deploy the legacy dashboard adapter on Horizon
- [Keycloak Authentication](auth-keycloak-stack4things.md) — auth model and rollout for Stack4Things services

## Architecture Decision Records

- [ADR-0001: Lightningrod Gateway and Execution Pipeline](../adr/0001-lightningrod-and-execution-pipeline.md)

## Quick Start

```bash
docker compose -f docker-compose.dev.yml --profile dev up -d --build
```

### Optional auth profile (Keycloak)

```bash
docker compose -f docker-compose.dev.yml --profile auth up -d keycloak
```

### Optional legacy dashboard profile (Horizon + IoTronic plugin)

```bash
docker compose -f docker-compose.dev.yml --profile legacy up -d --build legacy-keystone legacy-horizon
```

- Horizon legacy URL: `http://localhost:18089`
- Keystone legacy URL: `http://localhost:15000/v3/`
- Bootstrap credentials: `admin / admin`

The legacy profile is isolated from the v2.0 UI service and can run in parallel for migration testing.

### Optional board emulator profile (Lightning Rod-like agents)

```bash
docker compose -f docker-compose.dev.yml --profile emulator up -d --build lr-board-emulator-1 lr-board-emulator-2
```

This profile starts two synthetic edge boards that:
- register to `device-service` as agents,
- open a session on `lightningrod-gateway`,
- send periodic heartbeats,
- consume dispatched executions and callback with `succeeded`.

All services expose `/health` and `/metrics` endpoints.
