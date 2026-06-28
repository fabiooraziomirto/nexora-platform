#!/usr/bin/env bash
# Nexora — Migrate data from docker-compose dev stack to k3s self-hosted
#
# Usage: bash scripts/k3s/migrate-from-compose.sh [--compose-project nexora]
#
# Requires: docker, kubectl, k3s running with nxr namespace

set -euo pipefail

COMPOSE_PROJECT="${COMPOSE_PROJECT:-nexora}"
COMPOSE_MYSQL_CONTAINER="${COMPOSE_MYSQL_CONTAINER:-${COMPOSE_PROJECT}-mysql-1}"
K3S_NAMESPACE="nxr"
DUMP_FILE="/tmp/nexora-migrate-$(date +%Y%m%d%H%M%S).sql.gz"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "  ${GREEN}→${NC} $*"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $*"; }
err()  { echo -e "  ${RED}✗${NC} $*" >&2; exit 1; }

need() { command -v "$1" &>/dev/null || err "$1 is required but not installed"; }

check_prereqs() {
  need docker
  need kubectl
  kubectl get namespace "$K3S_NAMESPACE" &>/dev/null || err "k3s namespace '$K3S_NAMESPACE' not found — run install.sh first"
  docker inspect "$COMPOSE_MYSQL_CONTAINER" &>/dev/null || \
    err "Docker container '$COMPOSE_MYSQL_CONTAINER' not found — is docker-compose stack running?"
}

dump_from_compose() {
  log "Dumping MySQL from docker-compose container: $COMPOSE_MYSQL_CONTAINER"
  docker exec "$COMPOSE_MYSQL_CONTAINER" bash -c \
    'mysqldump -u nexora -p"$MYSQL_PASSWORD" --single-transaction --routines --triggers nexora' \
    | gzip > "$DUMP_FILE"
  local size
  size=$(du -sh "$DUMP_FILE" | cut -f1)
  log "Dump written to $DUMP_FILE ($size)"
}

import_to_k3s() {
  local mysql_pod
  mysql_pod=$(kubectl get pod -n "$K3S_NAMESPACE" -l app=mysql -o name 2>/dev/null | head -1 | cut -d/ -f2)
  [[ -n "$mysql_pod" ]] || err "No MySQL pod found in namespace $K3S_NAMESPACE"
  log "Importing dump into k3s pod: $mysql_pod"

  # Copy dump into pod
  kubectl cp "$DUMP_FILE" "$K3S_NAMESPACE/$mysql_pod:/tmp/migrate.sql.gz"

  # Import
  kubectl exec -n "$K3S_NAMESPACE" "$mysql_pod" -- bash -c \
    'gunzip -c /tmp/migrate.sql.gz | mysql -u nexora -p"$MYSQL_PASSWORD" nexora && rm /tmp/migrate.sql.gz'
  log "Import complete"
}

verify_row_counts() {
  log "Verifying row counts in k3s MySQL..."
  local compose_counts k3s_counts
  compose_counts=$(docker exec "$COMPOSE_MYSQL_CONTAINER" bash -c \
    'mysql -u nexora -p"$MYSQL_PASSWORD" nexora -sN \
     -e "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema='"'"'nexora'"'"' ORDER BY table_name;"' 2>/dev/null)

  local mysql_pod
  mysql_pod=$(kubectl get pod -n "$K3S_NAMESPACE" -l app=mysql -o name 2>/dev/null | head -1 | cut -d/ -f2)
  k3s_counts=$(kubectl exec -n "$K3S_NAMESPACE" "$mysql_pod" -- bash -c \
    'mysql -u nexora -p"$MYSQL_PASSWORD" nexora -sN \
     -e "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema='"'"'nexora'"'"' ORDER BY table_name;"' 2>/dev/null)

  echo ""
  echo "  Table             | Compose | k3s"
  echo "  ------------------|---------|-----"
  while IFS=$'\t' read -r table rows; do
    local k3s_rows
    k3s_rows=$(echo "$k3s_counts" | grep "^${table}" | awk '{print $2}' || echo "?")
    printf "  %-18s| %-8s| %s\n" "$table" "$rows" "$k3s_rows"
  done <<< "$compose_counts"
  echo ""
}

print_manual_checklist() {
  echo ""
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║         Manual steps required after data migration          ║"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║                                                              ║"
  echo "║  [ ] Update DNS: point nexora.yourdomain.com → k3s node IP  ║"
  echo "║  [ ] Copy INTERNAL_SERVICE_KEY from compose .env to k3s     ║"
  echo "║      secret (or rotate and re-deploy all services)          ║"
  echo "║  [ ] Copy AGENT_BOOTSTRAP_TOKENS — existing devices use     ║"
  echo "║      the same tokens unless you rotate them                 ║"
  echo "║  [ ] Re-pair any Matter devices: Matter fabric is not       ║"
  echo "║      portable — commission fresh from the new platform      ║"
  echo "║  [ ] Verify Keycloak realm: confirm nxr realm imported OK   ║"
  echo "║      at https://auth.<domain>/realms/nxr                    ║"
  echo "║  [ ] Smoke test: curl https://<domain>/api/v2/devices       ║"
  echo "║  [ ] Update monitoring alerting endpoints if changed        ║"
  echo "║  [ ] Decommission docker-compose stack once verified        ║"
  echo "║                                                              ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
}

main() {
  echo ""
  echo "Nexora docker-compose → k3s migration"
  echo "────────────────────────────────────────"

  check_prereqs
  dump_from_compose
  import_to_k3s
  verify_row_counts
  rm -f "$DUMP_FILE"
  log "Temporary dump file removed"
  print_manual_checklist
}

main "$@"
