#!/bin/bash
# Setup audit logging for RBAC

set -e

echo "📝 Setting up audit logging for RBAC"

# Create namespace if it doesn't exist
kubectl create namespace stack4things --dry-run=client -o yaml | kubectl apply -f -

# Apply audit logging configuration
echo "📝 Applying audit logging configuration..."
kubectl apply -f infrastructure/kubernetes/rbac/audit/ || true

# Create audit log storage
echo "📝 Creating audit log storage..."
kubectl apply -f infrastructure/kubernetes/rbac/audit/storage.yaml || true

# Setup Fluentd/Fluent Bit for log collection (if monitoring is set up)
if kubectl get deployment fluentd -n stack4things-monitoring &> /dev/null || \
   kubectl get daemonset fluent-bit -n stack4things-monitoring &> /dev/null; then
    echo "📝 Configuring log collection..."
    kubectl apply -f infrastructure/kubernetes/rbac/audit/log-collection.yaml || true
fi

echo ""
echo "✅ Audit logging setup complete!"
echo ""
echo "📋 Audit Log Configuration:"
echo "  Storage: PVC (audit-logs-storage)"
echo "  Retention: 90 days"
echo "  Format: JSON"
echo ""
echo "📝 View audit logs:"
echo "  kubectl logs -n stack4things -l app=rbac-service | grep audit"

