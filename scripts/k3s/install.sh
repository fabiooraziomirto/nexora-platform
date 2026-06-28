#!/usr/bin/env bash
# Nexora Platform — Self-hosted installer for k3s
#
# Usage:
#   curl -sfL https://raw.githubusercontent.com/nexora/nexora-platform/main/scripts/k3s/install.sh | bash
#   OR locally:
#   bash scripts/k3s/install.sh [--domain nexora.example.com] [--no-tls] [--monitoring]
#
# Requirements: Linux x86_64/arm64, 2+ CPU, 4GB+ RAM, 40GB+ disk

set -euo pipefail

# ── defaults ──────────────────────────────────────────────────────────────────
NEXORA_DOMAIN="${NEXORA_DOMAIN:-nexora.local}"
NEXORA_VERSION="${NEXORA_VERSION:-latest}"
INSTALL_MONITORING="${INSTALL_MONITORING:-false}"
INSTALL_SECURITY="${INSTALL_SECURITY:-true}"
INSTALL_VAULT="${INSTALL_VAULT:-false}"
TLS_MODE="${TLS_MODE:-self-signed}"   # self-signed | letsencrypt | none
ACME_EMAIL="${ACME_EMAIL:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/../../infrastructure/k3s" && pwd)"
K3S_NAMESPACE="nxr"

# ── argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --domain)       NEXORA_DOMAIN="$2"; shift 2 ;;
    --no-tls)       TLS_MODE="none"; shift ;;
    --letsencrypt)  TLS_MODE="letsencrypt"; shift ;;
    --email)        ACME_EMAIL="$2"; shift 2 ;;
    --monitoring)   INSTALL_MONITORING="true"; shift ;;
    --vault)        INSTALL_VAULT="true"; shift ;;
    --no-security)  INSTALL_SECURITY="false"; shift ;;
    --version)      NEXORA_VERSION="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

if [[ "$TLS_MODE" == "letsencrypt" && -z "$ACME_EMAIL" ]]; then
  err "--letsencrypt requires --email user@example.com"
fi

# ── helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[nexora] $*"; }
ok()   { echo "[nexora] ✓ $*"; }
err()  { echo "[nexora] ✗ $*" >&2; exit 1; }
need() { command -v "$1" &>/dev/null || err "$1 is required but not installed"; }

check_prereqs() {
  need curl
  need kubectl
  [[ $(id -u) -eq 0 ]] || err "Run as root or with sudo"

  local mem_kb
  mem_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
  [[ $mem_kb -ge 3900000 ]] || log "WARNING: less than 4GB RAM detected — performance may be degraded"
}

# ── k3s installation ──────────────────────────────────────────────────────────
install_k3s() {
  if command -v k3s &>/dev/null; then
    ok "k3s already installed ($(k3s --version | head -1))"
    return
  fi

  log "Installing k3s..."
  # Traefik is kept (unlike k3d dev setup) because it's the prod ingress controller
  curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=servicelb" sh -

  # Export kubeconfig for current user
  mkdir -p "$HOME/.kube"
  cp /etc/rancher/k3s/k3s.yaml "$HOME/.kube/config"
  chmod 600 "$HOME/.kube/config"
  export KUBECONFIG="$HOME/.kube/config"

  log "Waiting for k3s node to be Ready..."
  kubectl wait --for=condition=Ready node --all --timeout=120s
  ok "k3s installed and running"
}

# ── cert-manager ──────────────────────────────────────────────────────────────
install_cert_manager() {
  if kubectl get namespace cert-manager &>/dev/null; then
    ok "cert-manager already installed"
    return
  fi

  log "Installing cert-manager..."
  kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.yaml
  kubectl wait --for=condition=Available deployment --all -n cert-manager --timeout=120s
  ok "cert-manager ready"
}

# ── namespaces & RBAC ─────────────────────────────────────────────────────────
apply_base() {
  log "Applying namespaces and RBAC..."
  kubectl apply -f "$INFRA_DIR/base/namespaces.yaml"
  kubectl apply -f "$INFRA_DIR/base/rbac.yaml"
  ok "Base resources applied"
}

# ── secrets ───────────────────────────────────────────────────────────────────
generate_secrets() {
  if kubectl get secret nexora-internal -n "$K3S_NAMESPACE" &>/dev/null; then
    ok "Secrets already exist — skipping generation"
    return
  fi

  log "Generating secrets..."

  local internal_key bootstrap_token db_password db_url root_password

  internal_key=$(openssl rand -hex 32)
  bootstrap_token="bridge:$(openssl rand -hex 16):4102444800"
  db_password=$(openssl rand -hex 16)
  root_password=$(openssl rand -hex 16)
  db_url="mysql://nexora:${db_password}@mysql:3306/nexora"

  kubectl create secret generic nexora-internal \
    --namespace="$K3S_NAMESPACE" \
    --from-literal=INTERNAL_SERVICE_KEY="$internal_key" \
    --from-literal=AGENT_BOOTSTRAP_TOKENS="$bootstrap_token"

  kubectl create secret generic nexora-db \
    --namespace="$K3S_NAMESPACE" \
    --from-literal=DATABASE_URL="$db_url" \
    --from-literal=MYSQL_ROOT_PASSWORD="$root_password" \
    --from-literal=MYSQL_PASSWORD="$db_password"

  kubectl create secret generic nexora-keycloak \
    --namespace="$K3S_NAMESPACE" \
    --from-literal=KEYCLOAK_ADMIN_PASSWORD="$(openssl rand -hex 16)" \
    --from-literal=AUTH_DEV_TOKEN="$(openssl rand -hex 16)"

  ok "Secrets generated"
  log "  Bootstrap token: $bootstrap_token (save this for device pairing)"
}

# ── configmap ─────────────────────────────────────────────────────────────────
apply_configmap() {
  log "Applying configmap (domain=$NEXORA_DOMAIN)..."

  # Patch domain into configmap before applying
  sed "s/nexora.local/$NEXORA_DOMAIN/g; s/nexora.example.com/$NEXORA_DOMAIN/g" \
    "$INFRA_DIR/base/configmap.yaml" | kubectl apply -f -

  ok "ConfigMap applied"
}

# ── database & kafka ──────────────────────────────────────────────────────────
deploy_infrastructure() {
  log "Deploying MySQL and Kafka..."
  kubectl apply -f "$INFRA_DIR/database/mysql.yaml"
  kubectl apply -f "$INFRA_DIR/database/kafka.yaml"

  log "Waiting for MySQL to be ready (up to 3 min)..."
  kubectl wait --for=condition=Ready pod -l app=mysql -n "$K3S_NAMESPACE" --timeout=180s || \
    log "WARNING: MySQL not ready yet — services will retry on startup"

  ok "Infrastructure deployed"
}

# ── ingress / TLS ─────────────────────────────────────────────────────────────
configure_ingress() {
  case $TLS_MODE in
    letsencrypt)
      log "Configuring Let's Encrypt TLS for $NEXORA_DOMAIN (email=$ACME_EMAIL)..."
      sed "s/nexora.example.com/$NEXORA_DOMAIN/g; s/NEXORA_ACME_EMAIL/$ACME_EMAIL/g" \
        "$INFRA_DIR/mesh/traefik-ingress.yaml" | kubectl apply -f -
      ;;
    self-signed)
      log "Configuring self-signed TLS (no public domain required)..."
      # Create a self-signed certificate for the domain
      kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned
spec:
  selfSigned: {}
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: nexora-tls
  namespace: $K3S_NAMESPACE
spec:
  secretName: nexora-tls
  issuerRef:
    name: selfsigned
    kind: ClusterIssuer
  dnsNames:
    - "$NEXORA_DOMAIN"
    - "auth.$NEXORA_DOMAIN"
    - "*.${NEXORA_DOMAIN}"
EOF
      sed "s/nexora.example.com/$NEXORA_DOMAIN/g; s/certResolver: letsencrypt/secretName: nexora-tls/g" \
        "$INFRA_DIR/mesh/traefik-ingress.yaml" | kubectl apply -f -
      ;;
    none)
      log "Skipping TLS configuration (HTTP only)"
      ;;
  esac
  ok "Ingress configured (mode=$TLS_MODE)"
}

# ── auth (keycloak) ──────────────────────────────────────────────────────────
deploy_auth() {
  log "Deploying Keycloak..."
  kubectl apply -f "$INFRA_DIR/auth/keycloak.yaml"
  log "Waiting for Keycloak (up to 3 min)..."
  kubectl wait --for=condition=Ready pod -l app=keycloak -n keycloak --timeout=180s || \
    log "WARNING: Keycloak not ready yet"
  ok "Keycloak deployed"
}

# ── vault (optional) ─────────────────────────────────────────────────────────
deploy_vault() {
  if [[ "$INSTALL_VAULT" != "true" ]]; then
    return
  fi
  log "Deploying Vault..."
  kubectl apply -f "$INFRA_DIR/auth/vault.yaml"
  log "Vault deployed. IMPORTANT: run 'kubectl exec -n nxr deploy/vault -- vault operator init' to initialize."
  ok "Vault deployed (requires manual init)"
}

# ── security policies ─────────────────────────────────────────────────────────
deploy_security() {
  if [[ "$INSTALL_SECURITY" != "true" ]]; then
    return
  fi

  log "Applying network policies..."
  kubectl apply -f "$INFRA_DIR/security/network-policies.yaml"

  log "Checking for Kyverno..."
  if kubectl get crd clusterpolicies.kyverno.io &>/dev/null; then
    kubectl apply -f "$INFRA_DIR/security/kyverno-policies.yaml"
    ok "Kyverno policies applied"
  else
    log "Kyverno not installed — skipping pod security policies"
    log "  Install with: kubectl apply -f https://github.com/kyverno/kyverno/releases/download/v1.11.1/install.yaml"
  fi
  ok "Security configured"
}

# ── kafka topics ──────────────────────────────────────────────────────────────
init_kafka_topics() {
  log "Initializing Kafka topics..."
  kubectl apply -f "$INFRA_DIR/database/kafka-topics-init.yaml"
  ok "Kafka topic init job submitted"
}

# ── backup ────────────────────────────────────────────────────────────────────
deploy_backup() {
  log "Configuring automated MySQL backups..."
  kubectl apply -f "$INFRA_DIR/backup/mysql-backup.yaml"
  ok "Backup CronJobs scheduled (daily 02:00, verify 03:00)"
}

# ── redis ─────────────────────────────────────────────────────────────────────
deploy_redis() {
  log "Deploying Redis..."
  kubectl apply -f "$INFRA_DIR/database/redis.yaml"
  ok "Redis deployed"
}

# ── nexora services ───────────────────────────────────────────────────────────
deploy_services() {
  log "Deploying Nexora services..."
  kubectl apply -f "$INFRA_DIR/services/mosquitto.yaml"
  kubectl apply -f "$INFRA_DIR/services/device-service.yaml"
  kubectl apply -f "$INFRA_DIR/services/execution-service.yaml"
  kubectl apply -f "$INFRA_DIR/services/remaining-services.yaml"
  kubectl apply -f "$INFRA_DIR/services/network-dns-webservice.yaml"
  kubectl apply -f "$INFRA_DIR/services/bridges.yaml"

  log "Waiting for core services to be ready (up to 5 min)..."
  kubectl wait --for=condition=Available deployment/device-service \
    deployment/execution-service deployment/plugin-service \
    -n "$K3S_NAMESPACE" --timeout=300s || \
    log "WARNING: Some services not ready yet — check: kubectl get pods -n $K3S_NAMESPACE"

  ok "Services deployed"
}

# ── monitoring (optional) ─────────────────────────────────────────────────────
deploy_monitoring() {
  if [[ "$INSTALL_MONITORING" != "true" ]]; then
    return
  fi
  log "Deploying monitoring stack (Prometheus + Grafana + AlertManager)..."
  kubectl apply -f "$INFRA_DIR/monitoring/prometheus-rules.yaml"
  kubectl apply -f "$INFRA_DIR/monitoring/prometheus-lightweight.yaml"
  kubectl apply -f "$INFRA_DIR/monitoring/alertmanager.yaml"
  kubectl apply -f "$INFRA_DIR/monitoring/grafana-dashboards.yaml"
  ok "Monitoring deployed — Prometheus :9090 / Grafana :3000 (admin/admin) / AlertManager :9093"
}

# ── summary ───────────────────────────────────────────────────────────────────
print_summary() {
  local node_ip
  node_ip=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}' 2>/dev/null || echo "<node-ip>")

  echo ""
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║         Nexora Platform — Self-hosted Installation           ║"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  Domain:   $NEXORA_DOMAIN"
  echo "║  TLS:      $TLS_MODE"
  echo "║  Node IP:  $node_ip"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  API:      https://$NEXORA_DOMAIN/api/v2/"
  echo "║  Auth:     https://auth.$NEXORA_DOMAIN"
  if [[ "$INSTALL_MONITORING" == "true" ]]; then
  echo "║  Grafana:      http://$node_ip:3000    (admin/admin)"
  echo "║  Prometheus:   http://$node_ip:9090"
  echo "║  AlertManager: http://$node_ip:9093"
  fi
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  Check status:  kubectl get pods -n nxr"
  echo "║  View logs:     kubectl logs -n nxr deploy/device-service"
  echo "║  Uninstall:     bash scripts/k3s/uninstall.sh"
  echo "╚══════════════════════════════════════════════════════════════╝"
}

# ── main ──────────────────────────────────────────────────────────────────────
main() {
  log "Nexora self-hosted installer starting (domain=$NEXORA_DOMAIN, tls=$TLS_MODE)"
  check_prereqs
  install_k3s
  install_cert_manager
  apply_base
  generate_secrets
  apply_configmap
  deploy_infrastructure
  deploy_redis
  init_kafka_topics
  deploy_auth
  deploy_vault
  deploy_security
  configure_ingress
  deploy_services
  deploy_backup
  deploy_monitoring
  print_summary
}

main "$@"
