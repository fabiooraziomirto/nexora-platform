#!/bin/bash
# Setup script for Cert-Manager

set -e

echo "🔒 Setting up Cert-Manager for SSL certificates"

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
kubectl create namespace cert-manager --dry-run=client -o yaml | kubectl apply -f -

# Install Cert-Manager using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing Cert-Manager using Helm..."
    
    helm repo add jetstack https://charts.jetstack.io
    helm repo update
    
    # Install cert-manager CRDs first
    kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.crds.yaml
    
    # Install cert-manager
    helm install cert-manager jetstack/cert-manager \
        --namespace cert-manager \
        --set installCRDs=false \
        --set global.leaderElection.namespace=cert-manager \
        --wait
    
    echo "✅ Cert-Manager installed via Helm"
else
    echo "📦 Installing Cert-Manager using kubectl..."
    
    # Install cert-manager CRDs
    kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.crds.yaml
    
    # Install cert-manager
    kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.yaml
    
    echo "⏳ Waiting for Cert-Manager to be ready..."
    kubectl wait --namespace cert-manager \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/instance=cert-manager \
        --timeout=300s
    
    echo "✅ Cert-Manager installed via kubectl"
fi

# Create ClusterIssuer for Let's Encrypt (staging)
echo "📝 Creating Let's Encrypt Staging ClusterIssuer..."
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: admin@nxr.io
    privateKeySecretRef:
      name: letsencrypt-staging
    solvers:
      - http01:
          ingress:
            class: nginx
EOF

# Create ClusterIssuer for Let's Encrypt (production)
echo "📝 Creating Let's Encrypt Production ClusterIssuer..."
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@nxr.io
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
EOF

# Verify installation
echo ""
echo "📋 Cert-Manager Status:"
kubectl get pods -n cert-manager
kubectl get clusterissuers

echo ""
echo "✅ Cert-Manager setup complete!"
echo ""
echo "Available ClusterIssuers:"
echo "  - letsencrypt-staging: For testing (has rate limits)"
echo "  - letsencrypt-prod: For production (limited rate limits)"
echo ""
echo "Example Certificate usage:"
echo "  kubectl apply -f infrastructure/kubernetes/base/cert-manager/example-certificate.yaml"

