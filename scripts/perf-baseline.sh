#!/bin/bash
set -euo pipefail

TARGET_URL="${1:-http://localhost:8001/api/v2/plugins}"
REQUESTS="${2:-200}"
CONCURRENCY="${3:-20}"

if ! command -v hey >/dev/null 2>&1; then
  echo "hey tool not installed. Install with: brew install hey"
  exit 1
fi

echo "Running baseline performance test: ${TARGET_URL}"
hey -n "${REQUESTS}" -c "${CONCURRENCY}" "${TARGET_URL}"
