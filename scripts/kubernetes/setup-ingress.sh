#!/bin/bash
# Setup script for Nginx Ingress Controller

set -e

echo "🌐 Setting up Nginx Ingress Controller"

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
kubectl create namespace ingress-nginx --dry-run=client -o yaml | kubectl apply -f -

# Install Nginx Ingress Controller using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing Nginx Ingress Controller using Helm..."
    
    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
    helm repo update
    
    helm install ingress-nginx ingress-nginx/ingress-nginx \
        --namespace ingress-nginx \
        --set controller.service.type=LoadBalancer \
        --set controller.admissionWebhooks.enabled=false \
        --set controller.metrics.enabled=true \
        --set controller.podSecurityPolicy.enabled=false \
        --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"="nlb" \
        --wait
    
    echo "✅ Nginx Ingress Controller installed via Helm"
else
    echo "📦 Installing Nginx Ingress Controller using kubectl..."
    
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.2/deploy/static/provider/cloud/deploy.yaml
    
    echo "⏳ Waiting for Nginx Ingress Controller to be ready..."
    kubectl wait --namespace ingress-nginx \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/component=controller \
        --timeout=300s
    
    echo "✅ Nginx Ingress Controller installed via kubectl"
fi

# Get ingress controller IP
echo ""
echo "📋 Ingress Controller Status:"
kubectl get svc -n ingress-nginx ingress-nginx-controller

echo ""
echo "✅ Nginx Ingress Controller setup complete!"
echo ""
echo "You can now create Ingress resources in the stack4things namespace."

