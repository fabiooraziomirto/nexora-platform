#!/bin/bash
# Setup script for Prometheus Operator

set -e

echo "📊 Setting up Prometheus Operator"

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

# Install Prometheus Operator using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing Prometheus Operator using Helm..."
    
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    
    helm install prometheus prometheus-community/kube-prometheus-stack \
        --namespace stack4things-monitoring \
        --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
        --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false \
        --set prometheus.prometheusSpec.ruleSelectorNilUsesHelmValues=false \
        --set prometheusOperator.admissionWebhooks.enabled=false \
        --set alertmanager.alertmanagerSpec.replicas=1 \
        --set prometheus.prometheusSpec.replicas=1 \
        --set prometheus.prometheusSpec.retention=30d \
        --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.storageClassName=local-path \
        --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=10Gi \
        --wait
    
    echo "✅ Prometheus Operator installed via Helm"
else
    echo "❌ Helm is required for Prometheus Operator installation"
    echo "Please install Helm: https://helm.sh/docs/intro/install/"
    exit 1
fi

# Apply Prometheus custom resources
echo "📝 Applying Prometheus custom resources..."
kubectl apply -f infrastructure/kubernetes/monitoring/prometheus/ || true

# Verify installation
echo ""
echo "📋 Prometheus Operator Status:"
kubectl get pods -n stack4things-monitoring | grep prometheus

echo ""
echo "✅ Prometheus Operator setup complete!"
echo ""
echo "Access Prometheus UI:"
echo "  kubectl port-forward -n stack4things-monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090"
echo "  Open http://localhost:9090"

