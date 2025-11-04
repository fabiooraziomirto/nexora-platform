#!/bin/bash
# Setup script for Grafana

set -e

echo "📈 Setting up Grafana"

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

# Install Grafana using Helm (usually comes with Prometheus Operator)
if command -v helm &> /dev/null; then
    echo "📦 Checking if Grafana is already installed..."
    
    if ! kubectl get deployment grafana -n stack4things-monitoring &> /dev/null; then
        echo "📦 Installing Grafana using Helm..."
        
        helm repo add grafana https://grafana.github.io/helm-charts
        helm repo update
        
        helm install grafana grafana/grafana \
            --namespace stack4things-monitoring \
            --set adminPassword=admin \
            --set persistence.enabled=true \
            --set persistence.storageClassName=local-path \
            --set persistence.size=5Gi \
            --set service.type=LoadBalancer \
            --set service.port=80 \
            --wait
        
        echo "✅ Grafana installed via Helm"
    else
        echo "✅ Grafana already installed"
    fi
else
    echo "❌ Helm is required for Grafana installation"
    exit 1
fi

# Apply Grafana dashboards and datasources
echo "📝 Applying Grafana dashboards and datasources..."
kubectl apply -f infrastructure/kubernetes/monitoring/grafana/ || true

# Get Grafana admin password
echo ""
echo "📋 Grafana Status:"
kubectl get pods -n stack4things-monitoring | grep grafana

echo ""
echo "✅ Grafana setup complete!"
echo ""
echo "Access Grafana UI:"
echo "  kubectl port-forward -n stack4things-monitoring svc/grafana 3000:80"
echo "  Open http://localhost:3000"
echo "  Username: admin"
echo "  Password: admin (change on first login)"

