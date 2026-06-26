#!/bin/bash
# Setup script for k3d local Kubernetes cluster

set -e

CLUSTER_NAME="nxr"
KUBECONFIG_PATH="$HOME/.kube/config"

echo "🚀 Setting up k3d Kubernetes cluster for Nxr v2.0"

# Check if k3d is installed
if ! command -v k3d &> /dev/null; then
    echo "📦 Installing k3d..."
    curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
else
    echo "✅ k3d already installed"
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is required but not installed. Please install kubectl first."
    exit 1
fi

# Check if cluster already exists
if k3d cluster list | grep -q "$CLUSTER_NAME"; then
    echo "⚠️  Cluster '$CLUSTER_NAME' already exists"
    read -p "Do you want to delete and recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Deleting existing cluster..."
        k3d cluster delete "$CLUSTER_NAME"
    else
        echo "Using existing cluster"
        k3d kubeconfig merge "$CLUSTER_NAME" --kubeconfig-merge-default
        kubectl cluster-info
        exit 0
    fi
fi

# Create k3d cluster
echo "🔧 Creating k3d cluster '$CLUSTER_NAME'..."
k3d cluster create "$CLUSTER_NAME" \
    --port "80:80@loadbalancer" \
    --port "443:443@loadbalancer" \
    --port "8080:8080@loadbalancer" \
    --port "8443:8443@loadbalancer" \
    --servers 1 \
    --agents 2 \
    --k3s-arg "--disable=traefik@server:0" \
    --wait

# Merge kubeconfig
echo "📝 Merging kubeconfig..."
k3d kubeconfig merge "$CLUSTER_NAME" --kubeconfig-merge-default

# Verify cluster
echo "✅ Cluster created successfully!"
kubectl cluster-info

# Wait for nodes to be ready
echo "⏳ Waiting for nodes to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=120s

echo ""
echo "✅ k3d cluster setup complete!"
echo ""
echo "Next steps:"
echo "1. Apply namespace structure:"
echo "   kubectl apply -f infrastructure/kubernetes/base/namespaces.yaml"
echo ""
echo "2. Setup RBAC:"
echo "   kubectl apply -f infrastructure/kubernetes/base/rbac/"
echo ""
echo "3. Install Ingress Controller:"
echo "   ./scripts/kubernetes/setup-ingress.sh"
echo ""
echo "4. Install Cert-Manager:"
echo "   ./scripts/kubernetes/setup-cert-manager.sh"
