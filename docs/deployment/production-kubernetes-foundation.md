# Production Kubernetes Foundation

This document captures the baseline production settings for the first
Kubernetes hardening wave. It complements the service manifests under
`services/*/k8s/` and keeps local `.env.dev` workflows unchanged.

## Required Runtime Settings

Apply these values through the existing per-service ConfigMaps referenced by
each deployment (`<service>-config`):

```yaml
ENVIRONMENT: "production"
AUTH_ENABLED: "true"
AUTH_DEV_BYPASS_ENABLED: "false"
KAFKA_REQUIRED: "true"
```

For `nexora-edge`, also require Redis-backed state:

```yaml
ENVIRONMENT: "production"
KAFKA_REQUIRED: "true"
REDIS_ENABLED: "true"
REDIS_REQUIRED: "true"
```

The application now fails startup in production when authentication is disabled
or the development auth bypass is enabled. `nexora-edge` also fails startup in
production unless Redis is enabled and required, preventing accidental
single-instance in-memory session state.

## Secrets

Keep runtime secrets in the existing per-service Secret references
(`<service>-secrets`). Do not place real values in ConfigMaps or committed
manifests.

Minimum secret-backed values for production:

- `DATABASE_URL`
- `KEYCLOAK_ISSUER` or the service-specific Keycloak URL/JWKS settings
- `AUTH_DEV_TOKEN` only if needed for non-production automation; do not enable
  `AUTH_DEV_BYPASS_ENABLED` in production
- Kafka, Redis, and database credentials where the target cluster requires them
- `AGENT_CALLBACK_SECRET` for `execution-service` when callback replay
  protection is enabled

## Validation Checklist

Before promoting a cluster configuration:

- Confirm all service pods expose healthy `/health` and ready `/ready`.
- Confirm `nexora-edge` reports Redis as `ok` from `/ready`.
- Confirm Kafka outages fail readiness/startup when `KAFKA_REQUIRED=true`.
- Confirm `ENVIRONMENT=production AUTH_ENABLED=false` fails startup.
- Confirm `ENVIRONMENT=production AUTH_DEV_BYPASS_ENABLED=true` fails startup.
