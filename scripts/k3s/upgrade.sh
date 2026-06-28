#!/usr/bin/env bash
# Nexora Platform — Rolling upgrade of services on k3s
#
# Usage: bash scripts/k3s/upgrade.sh [--version v1.2.3] [--service device-service]
#
# Without --service: upgrades all Nexora deployments.
# With --service: upgrades only the specified deployment.

set -euo pipefail

NEXORA_VERSION="${NEXORA_VERSION:-latest}"
TARGET_SERVICE=""
K3S_NAMESPACE="nxr"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/../../infrastructure/k3s" && pwd)"

while [[ $# -gt 0 ]]; do
  case $1 in
    --version)  NEXORA_VERSION="$2"; shift 2 ;;
    --service)  TARGET_SERVICE="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

log() { echo "[nexora-upgrade] $*"; }
ok()  { echo "[nexora-upgrade] ✓ $*"; }

SERVICES=(
  device-service
  plugin-service
  execution-service
  fleet-service
  nexora-edge
  mqtt-bridge
  zigbee-bridge
  matter-bridge
)

upgrade_service() {
  local svc="$1"
  local image="nexora/${svc}:${NEXORA_VERSION}"
  log "Upgrading $svc → $image"
  kubectl set image "deployment/$svc" "$svc=$image" -n "$K3S_NAMESPACE"
  kubectl rollout status "deployment/$svc" -n "$K3S_NAMESPACE" --timeout=120s
  ok "$svc upgraded"
}

if [[ -n "$TARGET_SERVICE" ]]; then
  upgrade_service "$TARGET_SERVICE"
else
  log "Upgrading all services to $NEXORA_VERSION..."
  for svc in "${SERVICES[@]}"; do
    upgrade_service "$svc" || log "WARNING: $svc upgrade failed — continuing"
  done
  ok "All services upgraded"
fi

log "Current pod status:"
kubectl get pods -n "$K3S_NAMESPACE" -o wide
