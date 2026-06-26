#!/usr/bin/env bash
# run-unit-tests.sh — run every service's unit test suite with the correct
# PYTHONPATH and infra-disabled env. No running infrastructure required
# (SQLite + KAFKA_ENABLED=false + AUTH_ENABLED=false + REDIS_ENABLED=false).
#
# Usage: bash scripts/run-unit-tests.sh [service-name]
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export KAFKA_ENABLED=false AUTH_ENABLED=false REDIS_ENABLED=false OTEL_ENABLED=false

# service : pythonpath (relative to service dir)
SERVICES=(
  "device-service:src"
  "execution-service:src"
  "plugin-service:src"
  "rbac-service:src"
  "fleet-service:.:src"
  "dns-service:.:src"
  "network-service:.:src"
  "webservice-service:.:src"
  "nexora-edge:.:src"
  "nexora-function-runtime:."
)

filter="${1:-}"
fail=0
for entry in "${SERVICES[@]}"; do
  svc="${entry%%:*}"
  pp="${entry#*:}"
  [ -n "$filter" ] && [ "$filter" != "$svc" ] && continue
  dir="services/${svc}"
  [ -d "${dir}/tests" ] || { echo "skip ${svc} (no tests/)"; continue; }
  echo "──────────────────────────────────────────"
  echo "Running ${svc} (PYTHONPATH=${pp})"
  ( cd "$dir" && rm -f ./*.db 2>/dev/null
    PYTHONPATH="$pp" python3 -m pytest tests/ -q \
      --override-ini="addopts=" -p no:cacheprovider ) || fail=1
done

if [ "$fail" -ne 0 ]; then
  echo "✗ Some service test suites failed."
  exit 1
fi
echo "✓ All service test suites passed."
