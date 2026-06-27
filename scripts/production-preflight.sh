#!/usr/bin/env bash
set -euo pipefail

DEVICE_URL="${DEVICE_URL:-http://localhost:8000}"
EXEC_URL="${EXEC_URL:-http://localhost:8002}"
PLUGIN_URL="${PLUGIN_URL:-http://localhost:8001}"
FLEET_URL="${FLEET_URL:-http://localhost:8006}"
GW_URL="${GW_URL:-http://localhost:8007}"

fail() { echo "[FAIL] $*" >&2; exit 1; }
ok() { echo "[OK] $*"; }

[ "${ENVIRONMENT:-}" = "production" ] || fail "ENVIRONMENT must be production"
[ "${AUTH_ENABLED:-}" = "true" ] || fail "AUTH_ENABLED must be true"
[ "${AUTH_DEV_BYPASS_ENABLED:-}" = "false" ] || fail "AUTH_DEV_BYPASS_ENABLED must be false"
[ "${KAFKA_REQUIRED:-}" = "true" ] || fail "KAFKA_REQUIRED must be true"

for var in KEYCLOAK_URL KEYCLOAK_REALM DATABASE_URL KAFKA_BOOTSTRAP_SERVERS AGENT_CALLBACK_SECRET; do
  [ -n "${!var:-}" ] || fail "$var is required"
done

JWKS_URL="${KEYCLOAK_JWKS_URL:-${KEYCLOAK_URL%/}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/certs}"
curl -fsS "$JWKS_URL" >/dev/null || fail "Keycloak JWKS is not reachable: $JWKS_URL"
ok "Keycloak JWKS reachable"

for endpoint in \
  "$DEVICE_URL/health" "$DEVICE_URL/ready" \
  "$EXEC_URL/health" "$EXEC_URL/ready" \
  "$PLUGIN_URL/health" "$PLUGIN_URL/ready" \
  "$FLEET_URL/health" "$FLEET_URL/ready" \
  "$GW_URL/health" "$GW_URL/ready"; do
  curl -fsS "$endpoint" >/dev/null || fail "Endpoint not ready: $endpoint"
done

ok "Core health/readiness endpoints passed"
