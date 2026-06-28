# Nxr v2.0 — Deployment Documentation

## Contents

- [IoTronic / Lightning Rod Parity Matrix](nexora-parity-matrix.md) — concept mapping from legacy to v2.0
- [Execution Pipeline Runbook](execution-pipeline-runbook.md) — operator troubleshooting guide
- [Local Development](local-development.md) — Docker Compose profiles, ports, and local smoke checks
- [Production Kubernetes Foundation](production-kubernetes-foundation.md) — baseline production env, secrets, and readiness requirements
- [Release Checklist (MVP)](release-checklist-mvp.md) — pre-release verification steps
- [Keycloak Authentication](auth-keycloak-nxr.md) — auth model and rollout for Nxr services

## Architecture Decision Records

- [ADR-0001: Lightningrod Gateway and Execution Pipeline](../adr/0001-nexoraedge-and-execution-pipeline.md)

## Quick Start

```bash
make dev
make local-smoke
```

### Optional direct Compose usage

```bash
docker compose -f docker-compose.dev.yml --profile dev up -d --build
```

### Optional legacy dashboard profile (Horizon + IoTronic plugin)

```bash
```

- Horizon legacy URL: `http://localhost:18089`
- Keystone legacy URL: `http://localhost:15000/v3/`
- Bootstrap credentials: `admin / admin`

The legacy profile is isolated from the v2.0 UI service and can run in parallel for migration testing.

### Optional board emulator profile (Lightning Rod-like agents)

```bash
docker compose -f docker-compose.dev.yml --profile emulator up -d --build nexora-device-emulator-1 nexora-device-emulator-2
```

This profile starts two synthetic edge boards that:
- register to `device-service` as agents,
- open a session on `nexora-edge`,
- send periodic heartbeats,
- consume dispatched executions and callback with `succeeded`.

All services expose `/health` and `/metrics` endpoints.
