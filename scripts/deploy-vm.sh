#!/usr/bin/env bash
# deploy-vm.sh — Nexora Platform deployment wizard for Ubuntu Server VMs.
#
# Usage:
#   bash scripts/deploy-vm.sh
#
# Modes:
#   1) Docker Compose + port forwarding  (ports exposed on the host, e.g. :8000, :8006, :8080)
#   2) k3s (Kubernetes) + NodePort       (single-node k3s, services on NodePort 30000-30080)
#
# Requirements:
#   - Ubuntu 22.04 / 24.04
#   - sudo privileges
#   - Internet access (for Docker / k3s install)

set -euo pipefail

###############################################################################
# Colours & helpers
###############################################################################
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[nexora]${RESET} $*"; }
success() { echo -e "${GREEN}[nexora]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[nexora]${RESET} $*"; }
error()   { echo -e "${RED}[nexora] ERROR:${RESET} $*" >&2; exit 1; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

###############################################################################
# Banner
###############################################################################
echo -e "${BOLD}"
cat <<'BANNER'
  _   _
 | \ | | _____  _____  _ __ __ _
 |  \| |/ _ \ \/ / _ \| '__/ _` |
 | |\  |  __/>  < (_) | | | (_| |
 |_| \_|\___/_/\_\___/|_|  \__,_|
  Platform — deployment wizard
BANNER
echo -e "${RESET}"

###############################################################################
# Detect VM IP (used for the final summary)
###############################################################################
VM_IP=$(hostname -I | awk '{print $1}')
info "Host IP detected: ${BOLD}${VM_IP}${RESET}"
echo ""

###############################################################################
# Mode selection
###############################################################################
echo -e "${BOLD}Choose deployment mode:${RESET}"
echo "  1) Docker Compose  — port forwarding on host  (simple, no k8s)"
echo "  2) k3s NodePort    — single-node Kubernetes   (portable, NodePort)"
echo ""
read -rp "Enter choice [1/2]: " MODE_CHOICE
echo ""

case "$MODE_CHOICE" in
  1) MODE="compose" ;;
  2) MODE="k3s"     ;;
  *) error "Invalid choice. Run the script again and enter 1 or 2." ;;
esac

###############################################################################
# Shared: ensure Docker is installed
###############################################################################
install_docker() {
  if command -v docker &>/dev/null; then
    success "Docker already installed: $(docker --version)"
    return
  fi
  info "Installing Docker..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  success "Docker installed. You may need to log out and back in for group changes."
}

###############################################################################
# MODE 1 — Docker Compose
###############################################################################
deploy_compose() {
  install_docker

  if ! command -v docker &>/dev/null; then
    error "Docker not found after install. Please re-login and run the script again."
  fi

  # Install docker compose plugin if missing
  if ! docker compose version &>/dev/null; then
    info "Installing docker compose plugin..."
    sudo apt-get install -y docker-compose-plugin 2>/dev/null || \
      sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose && \
      sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  fi

  info "Building and starting the stack (profile: smoke)..."
  docker compose -f docker-compose.dev.yml --profile smoke up -d --build

  echo ""
  success "Stack is up! Service endpoints:"
  echo ""
  printf "  %-22s %s\n" "Service"         "URL"
  printf "  %-22s %s\n" "-------"         "---"
  printf "  %-22s ${CYAN}http://${VM_IP}:%s${RESET}\n" "nexora-ui (dashboard)" "8080"
  printf "  %-22s ${CYAN}http://${VM_IP}:%s${RESET}\n" "device-service"        "8000"
  printf "  %-22s ${CYAN}http://${VM_IP}:%s${RESET}\n" "plugin-service"        "8001"
  printf "  %-22s ${CYAN}http://${VM_IP}:%s${RESET}\n" "execution-service"     "8002"
  printf "  %-22s ${CYAN}http://${VM_IP}:%s${RESET}\n" "network-service"       "8003"
  printf "  %-22s ${CYAN}http://${VM_IP}:%s${RESET}\n" "dns-service"           "8004"
  printf "  %-22s ${CYAN}http://${VM_IP}:%s${RESET}\n" "webservice-service"    "8005"
  printf "  %-22s ${CYAN}http://${VM_IP}:%s${RESET}\n" "fleet-service"         "8006"
  printf "  %-22s ${CYAN}http://${VM_IP}:%s${RESET}\n" "nexora-edge"           "8007"
  echo ""
  info "To stop:  docker compose -f docker-compose.dev.yml --profile smoke down"
  info "Logs:     docker compose -f docker-compose.dev.yml logs -f"
}

###############################################################################
# MODE 2 — k3s + NodePort
###############################################################################
deploy_k3s() {
  # ── 1. Install k3s ──────────────────────────────────────────────────────────
  if command -v k3s &>/dev/null; then
    success "k3s already installed: $(k3s --version | head -1)"
  else
    info "Installing k3s (single-node Kubernetes)..."
    curl -sfL https://get.k3s.io | sudo sh -
    # Wait for node to be ready
    info "Waiting for k3s node to become ready..."
    local i=0
    until sudo k3s kubectl get node 2>/dev/null | grep -q " Ready"; do
      sleep 3; i=$((i+1))
      [ $i -gt 40 ] && error "k3s node did not become ready in time."
    done
    success "k3s node is ready."
  fi

  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

  # ── 2. Install Docker (for local image builds) ───────────────────────────────
  install_docker

  # ── 3. Build all service images ─────────────────────────────────────────────
  SERVICES=(
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

  info "Building service images..."
  for svc in "${SERVICES[@]}"; do
    svc_dir="services/${svc}"
    if [ -f "${svc_dir}/Dockerfile" ]; then
      info "  Building nxr/${svc}:latest"
      docker build -t "nxr/${svc}:latest" "${svc_dir}/" -q
    else
      warn "  No Dockerfile for ${svc}, skipping."
    fi
  done

  # ── 4. Import images into k3s containerd ────────────────────────────────────
  info "Importing images into k3s containerd..."
  for svc in "${SERVICES[@]}"; do
    if docker image inspect "nxr/${svc}:latest" &>/dev/null; then
      docker save "nxr/${svc}:latest" | sudo k3s ctr images import - 2>/dev/null && \
        info "  Imported nxr/${svc}:latest" || \
        warn "  Could not import nxr/${svc}:latest (may already exist)"
    fi
  done

  # ── 5. Apply manifests ───────────────────────────────────────────────────────
  info "Applying Kubernetes manifests..."
  sudo k3s kubectl apply -f k8s/base/namespace.yaml
  sudo k3s kubectl apply -f k8s/base/infra.yaml
  # Wait for MySQL to be ready before deploying services
  info "Waiting for MySQL to become ready (this can take ~60s)..."
  sudo k3s kubectl rollout status deployment/mysql -n nxr --timeout=120s || \
    warn "MySQL rollout timed out — services may fail on first start, they will retry."
  sudo k3s kubectl apply -f k8s/base/services.yaml
  sudo k3s kubectl apply -f k8s/nodeport/services.yaml

  # ── 6. Wait for deployments ──────────────────────────────────────────────────
  info "Waiting for service deployments..."
  for svc in "${SERVICES[@]}"; do
    sudo k3s kubectl rollout status deployment/"${svc}" -n nxr --timeout=120s 2>/dev/null || \
      warn "  ${svc} rollout not complete yet (will retry in background)"
  done

  # ── 7. Summary ───────────────────────────────────────────────────────────────
  echo ""
  success "k3s NodePort deployment complete!"
  echo ""
  printf "  %-22s %-12s %s\n" "Service"          "NodePort"  "URL"
  printf "  %-22s %-12s %s\n" "-------"          "--------"  "---"
  printf "  %-22s %-12s ${CYAN}http://${VM_IP}:%s${RESET}\n" "nexora-ui"          "30080" "30080"
  printf "  %-22s %-12s ${CYAN}http://${VM_IP}:%s${RESET}\n" "device-service"     "30000" "30000"
  printf "  %-22s %-12s ${CYAN}http://${VM_IP}:%s${RESET}\n" "plugin-service"     "30001" "30001"
  printf "  %-22s %-12s ${CYAN}http://${VM_IP}:%s${RESET}\n" "execution-service"  "30002" "30002"
  printf "  %-22s %-12s ${CYAN}http://${VM_IP}:%s${RESET}\n" "network-service"    "30003" "30003"
  printf "  %-22s %-12s ${CYAN}http://${VM_IP}:%s${RESET}\n" "dns-service"        "30004" "30004"
  printf "  %-22s %-12s ${CYAN}http://${VM_IP}:%s${RESET}\n" "webservice-service" "30005" "30005"
  printf "  %-22s %-12s ${CYAN}http://${VM_IP}:%s${RESET}\n" "fleet-service"      "30006" "30006"
  printf "  %-22s %-12s ${CYAN}http://${VM_IP}:%s${RESET}\n" "nexora-edge"        "30007" "30007"
  echo ""
  info "kubectl alias:  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
  info "Pod status:     sudo k3s kubectl get pods -n nxr"
  info "Logs:           sudo k3s kubectl logs -n nxr deploy/device-service -f"
  info "Teardown:       sudo k3s kubectl delete namespace nxr"
}

###############################################################################
# Run selected mode
###############################################################################
case "$MODE" in
  compose) deploy_compose ;;
  k3s)     deploy_k3s     ;;
esac
