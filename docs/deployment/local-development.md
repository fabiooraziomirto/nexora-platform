# Local Development

This guide covers the local Docker Compose path. It does not require GitHub Actions or any hosted CI/CD integration.

## Commands

```bash
make dev          # full development stack, profile=dev
make smoke        # smaller core stack, profile=smoke
make ps           # container status
make logs         # follow logs
make local-smoke  # local smoke checks against the active stack
make down         # stop containers
make clean        # stop containers and remove volumes
```

Equivalent script form:

```bash
bash scripts/dev-compose.sh up
bash scripts/dev-compose.sh smoke
bash scripts/dev-compose.sh down
```

Use a different profile with:

```bash
PROFILE=smoke make dev
COMPOSE_PROFILE=smoke bash scripts/dev-compose.sh up
```

## Profiles

- `dev`: full local platform, including UI, emulator, IoT bridges, Keycloak, Kafka, MySQL, Redis, Jaeger, and function runtime.
- `smoke`: core services and infrastructure for fast checks.
- `mqtt`: Mosquitto plus MQTT bridge.
- `zigbee`: Mosquitto, zigbee2mqtt, and Zigbee bridge.
- `matter`: Matter server plus Matter bridge.
- `emulator`: device emulator and function runtime helpers.
- `ollama`: optional local LLM runtime.

## Local Ports

| Component | Host port | Notes |
| --- | ---: | --- |
| device-service | 8000 | device inventory, agent register, telemetry |
| plugin-service | 8001 | plugin/function catalog |
| execution-service | 8002 | execution dispatch and callbacks |
| network-service | 8003 | ports/network metadata |
| dns-service | 8004 | DNS records |
| webservice-service | 8005 | published webservices |
| fleet-service | 8006 | fleet membership and fleet health |
| nexora-edge | 8007 | agent tunnel/session gateway |
| ai-pipeline-service | 8008 | AI insights/risk/functions |
| mqtt-bridge | 8009 | MQTT bridge API |
| zigbee-bridge | 8010 | Zigbee bridge API |
| matter-bridge | 8011 | host mapping to container port 8008 |
| nexora-ui | 8080 | dashboard |
| Keycloak | 18080 | dev identity provider |
| Kafka | 29092 | host listener; services use `kafka:9092` internally |
| MySQL | 3306 | dev database |
| Redis | 6379 | cache/session support |
| Jaeger UI | 16686 | tracing UI |

## Smoke Checks

`scripts/local-smoke.sh` verifies that required services are running, calls health endpoints from inside containers, and exercises:

- `device-service /health`
- `execution-service /health`
- `plugin-service /health`
- `device-service /api/v2/devices?page=1&page_size=200`
- `matter-bridge /health` when the Matter profile is active

This catches the most common local regressions: stale database schemas, unhealthy Kafka/MySQL dependencies, broken service imports, and port conflicts.

## Database Schema In Dev

The local stack keeps MySQL volumes between runs. Some services therefore include idempotent schema guards in addition to Alembic migrations. This keeps existing dev volumes usable after new columns are added. For a completely clean database:

```bash
make clean
make dev
```
