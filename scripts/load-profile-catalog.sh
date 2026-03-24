#!/bin/bash
set -euo pipefail

TARGET="${1:-http://localhost:8001/api/v2/plugins}"
PROFILE="${2:-steady}"

if ! command -v hey >/dev/null 2>&1; then
  echo "hey not installed"
  exit 1
fi

case "$PROFILE" in
  steady) hey -n 1000 -c 20 "$TARGET" ;;
  burst) hey -n 2000 -c 200 "$TARGET" ;;
  soak) hey -z 5m -c 30 "$TARGET" ;;
  stress) hey -n 5000 -c 400 "$TARGET" ;;
  *) echo "Unknown profile: $PROFILE"; exit 1 ;;
esac
