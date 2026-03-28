# Stack4Things v2.0 — Deployment Documentation

## Contents

- [IoTronic / Lightning Rod Parity Matrix](iotronic-parity-matrix.md) — concept mapping from legacy to v2.0
- [Execution Pipeline Runbook](execution-pipeline-runbook.md) — operator troubleshooting guide
- [Release Checklist (MVP)](release-checklist-mvp.md) — pre-release verification steps

## Architecture Decision Records

- [ADR-0001: Lightningrod Gateway and Execution Pipeline](../adr/0001-lightningrod-and-execution-pipeline.md)

## Quick Start

```bash
docker compose -f docker-compose.dev.yml --profile dev up -d --build
```

All services expose `/health` and `/metrics` endpoints.
