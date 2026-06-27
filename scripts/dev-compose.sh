#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.dev.yml"
PROFILE="${COMPOSE_PROFILE:-dev}"

usage() {
  cat <<'EOF'
Usage: bash scripts/dev-compose.sh <command> [extra compose args]

Commands:
  up       Start dev stack with build (default)
  down     Stop stack
  clean    Stop stack and remove volumes
  ps       List compose services
  logs     Follow compose logs
  config   Show rendered compose config

Examples:
  bash scripts/dev-compose.sh up
  bash scripts/dev-compose.sh down
  bash scripts/dev-compose.sh clean
  COMPOSE_PROFILE=smoke bash scripts/dev-compose.sh up
  bash scripts/dev-compose.sh logs device-service
EOF
}

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

COMMAND="${1:-up}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$COMMAND" in
  up)
    docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" up -d --build "$@"
    ;;
  down)
    docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" down "$@"
    ;;
  clean)
    docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" down -v "$@"
    ;;
  ps)
    docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" ps "$@"
    ;;
  logs)
    docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" logs -f --tail=200 "$@"
    ;;
  config)
    docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" config "$@"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: $COMMAND" >&2
    usage
    exit 1
    ;;
esac
