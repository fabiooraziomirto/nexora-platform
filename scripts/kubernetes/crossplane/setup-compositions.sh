#!/bin/bash
# Setup compositions for Nxr infrastructure

set -e

echo "📦 Setting up Crossplane Compositions for Nxr"

# Check if Crossplane is installed
if ! kubectl get deployment crossplane -n crossplane-system &> /dev/null; then
    echo "❌ Crossplane not found. Installing..."
    ./scripts/kubernetes/crossplane/setup-crossplane.sh
fi

# Apply XRDs (Composite Resource Definitions)
echo "📝 Applying Composite Resource Definitions..."
kubectl apply -f infrastructure/crossplane/xrds/ || true

# Wait for XRDs to be ready
echo "⏳ Waiting for XRDs to be ready..."
kubectl wait --for=condition=established --timeout=60s \
    crd/xstacks.database.nxr.io || true
kubectl wait --for=condition=established --timeout=60s \
    crd/xstacks.cache.nxr.io || true
kubectl wait --for=condition=established --timeout=60s \
    crd/xstacks.messaging.nxr.io || true
kubectl wait --for=condition=established --timeout=60s \
    crd/xstacks.storage.nxr.io || true
kubectl wait --for=condition=established --timeout=60s \
    crd/xstacks.loadbalancer.nxr.io || true

# Apply Compositions
echo "📝 Applying Compositions..."
kubectl apply -f infrastructure/crossplane/compositions/ || true

echo ""
echo "✅ Compositions setup complete!"
echo ""
echo "📋 Available Compositions:"
kubectl get compositions
echo ""
echo "📋 Available XRDs:"
kubectl get crd | grep nxr
echo ""
echo "💡 Example usage:"
echo "  kubectl apply -f infrastructure/crossplane/examples/database-claim.yaml"

