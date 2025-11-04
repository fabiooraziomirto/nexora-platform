#!/bin/bash
# Complete Kubernetes infrastructure setup script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 Setting up complete Kubernetes infrastructure for Stack4Things v2.0"

# Step 1: Create k3d cluster
echo ""
echo "=== Step 1: Creating k3d cluster ==="
"$SCRIPT_DIR/setup-k3d.sh"

# Step 2: Apply namespaces
echo ""
echo "=== Step 2: Applying namespace structure ==="
kubectl apply -f "$PROJECT_ROOT/infrastructure/kubernetes/base/namespaces.yaml"
echo "✅ Namespaces created"

# Step 3: Setup RBAC
echo ""
echo "=== Step 3: Setting up RBAC ==="
kubectl apply -f "$PROJECT_ROOT/infrastructure/kubernetes/base/rbac/"
echo "✅ RBAC configured"

# Step 4: Install Ingress Controller
echo ""
echo "=== Step 4: Installing Nginx Ingress Controller ==="
"$SCRIPT_DIR/setup-ingress.sh"

# Step 5: Install Cert-Manager
echo ""
echo "=== Step 5: Installing Cert-Manager ==="
"$SCRIPT_DIR/setup-cert-manager.sh"

# Summary
echo ""
echo "🎉 Kubernetes infrastructure setup complete!"
echo ""
echo "📋 Summary:"
echo "  ✅ k3d cluster created"
echo "  ✅ Namespaces created"
echo "  ✅ RBAC configured"
echo "  ✅ Nginx Ingress Controller installed"
echo "  ✅ Cert-Manager installed"
echo ""
echo "📝 Next steps:"
echo "  1. Check cluster status:"
echo "     kubectl get nodes"
echo ""
echo "  2. Check namespaces:"
echo "     kubectl get namespaces"
echo ""
echo "  3. Check ingress controller:"
echo "     kubectl get svc -n ingress-nginx"
echo ""
echo "  4. Check cert-manager:"
echo "     kubectl get pods -n cert-manager"
echo ""
echo "  5. Deploy services:"
echo "     kubectl apply -f infrastructure/kubernetes/base/"

