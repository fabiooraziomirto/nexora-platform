#!/bin/bash
# Setup Vault secrets engine and policies

set -e

echo "🔐 Setting up Vault secrets engine for Nxr"

VAULT_POD=$(kubectl get pods -n nxr-vault -l app.kubernetes.io/name=vault -o jsonpath='{.items[0].metadata.name}')
VAULT_ADDR="http://localhost:8200"
ROOT_TOKEN="dev-root-token"

# Wait for Vault to be ready
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=vault \
    -n nxr-vault \
    --timeout=300s

# Setup KV secrets engine
echo "📝 Setting up KV secrets engine..."
kubectl exec -n nxr-vault "$VAULT_POD" -- \
    vault secrets enable -path=nxr kv-v2 || true

# Create policies
echo "📝 Creating Vault policies..."

# Policy for services
kubectl exec -n nxr-vault "$VAULT_POD" -- \
    vault policy write nxr-service - <<EOF
path "nxr/data/*" {
  capabilities = ["read"]
}
EOF

# Policy for admin
kubectl exec -n nxr-vault "$VAULT_POD" -- \
    vault policy write nxr-admin - <<EOF
path "nxr/data/*" {
  capabilities = ["create", "read", "update", "delete"]
}
EOF

# Setup Kubernetes auth
echo "📝 Setting up Kubernetes authentication..."
kubectl exec -n nxr-vault "$VAULT_POD" -- \
    vault auth enable kubernetes || true

# Get Kubernetes service account token
TOKEN_REVIEW_JWT=$(kubectl exec -n nxr-vault "$VAULT_POD" -- cat /var/run/secrets/kubernetes.io/serviceaccount/token)
KUBE_CA_CERT=$(kubectl exec -n nxr-vault "$VAULT_POD" -- cat /var/run/secrets/kubernetes.io/serviceaccount/ca.crt | base64 | tr -d '\n')
KUBE_HOST=$(kubectl config view --raw --minify --flatten -o jsonpath='{.clusters[].cluster.server}')

# Configure Kubernetes auth
kubectl exec -n nxr-vault "$VAULT_POD" -- \
    vault write auth/kubernetes/config \
    token_reviewer_jwt="$TOKEN_REVIEW_JWT" \
    kubernetes_host="$KUBE_HOST" \
    kubernetes_ca_cert="$KUBE_CA_CERT"

# Create role for services
kubectl exec -n nxr-vault "$VAULT_POD" -- \
    vault write auth/kubernetes/role/nxr-service \
    bound_service_account_names=nxr-service \
    bound_service_account_namespaces=nxr \
    policies=nxr-service \
    ttl=1h

# Create initial secrets
echo "📝 Creating initial secrets..."

# Database credentials
kubectl exec -n nxr-vault "$VAULT_POD" -- \
    vault kv put nxr/database \
    username=nxr \
    password="$(openssl rand -base64 32)" \
    database=nxr

# Redis credentials
kubectl exec -n nxr-vault "$VAULT_POD" -- \
    vault kv put nxr/redis \
    password="$(openssl rand -base64 32)"

# App secrets
kubectl exec -n nxr-vault "$VAULT_POD" -- \
    vault kv put nxr/app \
    jwt-secret="$(openssl rand -hex 32)" \
    encryption-key="$(openssl rand -hex 32)"

echo ""
echo "✅ Vault secrets engine setup complete!"
echo ""
echo "📋 Secrets Paths:"
echo "  Database: nxr/database"
echo "  Redis: nxr/redis"
echo "  App: nxr/app"
echo ""
echo "📝 Read secret example:"
echo "  kubectl exec -n nxr-vault $VAULT_POD -- vault kv get nxr/database"

