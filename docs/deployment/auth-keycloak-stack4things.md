# Keycloak Authentication for Stack4Things v2.0

## Current implementation

Services already support bearer auth via env vars:

- `AUTH_ENABLED=true|false`
- `AUTH_DEV_TOKEN=...` (dev fallback)
- `KEYCLOAK_ISSUER=...`
- `AUTH_WRITE_ROLE=writer`

When enabled, write operations require a token containing `realm_access.roles`
with the configured write role.

## Run Keycloak locally

```bash
docker compose -f docker-compose.dev.yml --profile auth up -d keycloak
```

Keycloak console: `http://localhost:18080` (admin/admin in dev profile).

## Suggested rollout

1. Keep `AUTH_ENABLED=false` for bootstrap/smoke.
2. Configure Keycloak realm/client and role mappings.
3. Set `KEYCLOAK_ISSUER` in service env to your realm issuer URL.
4. Switch `AUTH_ENABLED=true` service-by-service.
5. Update dashboard adapter runtime with `S4T_AUTH_TOKEN`.

## Notes for IoTronic UI adapter

The adapted dashboard does not authenticate directly against Keycloak by itself;
it forwards an optional static bearer token (`S4T_AUTH_TOKEN`) to Stack4Things APIs.
For production, wire Horizon auth/session to obtain and refresh this token.
