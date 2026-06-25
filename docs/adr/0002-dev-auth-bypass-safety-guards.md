# ADR-0002 — Dev-Auth Bypass Safety Guards

**Status**: Accepted  
**Date**: 2026-06-25  
**Scope**: All FastAPI services with HTTP auth middleware (plugin-service, execution-service, fleet-service, dns-service, network-service, webservice-service) and iotronic-ui

---

## Context

Several services expose an `AUTH_DEV_TOKEN` environment variable that, when `AUTH_ENABLED=true`, allows a static token to bypass full JWT validation. This is useful during local development and automated E2E tests.

The original design had a latent security flaw: setting `AUTH_DEV_TOKEN=<value>` alone was sufficient to activate the bypass when auth was enabled — there was no separate opt-in flag. A misconfigured production deployment could accidentally activate the bypass if `AUTH_DEV_TOKEN` was set in the environment (e.g., via a copied `.env` file).

---

## Decision

Introduce a dedicated `AUTH_DEV_BYPASS_ENABLED` flag (default: `false`) that must be **explicitly set to `true`** to activate the bypass. The bypass now requires **both** conditions:

```
AUTH_DEV_BYPASS_ENABLED=true  AND  token == AUTH_DEV_TOKEN
```

Setting only `AUTH_DEV_TOKEN` without `AUTH_DEV_BYPASS_ENABLED=true` has no effect on auth decisions.

### Production guard

If `AUTH_DEV_BYPASS_ENABLED=true` and `ENVIRONMENT=production`, the service **fails startup** with a `RuntimeError`. This is intentionally fatal — a warning would be insufficient because the process could still serve traffic. The fail-fast behaviour forces the operator to explicitly resolve the misconfiguration before the service can accept requests.

### Startup warning

When `AUTH_DEV_BYPASS_ENABLED=true` (and `ENVIRONMENT != production`), every service emits a `WARNING`-level log line at startup:

```
AUTH DEV BYPASS ENABLED — NOT FOR PRODUCTION
```

This is visible in container logs regardless of log verbosity level.

### iotronic-ui local admin fallback

The UI's local-admin login fallback (`/login` endpoint) follows the same rule: the fallback is only active when `AUTH_DEV_BYPASS_ENABLED=true`. Without the flag, a failed Keycloak auth always returns a redirect to the login error page.

---

## Env vars summary

| Variable | Default | Purpose |
|---|---|---|
| `AUTH_DEV_BYPASS_ENABLED` | `false` | Explicit opt-in for dev token bypass |
| `AUTH_DEV_TOKEN` | `dev-token` | The static token value accepted when bypass is enabled |
| `AUTH_ENABLED` | `false` | Enables auth middleware (bypassed entirely when false) |
| `ENVIRONMENT` | `development` | Set to `production` to block bypass at startup |

---

## Consequences

**Positive**
- A copied `.env` with `AUTH_DEV_TOKEN` set cannot accidentally activate bypass in production.
- Production misconfiguration is caught at startup, not at first auth request.
- Startup warning ensures bypass is never silently active.

**Negative**
- Existing dev/test setups must now also set `AUTH_DEV_BYPASS_ENABLED=true` (alongside `AUTH_ENABLED=true`) to use static token auth. The E2E and benchmark scripts export this flag automatically.

---

## Implementation notes

- All 6 flat-service `main.py` files and `services/iotronic-ui/main.py` were updated uniformly in one changeset.
- The `docker-compose.dev.yml` file intentionally does **not** set `AUTH_DEV_BYPASS_ENABLED=true` by default because `AUTH_ENABLED` defaults to `false` in all services, making the bypass moot in the default dev stack. Operators who want to test the full auth path in dev should set both flags explicitly.
- Scripts `lr-emulator-e2e.sh` and `perf-dispatch-latency.sh` export `AUTH_DEV_BYPASS_ENABLED=true` as a default, honoring any override already present in the environment.
