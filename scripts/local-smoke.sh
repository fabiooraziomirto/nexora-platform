#!/usr/bin/env bash
# Local Docker Compose smoke checks for Nexora.
#
# This script intentionally runs checks from inside service containers so it
# works in WSL/sandbox environments where localhost port forwarding may differ.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.dev.yml}"
PROFILE="${PROFILE:-dev}"
COMPOSE=(docker compose -f "$COMPOSE_FILE" --profile "$PROFILE")

PASS=0
FAIL=0

ok() {
  printf '[OK] %s\n' "$*"
  PASS=$((PASS + 1))
}

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  FAIL=$((FAIL + 1))
}

require_running() {
  local service=$1
  local state_health
  state_health="$("${COMPOSE[@]}" ps --format json "$service" | python3 -c '
import json
import sys

raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(1)
rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
row = rows[0]
print("{} {}".format(row.get("State", "unknown"), row.get("Health") or "no-healthcheck"))
' 2>/dev/null || true)"
  if [[ -z "$state_health" ]]; then
    fail "$service has no container"
    return 1
  fi
  case "$state_health" in
    "running healthy"|"running no-healthcheck"|"running starting")
      ok "$service is $state_health"
      ;;
    *)
      fail "$service is $state_health"
      return 1
      ;;
  esac
}

http_from() {
  local service=$1
  local url=$2
  local label=$3
  "${COMPOSE[@]}" exec -T "$service" python - "$url" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
with urllib.request.urlopen(url, timeout=5) as resp:
    body = resp.read(2048)
    if resp.status >= 400:
        raise SystemExit(f"{resp.status}: {body!r}")
PY
  ok "$label"
}

json_count_from() {
  local service=$1
  local url=$2
  local label=$3
  local total
  total="$("${COMPOSE[@]}" exec -T "$service" python - "$url" <<'PY'
import json
import sys
import urllib.request

url = sys.argv[1]
with urllib.request.urlopen(url, timeout=5) as resp:
    data = json.loads(resp.read().decode("utf-8"))
if "items" not in data or "total" not in data:
    raise SystemExit(f"unexpected payload: {data!r}")
print(data["total"])
PY
)"
  ok "$label (total=$total)"
}

printf 'Nexora local smoke checks (profile=%s)\n' "$PROFILE"

core_services=(
  mysql
  redis
  kafka
  device-service
  plugin-service
  execution-service
  network-service
  dns-service
  webservice-service
  fleet-service
  nexora-edge
  nexora-ui
)

for service in "${core_services[@]}"; do
  require_running "$service"
done

optional_services=(mosquitto mqtt-bridge zigbee-bridge matter-bridge nexora-function-runtime)
for service in "${optional_services[@]}"; do
  if "${COMPOSE[@]}" ps -q "$service" >/dev/null 2>&1 && [[ -n "$("${COMPOSE[@]}" ps -q "$service")" ]]; then
    require_running "$service"
  fi
done

http_from device-service "http://localhost:8000/health" "device-service health"
http_from execution-service "http://localhost:8000/health" "execution-service health"
http_from plugin-service "http://localhost:8000/health" "plugin-service health"
json_count_from device-service "http://localhost:8000/api/v2/devices?page=1&page_size=200" "device list API"

if "${COMPOSE[@]}" ps -q matter-bridge >/dev/null 2>&1 && [[ -n "$("${COMPOSE[@]}" ps -q matter-bridge)" ]]; then
  http_from matter-bridge "http://localhost:8008/health" "matter-bridge health"
fi

printf 'Smoke complete: %d passed, %d failed\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
