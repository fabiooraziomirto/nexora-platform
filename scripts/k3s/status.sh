#!/usr/bin/env bash
# Nexora k3s — deployment health check
#
# Usage: bash scripts/k3s/status.sh

set -euo pipefail

NAMESPACE="nxr"
MON_NAMESPACE="nxr-monitoring"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $*"; }
fail() { echo -e "  ${RED}✗${NC} $*"; }

check_deployment() {
  local ns="$1" name="$2"
  local desired available
  desired=$(kubectl get deployment "$name" -n "$ns" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
  available=$(kubectl get deployment "$name" -n "$ns" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
  if [[ "$available" == "$desired" && "$desired" -gt 0 ]]; then
    ok "$name ($available/$desired)"
  elif [[ "$desired" == "0" ]]; then
    warn "$name not found"
  else
    fail "$name ($available/$desired replicas available)"
  fi
}

check_statefulset() {
  local ns="$1" name="$2"
  local ready
  ready=$(kubectl get statefulset "$name" -n "$ns" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
  if [[ "${ready:-0}" -gt 0 ]]; then
    ok "$name ($ready ready)"
  else
    fail "$name (0 ready)"
  fi
}

check_endpoint() {
  local svc="$1" port="$2" path="${3:-/health}"
  local url="http://${svc}.${NAMESPACE}.svc.cluster.local:${port}${path}"
  # Run from within the cluster via kubectl exec
  local status
  status=$(kubectl run --rm -i --restart=Never --image=curlimages/curl:8.4.0 \
    curl-check-$RANDOM -n "$NAMESPACE" \
    -- curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
  if [[ "$status" == "200" ]]; then
    ok "$svc $path → HTTP $status"
  else
    warn "$svc $path → HTTP $status (may be starting)"
  fi
}

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         Nexora Platform — Deployment Status                  ║"
echo "╠══════════════════════════════════════════════════════════════╣"

echo ""
echo "── k3s Node ─────────────────────────────────────────────────"
kubectl get nodes -o wide 2>/dev/null || fail "kubectl not available"

echo ""
echo "── Core Services (namespace: $NAMESPACE) ─────────────────────"
check_deployment "$NAMESPACE" device-service
check_deployment "$NAMESPACE" plugin-service
check_deployment "$NAMESPACE" execution-service
check_deployment "$NAMESPACE" fleet-service
check_deployment "$NAMESPACE" network-service
check_deployment "$NAMESPACE" dns-service
check_deployment "$NAMESPACE" webservice-service
check_deployment "$NAMESPACE" nexora-edge

echo ""
echo "── IoT Bridges ──────────────────────────────────────────────"
check_deployment "$NAMESPACE" mqtt-bridge
check_deployment "$NAMESPACE" zigbee-bridge
check_deployment "$NAMESPACE" matter-bridge

echo ""
echo "── Infrastructure ───────────────────────────────────────────"
check_statefulset "$NAMESPACE" mysql
check_statefulset "$NAMESPACE" kafka
check_statefulset "$NAMESPACE" zookeeper
check_statefulset "$NAMESPACE" redis
check_statefulset "$NAMESPACE" vault 2>/dev/null || warn "vault not installed"

echo ""
echo "── Auth ─────────────────────────────────────────────────────"
check_statefulset keycloak keycloak

echo ""
echo "── Monitoring ───────────────────────────────────────────────"
check_deployment "$MON_NAMESPACE" prometheus 2>/dev/null || warn "monitoring not installed"
check_deployment "$MON_NAMESPACE" grafana    2>/dev/null || warn "monitoring not installed"
check_deployment "$MON_NAMESPACE" alertmanager 2>/dev/null || warn "monitoring not installed"

echo ""
echo "── Pods (all namespaces) ────────────────────────────────────"
kubectl get pods -A --field-selector="metadata.namespace in (nxr,keycloak,nxr-monitoring)" \
  -o custom-columns="NAMESPACE:.metadata.namespace,NAME:.metadata.name,STATUS:.status.phase,READY:.status.containerStatuses[0].ready" 2>/dev/null

echo ""
echo "── PVC Usage ────────────────────────────────────────────────"
kubectl get pvc -n "$NAMESPACE" -o custom-columns="NAME:.metadata.name,STATUS:.status.phase,CAPACITY:.spec.resources.requests.storage" 2>/dev/null

echo ""
echo "── Backup Jobs ──────────────────────────────────────────────"
kubectl get cronjob -n "$NAMESPACE" -o custom-columns="NAME:.metadata.name,SCHEDULE:.spec.schedule,LAST-RUN:.status.lastScheduleTime" 2>/dev/null

echo ""
echo "╚══════════════════════════════════════════════════════════════╝"
