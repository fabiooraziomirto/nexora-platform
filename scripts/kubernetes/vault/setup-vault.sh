#!/bin/bash
# Setup script for HashiCorp Vault

set -e

echo "🗄️  Setting up HashiCorp Vault for Stack4Things v2.0"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is required but not installed."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster"
    exit 1
fi

# Create namespace if it doesn't exist
kubectl create namespace stack4things-vault --dry-run=client -o yaml | kubectl apply -f -

# Install Vault using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing Vault using Helm..."
    
    helm repo add hashicorp https://helm.releases.hashicorp.com
    helm repo update
    
    # Install Vault in dev mode (for development/testing)
    # For production, use HA mode with proper storage backend
    helm install vault hashicorp/vault \
        --namespace stack4things-vault \
        --set server.dev.enabled=true \
        --set server.dev.devRootToken="dev-root-token" \
        --set server.dataStorage.enabled=true \
        --set server.dataStorage.storageClass=local-path \
        --set server.dataStorage.size=10Gi \
        --wait
    
    echo "✅ Vault installed via Helm"
else
    echo "❌ Helm is required for Vault installation"
    echo "Please install Helm: https://helm.sh/docs/intro/install/"
    exit 1
fi

# Wait for Vault to be ready
echo "⏳ Waiting for Vault to be ready..."
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=vault \
    -n stack4things-vault \
    --timeout=300s

# Initialize Vault (dev mode already initialized)
echo "🔓 Vault is running in dev mode"
echo "Root token: dev-root-token"

# Apply Vault configuration
echo "📝 Applying Vault configuration..."
kubectl apply -f infrastructure/kubernetes/vault/ || true

# Setup Vault secrets engine
echo "📝 Setting up Vault secrets engine..."
./scripts/kubernetes/vault/setup-vault-secrets.sh

echo ""
echo "✅ Vault setup complete!"
echo ""
echo "📋 Vault Info:"
echo "  Namespace: stack4things-vault"
echo "  Service: vault.stack4things-vault.svc.cluster.local:8200"
echo "  Root Token: dev-root-token (dev mode only)"
echo ""
echo "📝 Access Vault UI:"
echo "  kubectl port-forward -n stack4things-vault svc/vault 8200:8200"
echo "  Open http://localhost:8200"
echo ""
echo "⚠️  WARNING: This is dev mode. For production, use HA mode with proper storage backend."

