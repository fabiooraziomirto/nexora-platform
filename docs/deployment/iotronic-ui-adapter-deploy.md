# Deploy IoTronic UI Adapter on Nxr v2.0

This project includes a compatibility adapter for the original IoTronic Horizon
plugin under:

- `tools/nexora-dashboard-adapter/`

The adapter remaps legacy IoTronic API calls to Nxr v2 microservices.

## Important

- Functional parity is provided for core inventory/actions.
- WAMP/Crossbar protocol parity is **not** provided (by design).
- Horizon itself still requires a working OpenStack Dashboard runtime.

## Authentication model

In Nxr v2 services, auth is bearer-token based (`Authorization: Bearer ...`).

Recommended approach:

1. Run Keycloak (optional profile in compose):
   `docker compose -f docker-compose.dev.yml --profile auth up -d keycloak`
2. Issue a token for a service-account/user in Keycloak realm.
3. Configure Horizon runtime env with:
   - `S4T_AUTH_TOKEN=<access-token>`
   - `S4T_TENANT_ID=<tenant-id>` (optional)

If service auth is disabled (`AUTH_ENABLED=false`), token is not required.

## Deploy steps on Horizon host

```bash
cd /path/to/nxr_v2.0
bash scripts/deploy-nexora-dashboard-adapter.sh
```

If your Horizon paths differ:

```bash
HORIZON_API_DIR=/custom/api \
HORIZON_ENABLED_DIR=/custom/enabled \
bash scripts/deploy-nexora-dashboard-adapter.sh
```

Then restart Horizon web server.

## Endpoint configuration

Set these env vars for Horizon process if services are not local:

- `S4T_DEVICE_URL` (default `http://localhost:8000`)
- `S4T_PLUGIN_URL` (default `http://localhost:8001`)
- `S4T_EXECUTION_URL` (default `http://localhost:8002`)
- `S4T_NETWORK_URL` (default `http://localhost:8003`)
- `S4T_DNS_URL` (default `http://localhost:8004`)
- `S4T_WEBSERVICE_URL` (default `http://localhost:8005`)
- `S4T_FLEET_URL` (default `http://localhost:8006`)


## Built-in UI service (recommended for local deployment)

The repository now includes an operational compatibility dashboard service:

```bash
docker compose -f docker-compose.dev.yml --profile dev --profile ui --profile auth up -d --build
```

- UI: `http://localhost:18088`
- Keycloak: `http://localhost:18080`

Login in the UI by pasting a bearer token (or leave empty if `AUTH_ENABLED=false`).
