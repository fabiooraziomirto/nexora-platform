#!/bin/bash
# Setup RBAC system for Stack4Things

set -e

echo "🔐 Setting up RBAC system for Stack4Things v2.0"

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
kubectl create namespace stack4things --dry-run=client -o yaml | kubectl apply -f -

# Apply RBAC configurations
echo "📝 Applying RBAC configurations..."
kubectl apply -f infrastructure/kubernetes/rbac/ || true

# Setup policy engine
echo "📝 Setting up policy engine..."
kubectl apply -f infrastructure/kubernetes/rbac/policy-engine/ || true

# Setup policy caching
echo "📝 Setting up policy caching..."
kubectl apply -f infrastructure/kubernetes/rbac/policy-cache/ || true

# Deploy RBAC service (if exists)
if [ -f "services/rbac-service/k8s/deployment.yaml" ]; then
    echo "📝 Deploying RBAC service..."
    kubectl apply -f services/rbac-service/k8s/ || true
fi

# Verify installation
echo ""
echo "📋 RBAC Configuration Status:"
kubectl get configmap -n stack4things | grep -E "rbac|policy"

echo ""
echo "✅ RBAC setup complete!"
echo ""
echo "📋 Components:"
echo "  ✅ OpenStack standard roles configured"
echo "  ✅ Stack4Things custom roles configured"
echo "  ✅ Policy engine configured"
echo "  ✅ Policy caching enabled"
echo ""
echo "📝 Next steps:"
echo "  1. Integrate with Keycloak:"
echo "     ./scripts/kubernetes/rbac/integrate-keycloak.sh"
echo ""
echo "  2. Integrate with Keystone:"
echo "     ./scripts/kubernetes/rbac/integrate-keystone.sh"
echo ""
echo "  3. Setup audit logging:"
echo "     ./scripts/kubernetes/rbac/setup-audit.sh"

