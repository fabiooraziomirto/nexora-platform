# IoTronic UI -> Nxr v2 Adapter

This fork adapts legacy `nexora-dashboard` (Horizon plugin) to Nxr v2 APIs.

## What changed

- `nexora_dashboard/api/nexora.py` no longer uses `nexoraclient`.
- It calls Nxr services directly over HTTP:
  - device-service: boards/devices
  - plugin-service: plugins
  - network-service: ports
  - fleet-service: fleets
  - webservice-service: webservices
- Plugin actions / service actions not yet available in v2 are stubbed with
  compatibility messages so the UI remains navigable.
- Python3 compatibility fix for `cPickle` imports in plugin forms/views.

## Authentication

Original dashboard relied on Keystone session/token.
In this adapter:
- Horizon login/identity still depends on your Horizon deployment policy.
- Backend API calls can optionally send a static bearer token via:
  - `S4T_AUTH_TOKEN`
- Tenant scoping can be set with:
  - `S4T_TENANT_ID`

## Endpoint configuration

Set these env vars for Horizon process:

- `S4T_DEVICE_URL` (default `http://localhost:8000`)
- `S4T_PLUGIN_URL` (default `http://localhost:8001`)
- `S4T_EXECUTION_URL` (default `http://localhost:8002`)
- `S4T_NETWORK_URL` (default `http://localhost:8003`)
- `S4T_DNS_URL` (default `http://localhost:8004`)
- `S4T_WEBSERVICE_URL` (default `http://localhost:8005`)
- `S4T_FLEET_URL` (default `http://localhost:8006`)

## Deploy on Horizon host

Run:

```bash
bash deploy/deploy_nxr_horizon.sh
```

Then restart Apache/httpd hosting Horizon.

## Limitations

- `service_*` and plugin board-side execution are compatibility stubs.
- Full legacy parity (WAMP/Crossbar workflows) is intentionally not reproduced.
