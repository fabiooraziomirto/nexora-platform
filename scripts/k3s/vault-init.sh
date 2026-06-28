#!/usr/bin/env bash
# Nexora — Initialize and configure Vault for k3s self-hosted deployment.
#
# Usage: bash scripts/k3s/vault-init.sh
#
# Run ONCE after first deployment. Stores unseal keys locally (keep safe!).

set -euo pipefail

NAMESPACE="nxr"
VAULT_POD=$(kubectl get pod -n "$NAMESPACE" -l app=vault -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
KEYS_FILE="$HOME/.nexora/vault-keys.json"

log() { echo "[vault-init] $*"; }
ok()  { echo "[vault-init] ✓ $*"; }

[[ -z "$VAULT_POD" ]] && { log "ERROR: Vault pod not found in namespace $NAMESPACE"; exit 1; }

log "Vault pod: $VAULT_POD"

# Check if already initialized
if kubectl exec -n "$NAMESPACE" "$VAULT_POD" -- vault status 2>/dev/null | grep -q "Initialized.*true"; then
  log "Vault is already initialized"
  exit 0
fi

log "Initializing Vault (1 key share for self-hosted simplicity)..."
mkdir -p "$(dirname "$KEYS_FILE")"
chmod 700 "$(dirname "$KEYS_FILE")"

kubectl exec -n "$NAMESPACE" "$VAULT_POD" -- \
  vault operator init -key-shares=1 -key-threshold=1 -format=json > "$KEYS_FILE"
chmod 600 "$KEYS_FILE"

UNSEAL_KEY=$(jq -r '.unseal_keys_b64[0]' "$KEYS_FILE")
ROOT_TOKEN=$(jq -r '.root_token' "$KEYS_FILE")

log "Unsealing Vault..."
kubectl exec -n "$NAMESPACE" "$VAULT_POD" -- vault operator unseal "$UNSEAL_KEY"

log "Enabling Kubernetes auth..."
kubectl exec -n "$NAMESPACE" "$VAULT_POD" -- \
  vault login "$ROOT_TOKEN" > /dev/null

kubectl exec -n "$NAMESPACE" "$VAULT_POD" -- \
  vault auth enable kubernetes 2>/dev/null || true

# Configure K8s auth
K8S_HOST=$(kubectl config view --raw -o jsonpath='{.clusters[0].cluster.server}')
K8S_CA=$(kubectl get secret -n "$NAMESPACE" \
  "$(kubectl get sa nexora-service -n "$NAMESPACE" -o jsonpath='{.secrets[0].name}' 2>/dev/null || echo '')" \
  -o jsonpath='{.data.ca\.crt}' 2>/dev/null || echo "")

if [[ -n "$K8S_CA" ]]; then
  kubectl exec -n "$NAMESPACE" "$VAULT_POD" -- \
    vault write auth/kubernetes/config \
      kubernetes_host="$K8S_HOST" \
      kubernetes_ca_cert="$(echo "$K8S_CA" | base64 -d)"
fi

# Create nexora policy
kubectl exec -n "$NAMESPACE" "$VAULT_POD" -- \
  vault policy write nexora-services - <<'EOF'
path "secret/data/nexora/*" {
  capabilities = ["read", "list"]
}
path "secret/data/nexora/internal/*" {
  capabilities = ["read", "list"]
}
EOF

log "Enabling KV secrets engine..."
kubectl exec -n "$NAMESPACE" "$VAULT_POD" -- \
  vault secrets enable -path=secret kv-v2 2>/dev/null || true

log "Storing Nexora secrets in Vault..."
INTERNAL_KEY=$(kubectl get secret nexora-internal -n "$NAMESPACE" \
  -o jsonpath='{.data.INTERNAL_SERVICE_KEY}' | base64 -d)
BOOTSTRAP_TOKENS=$(kubectl get secret nexora-internal -n "$NAMESPACE" \
  -o jsonpath='{.data.AGENT_BOOTSTRAP_TOKENS}' | base64 -d)

kubectl exec -n "$NAMESPACE" "$VAULT_POD" -- \
  vault kv put secret/nexora/internal \
    INTERNAL_SERVICE_KEY="$INTERNAL_KEY" \
    AGENT_BOOTSTRAP_TOKENS="$BOOTSTRAP_TOKENS"

ok "Vault initialized and configured"
echo ""
echo "  Unseal key and root token saved to: $KEYS_FILE"
echo "  IMPORTANT: Back up this file securely — it cannot be recovered!"
echo ""
echo "  Vault UI: kubectl port-forward -n $NAMESPACE svc/vault 8200:8200"
echo "  Then open: http://localhost:8200"
echo "  Root token: $ROOT_TOKEN"
