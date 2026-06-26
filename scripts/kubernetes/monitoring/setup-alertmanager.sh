#!/bin/bash
# Setup script for Alertmanager

set -e

echo "🚨 Setting up Alertmanager"

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
kubectl create namespace nxr-monitoring --dry-run=client -o yaml | kubectl apply -f -

# Alertmanager is usually installed with Prometheus Operator
echo "📦 Checking if Alertmanager is already installed..."
if ! kubectl get deployment alertmanager -n nxr-monitoring &> /dev/null; then
    echo "⚠️  Alertmanager should be installed with Prometheus Operator"
    echo "Running Prometheus Operator setup..."
    ./scripts/kubernetes/monitoring/setup-prometheus.sh
else
    echo "✅ Alertmanager already installed"
fi

# Apply Alertmanager configuration
echo "📝 Applying Alertmanager configuration..."
kubectl apply -f infrastructure/kubernetes/monitoring/alertmanager/ || true

# Verify installation
echo ""
echo "📋 Alertmanager Status:"
kubectl get pods -n nxr-monitoring | grep alertmanager

echo ""
echo "✅ Alertmanager setup complete!"
echo ""
echo "Access Alertmanager UI:"
echo "  kubectl port-forward -n nxr-monitoring svc/alertmanager-operated 9093:9093"
echo "  Open http://localhost:9093"

