#!/bin/bash
# Setup compositions for Stack4Things infrastructure

set -e

echo "📦 Setting up Crossplane Compositions for Stack4Things"

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
    crd/xstacks.database.stack4things.io || true
kubectl wait --for=condition=established --timeout=60s \
    crd/xstacks.cache.stack4things.io || true
kubectl wait --for=condition=established --timeout=60s \
    crd/xstacks.messaging.stack4things.io || true
kubectl wait --for=condition=established --timeout=60s \
    crd/xstacks.storage.stack4things.io || true
kubectl wait --for=condition=established --timeout=60s \
    crd/xstacks.loadbalancer.stack4things.io || true

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
kubectl get crd | grep stack4things
echo ""
echo "💡 Example usage:"
echo "  kubectl apply -f infrastructure/crossplane/examples/database-claim.yaml"

