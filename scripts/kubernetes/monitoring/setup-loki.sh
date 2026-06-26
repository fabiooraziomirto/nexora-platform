#!/bin/bash
# Setup script for Loki (Log Aggregation)

set -e

echo "📝 Setting up Loki for log aggregation"

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

# Install Loki using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing Loki using Helm..."
    
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update
    
    helm install loki grafana/loki \
        --namespace nxr-monitoring \
        --set loki.replicas=1 \
        --set persistence.enabled=true \
        --set persistence.storageClassName=local-path \
        --set persistence.size=10Gi \
        --wait
    
    echo "✅ Loki installed via Helm"
    
    # Install Promtail for log collection
    echo "📦 Installing Promtail for log collection..."
    helm install promtail grafana/promtail \
        --namespace nxr-monitoring \
        --set promtail.config.clients[0].url=http://loki:3100/loki/api/v1/push \
        --wait
    
    echo "✅ Promtail installed via Helm"
else
    echo "❌ Helm is required for Loki installation"
    exit 1
fi

# Apply Loki configuration
echo "📝 Applying Loki configuration..."
kubectl apply -f infrastructure/kubernetes/monitoring/loki/ || true

# Verify installation
echo ""
echo "📋 Loki Status:"
kubectl get pods -n nxr-monitoring | grep -E "loki|promtail"

echo ""
echo "✅ Loki setup complete!"
echo ""
echo "Loki is now available for log aggregation."
echo "Logs are automatically collected by Promtail from all pods."

