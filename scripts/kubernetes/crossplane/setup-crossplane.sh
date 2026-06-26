#!/bin/bash
# Setup script for Crossplane

set -e

echo "☁️  Setting up Crossplane for Nxr v2.0"

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
kubectl create namespace crossplane-system --dry-run=client -o yaml | kubectl apply -f -

# Install Crossplane using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing Crossplane using Helm..."
    
    helm repo add crossplane-stable https://charts.crossplane.io/stable
    helm repo update
    
    # Install Crossplane
    helm install crossplane crossplane-stable/crossplane \
        --namespace crossplane-system \
        --create-namespace \
        --wait
    
    echo "✅ Crossplane installed via Helm"
else
    echo "📦 Installing Crossplane using kubectl..."
    
    # Install Crossplane using kubectl
    kubectl apply -f https://raw.githubusercontent.com/crossplane/crossplane/release-1.14/cluster/charts/crossplane/crds/crd-storage.yaml
    kubectl apply -f https://raw.githubusercontent.com/crossplane/crossplane/release-1.14/cluster/charts/crossplane/crds/crd-apiextensions.yaml
    kubectl apply -f https://raw.githubusercontent.com/crossplane/crossplane/release-1.14/cluster/charts/crossplane/crds/crd-pkg.yaml
    
    # Wait for CRDs to be ready
    kubectl wait --for condition=established --timeout=60s crd/providerconfigs.pkg.crossplane.io
    
    echo "✅ Crossplane installed via kubectl"
fi

# Wait for Crossplane to be ready
echo "⏳ Waiting for Crossplane to be ready..."
kubectl wait --for=condition=ready pod \
    -l app=crossplane \
    -n crossplane-system \
    --timeout=300s

# Install Crossplane CLI (optional)
if ! command -v crossplane &> /dev/null; then
    echo "💡 Crossplane CLI not installed. Install it with:"
    echo "   curl -sL https://raw.githubusercontent.com/crossplane/crossplane-cli/main/bootstrap.sh | bash"
fi

echo ""
echo "✅ Crossplane setup complete!"
echo ""
echo "📋 Crossplane Status:"
kubectl get pods -n crossplane-system
echo ""
echo "📝 Next steps:"
echo "  1. Configure cloud provider:"
echo "     ./scripts/kubernetes/crossplane/setup-provider.sh <gcp|aws|azure>"
echo ""
echo "  2. Install providers:"
echo "     ./scripts/kubernetes/crossplane/install-providers.sh"
echo ""
echo "  3. Create XRDs and Compositions:"
echo "     ./scripts/kubernetes/crossplane/setup-compositions.sh"

