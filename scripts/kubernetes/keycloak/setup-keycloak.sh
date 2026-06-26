#!/bin/bash
# Setup script for Keycloak in Kubernetes

set -e

echo "🔐 Setting up Keycloak for Nxr v2.0"

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
kubectl create namespace nxr-auth --dry-run=client -o yaml | kubectl apply -f -

# Install Keycloak using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing Keycloak using Helm..."
    
    helm repo add bitnami https://charts.bitnami.com/bitnami
    helm repo update
    
    # Get admin password from secret or generate new
    ADMIN_PASSWORD=$(kubectl get secret keycloak-secrets -n nxr-auth -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d || openssl rand -base64 32)
    
    # Install Keycloak
    helm install keycloak bitnami/keycloak \
        --namespace nxr-auth \
        --set auth.adminUser=admin \
        --set auth.adminPassword="$ADMIN_PASSWORD" \
        --set persistence.enabled=true \
        --set persistence.storageClass=local-path \
        --set persistence.size=10Gi \
        --set postgresql.enabled=true \
        --set postgresql.auth.postgresPassword="$(openssl rand -base64 32)" \
        --set postgresql.auth.database=keycloak \
        --set postgresql.persistence.enabled=true \
        --set postgresql.persistence.storageClass=local-path \
        --set postgresql.persistence.size=10Gi \
        --set service.type=ClusterIP \
        --set metrics.enabled=true \
        --wait
    
    echo "✅ Keycloak installed via Helm"
else
    echo "❌ Helm is required for Keycloak installation"
    echo "Please install Helm: https://helm.sh/docs/intro/install/"
    exit 1
fi

# Wait for Keycloak to be ready
echo "⏳ Waiting for Keycloak to be ready..."
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=keycloak \
    -n nxr-auth \
    --timeout=300s

# Apply Keycloak configuration
echo "📝 Applying Keycloak configuration..."
kubectl apply -f infrastructure/kubernetes/keycloak/ || true

# Configure realm
echo "📝 Configuring Keycloak realm..."
./scripts/kubernetes/keycloak/configure-realm.sh

# Verify installation
echo ""
echo "📋 Keycloak Status:"
kubectl get pods -n nxr-auth | grep keycloak

echo ""
echo "✅ Keycloak setup complete!"
echo ""
echo "📋 Keycloak Info:"
echo "  Namespace: nxr-auth"
echo "  Service: keycloak.nxr-auth.svc.cluster.local:8080"
echo "  Admin Username: admin"
echo "  Admin Password: $ADMIN_PASSWORD"
echo ""
echo "📝 Access Keycloak Admin Console:"
echo "  kubectl port-forward -n nxr-auth svc/keycloak 8080:8080"
echo "  Open http://localhost:8080"
echo "  Username: admin"
echo "  Password: $ADMIN_PASSWORD"
echo ""
echo "📝 Next steps:"
echo "  1. Configure Keystone Identity Broker:"
echo "     ./scripts/kubernetes/keycloak/configure-keystone-broker.sh"
echo ""
echo "  2. Setup API Gateway dual auth:"
echo "     ./scripts/kubernetes/keycloak/configure-api-gateway.sh"

