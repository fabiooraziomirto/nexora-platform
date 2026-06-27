#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"
UI_URL="${UI_URL:-http://localhost:8080}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:18080}"
DEVICE_URL="${DEVICE_URL:-http://localhost:8000}"
PLUGIN_URL="${PLUGIN_URL:-http://localhost:8001}"
EXECUTION_URL="${EXECUTION_URL:-http://localhost:8002}"
NETWORK_URL="${NETWORK_URL:-http://localhost:8003}"
DNS_URL="${DNS_URL:-http://localhost:8004}"
WEBSERVICE_URL="${WEBSERVICE_URL:-http://localhost:8005}"
FLEET_URL="${FLEET_URL:-http://localhost:8006}"
EDGE_URL="${EDGE_URL:-http://localhost:8007}"
AI_URL="${AI_URL:-http://localhost:8008}"
FUNCTION_RUNTIME_URL="${FUNCTION_RUNTIME_URL:-http://localhost:9000}"
EMULATOR_URL="${EMULATOR_URL:-http://localhost:8091}"

failures=0

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "FAIL missing command: $1"
    exit 1
  fi
}

check_http() {
  local name="$1"
  local url="$2"
  local code
  code="$(curl -fsS -o /dev/null -w "%{http_code}" "$url" || true)"
  if [[ "$code" =~ ^[23] ]]; then
    printf "OK   %-24s %s\n" "$name" "$url"
  else
    printf "FAIL %-24s %s (http %s)\n" "$name" "$url" "${code:-000}"
    failures=$((failures + 1))
  fi
}

check_optional_http() {
  local name="$1"
  local url="$2"
  local code
  code="$(curl -fsS -o /dev/null -w "%{http_code}" "$url" || true)"
  if [[ "$code" =~ ^[23] ]]; then
    printf "OK   %-24s %s\n" "$name" "$url"
  else
    printf "WARN %-24s %s (http %s)\n" "$name" "$url" "${code:-000}"
  fi
}

check_json_count() {
  local name="$1"
  local url="$2"
  local body
  body="$(curl -fsS "$url" || true)"
  if [[ -n "$body" ]]; then
    printf "OK   %-24s %s\n" "$name" "$url"
  else
    printf "FAIL %-24s %s\n" "$name" "$url"
    failures=$((failures + 1))
  fi
}

need curl

echo "Nexora Demo Reliability Gate"
echo "============================"
echo

check_http "UI" "$UI_URL/"
check_http "Keycloak realm" "$KEYCLOAK_URL/realms/nxr/.well-known/openid-configuration"
check_http "Device health" "$DEVICE_URL/health"
check_http "Device ready" "$DEVICE_URL/ready"
check_http "Fleet health" "$FLEET_URL/health"
check_http "Execution health" "$EXECUTION_URL/health"
check_http "Plugin health" "$PLUGIN_URL/health"
check_http "Network health" "$NETWORK_URL/health"
check_http "DNS health" "$DNS_URL/health"
check_http "Webservice health" "$WEBSERVICE_URL/health"
check_http "Edge gateway health" "$EDGE_URL/health"
check_http "AI health" "$AI_URL/health"
check_optional_http "Function runtime" "$FUNCTION_RUNTIME_URL/health"
check_optional_http "Emulator pairing UI" "$EMULATOR_URL/"

echo
echo "Demo data surface"
echo "-----------------"
check_json_count "Devices API" "$DEVICE_URL/api/v2/devices?page=1&page_size=10"
check_json_count "Pending pairing API" "$DEVICE_URL/api/v2/devices/pending"
check_json_count "Executions API" "$EXECUTION_URL/api/v2/executions?page=1&page_size=10"
check_json_count "Audit API" "$DEVICE_URL/api/v2/audit/events?page=1&page_size=10"
check_json_count "Audit export JSON" "$DEVICE_URL/api/v2/audit/events/export?format=json&limit=10"

echo
echo "Container status"
echo "----------------"
if command -v docker >/dev/null 2>&1; then
  if docker compose -f "$COMPOSE_FILE" --profile dev ps >/tmp/nexora-demo-gate-ps.txt 2>/tmp/nexora-demo-gate-ps.err; then
    cat /tmp/nexora-demo-gate-ps.txt
    if grep -Eiq "(unhealthy|exited|dead)" /tmp/nexora-demo-gate-ps.txt; then
      echo "FAIL compose stack has unhealthy or exited containers"
      failures=$((failures + 1))
    else
      echo "OK   compose stack has no obvious unhealthy/exited containers"
    fi
  else
    echo "WARN docker compose status unavailable"
    cat /tmp/nexora-demo-gate-ps.err
  fi
else
  echo "WARN docker not installed; container status skipped"
fi

echo
if [[ "$failures" -gt 0 ]]; then
  echo "Demo gate failed with $failures blocking check(s)."
  exit 1
fi

echo "Demo gate passed."
