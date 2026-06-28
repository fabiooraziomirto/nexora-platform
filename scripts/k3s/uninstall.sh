#!/usr/bin/env bash
# Nexora Platform — Uninstall self-hosted k3s deployment
#
# Usage: bash scripts/k3s/uninstall.sh [--purge-data]
#
# Without --purge-data: removes k3s but keeps persistent volumes on disk.
# With --purge-data: removes everything including MySQL and Kafka data.

set -euo pipefail

PURGE_DATA=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --purge-data) PURGE_DATA=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

log() { echo "[nexora-uninstall] $*"; }

if [[ "$PURGE_DATA" == "true" ]]; then
  read -r -p "This will DELETE all Nexora data (database, kafka). Are you sure? (yes/N): " confirm
  [[ "$confirm" == "yes" ]] || { log "Aborted."; exit 0; }
fi

log "Removing Nexora namespaces..."
kubectl delete namespace nxr nxr-monitoring keycloak cert-manager --ignore-not-found=true --timeout=60s || true

if [[ "$PURGE_DATA" == "true" ]]; then
  log "Removing persistent volumes..."
  kubectl delete pvc --all -n nxr --ignore-not-found=true || true
fi

log "Uninstalling k3s..."
if command -v k3s-uninstall.sh &>/dev/null; then
  k3s-uninstall.sh
else
  log "k3s-uninstall.sh not found — k3s may already be removed"
fi

log "Done. Nexora has been removed from this host."
