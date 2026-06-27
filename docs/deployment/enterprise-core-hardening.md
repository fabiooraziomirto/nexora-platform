# Enterprise Core Hardening

This guide packages Nexora for a private/on-prem pilot aimed at public-sector
and research environments.

## Identity

Keycloak is the supported identity provider for this release.

Import the pilot realm:

```bash
kc.sh import --file infrastructure/kubernetes/keycloak/realm/nexora-pilot-realm.json
```

Configure the UI with:

```bash
VITE_KEYCLOAK_URL=https://keycloak.example.org
VITE_KEYCLOAK_REALM=nxr
VITE_KEYCLOAK_CLIENT_ID=nexora-ui
```

JWT contract:

- `sub` is the user ID.
- The first `groups[]` entry is the tenant ID.
- `realm_access.roles[]` contains Nexora roles.

Supported roles:

- `platform-admin`: cross-tenant administration.
- `tenant-admin`: full access inside one tenant.
- `operator`: operational write access inside one tenant.
- `viewer`: read-only access.

## Production Defaults

Use `.env.production.example` as the checklist for required settings. Production
must run with:

```bash
ENVIRONMENT=production
AUTH_ENABLED=true
AUTH_DEV_BYPASS_ENABLED=false
KAFKA_REQUIRED=true
```

Apply the production overlay after replacing placeholder secrets:

```bash
kubectl apply -k k8s/overlays/production
```

Run the preflight check from an environment that can reach Keycloak and the
Nexora service endpoints:

```bash
source .env.production
bash scripts/production-preflight.sh
```

## Secrets

This release uses Kubernetes Secrets as the supported pilot baseline. Use
`k8s/secrets.example.yaml` as a template and replace every `REPLACE_*` value
before applying it to a real cluster.

Vault is documented as a phase-2 migration path. Do not make Vault a hard
dependency for the first pilot unless the customer already operates it.

## Optional mTLS

Istio mTLS is optional. Apply it only on clusters that already run Istio:

```bash
kubectl apply -k k8s/overlays/istio-mtls
```

The overlay enables STRICT namespace mTLS and an ISTIO_MUTUAL destination rule.

## Audit

Structured audit events are written as JSONL to `AUDIT_LOG_PATH`, defaulting to:

```text
/tmp/nexora-audit/events.jsonl
```

The operator-facing API is:

```text
GET /api/v2/audit/events
```

Tenant admins see only their tenant. Platform admins may filter by `tenant_id`.
The UI exposes the same data under `/audit`.
