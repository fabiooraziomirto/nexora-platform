#!/bin/bash
# Setup script for Tempo (Distributed Tracing)

set -e

echo "🔍 Setting up Tempo for distributed tracing"

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
kubectl create namespace stack4things-monitoring --dry-run=client -o yaml | kubectl apply -f -

# Install Tempo using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing Tempo using Helm..."
    
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update
    
    helm install tempo grafana/tempo-distributed \
        --namespace stack4things-monitoring \
        --set tempo.tempo.queryFrontend.replicas=1 \
        --set tempo.tempo.ingester.replicas=1 \
        --set tempo.tempo.compactor.replicas=1 \
        --set tempo.tempo.distributor.replicas=1 \
        --set tempo.tempo.querier.replicas=1 \
        --set storageSize=10Gi \
        --set storageClassName=local-path \
        --wait
    
    echo "✅ Tempo installed via Helm"
else
    echo "❌ Helm is required for Tempo installation"
    exit 1
fi

# Apply Tempo configuration
echo "📝 Applying Tempo configuration..."
kubectl apply -f infrastructure/kubernetes/monitoring/tempo/ || true

# Verify installation
echo ""
echo "📋 Tempo Status:"
kubectl get pods -n stack4things-monitoring | grep tempo

echo ""
echo "✅ Tempo setup complete!"
echo ""
echo "Tempo is now available for distributed tracing."
echo "Configure your services to send traces to: tempo-distributed-distributor.stack4things-monitoring:4317"

