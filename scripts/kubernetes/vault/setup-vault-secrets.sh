#!/bin/bash
# Setup Vault secrets engine and policies

set -e

echo "🔐 Setting up Vault secrets engine for Stack4Things"

VAULT_POD=$(kubectl get pods -n stack4things-vault -l app.kubernetes.io/name=vault -o jsonpath='{.items[0].metadata.name}')
VAULT_ADDR="http://localhost:8200"
ROOT_TOKEN="dev-root-token"

# Wait for Vault to be ready
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=vault \
    -n stack4things-vault \
    --timeout=300s

# Setup KV secrets engine
echo "📝 Setting up KV secrets engine..."
kubectl exec -n stack4things-vault "$VAULT_POD" -- \
    vault secrets enable -path=stack4things kv-v2 || true

# Create policies
echo "📝 Creating Vault policies..."

# Policy for services
kubectl exec -n stack4things-vault "$VAULT_POD" -- \
    vault policy write stack4things-service - <<EOF
path "stack4things/data/*" {
  capabilities = ["read"]
}
EOF

# Policy for admin
kubectl exec -n stack4things-vault "$VAULT_POD" -- \
    vault policy write stack4things-admin - <<EOF
path "stack4things/data/*" {
  capabilities = ["create", "read", "update", "delete"]
}
EOF

# Setup Kubernetes auth
echo "📝 Setting up Kubernetes authentication..."
kubectl exec -n stack4things-vault "$VAULT_POD" -- \
    vault auth enable kubernetes || true

# Get Kubernetes service account token
TOKEN_REVIEW_JWT=$(kubectl exec -n stack4things-vault "$VAULT_POD" -- cat /var/run/secrets/kubernetes.io/serviceaccount/token)
KUBE_CA_CERT=$(kubectl exec -n stack4things-vault "$VAULT_POD" -- cat /var/run/secrets/kubernetes.io/serviceaccount/ca.crt | base64 | tr -d '\n')
KUBE_HOST=$(kubectl config view --raw --minify --flatten -o jsonpath='{.clusters[].cluster.server}')

# Configure Kubernetes auth
kubectl exec -n stack4things-vault "$VAULT_POD" -- \
    vault write auth/kubernetes/config \
    token_reviewer_jwt="$TOKEN_REVIEW_JWT" \
    kubernetes_host="$KUBE_HOST" \
    kubernetes_ca_cert="$KUBE_CA_CERT"

# Create role for services
kubectl exec -n stack4things-vault "$VAULT_POD" -- \
    vault write auth/kubernetes/role/stack4things-service \
    bound_service_account_names=stack4things-service \
    bound_service_account_namespaces=stack4things \
    policies=stack4things-service \
    ttl=1h

# Create initial secrets
echo "📝 Creating initial secrets..."

# Database credentials
kubectl exec -n stack4things-vault "$VAULT_POD" -- \
    vault kv put stack4things/database \
    username=stack4things \
    password="$(openssl rand -base64 32)" \
    database=stack4things

# Redis credentials
kubectl exec -n stack4things-vault "$VAULT_POD" -- \
    vault kv put stack4things/redis \
    password="$(openssl rand -base64 32)"

# App secrets
kubectl exec -n stack4things-vault "$VAULT_POD" -- \
    vault kv put stack4things/app \
    jwt-secret="$(openssl rand -hex 32)" \
    encryption-key="$(openssl rand -hex 32)"

echo ""
echo "✅ Vault secrets engine setup complete!"
echo ""
echo "📋 Secrets Paths:"
echo "  Database: stack4things/database"
echo "  Redis: stack4things/redis"
echo "  App: stack4things/app"
echo ""
echo "📝 Read secret example:"
echo "  kubectl exec -n stack4things-vault $VAULT_POD -- vault kv get stack4things/database"

