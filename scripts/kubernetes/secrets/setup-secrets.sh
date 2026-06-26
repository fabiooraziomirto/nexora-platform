#!/bin/bash
# Setup script for Kubernetes Secrets

set -e

echo "🔐 Setting up Kubernetes Secrets for Nxr v2.0"

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

# Create namespaces if they don't exist
kubectl create namespace nxr --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace nxr-infrastructure --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace nxr-auth --dry-run=client -o yaml | kubectl apply -f -

# Function to generate random password
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

# Generate passwords if not set
DB_PASSWORD=${DB_PASSWORD:-$(generate_password)}
REDIS_PASSWORD=${REDIS_PASSWORD:-$(generate_password)}
KAFKA_PASSWORD=${KAFKA_PASSWORD:-$(generate_password)}
JWT_SECRET=${JWT_SECRET:-$(openssl rand -hex 32)}
ENCRYPTION_KEY=${ENCRYPTION_KEY:-$(openssl rand -hex 32)}

echo "📝 Creating base secrets..."

# Database secrets
kubectl create secret generic mysql-credentials \
    --from-literal=username=nxr \
    --from-literal=password="$DB_PASSWORD" \
    --from-literal=database=nxr \
    --namespace=nxr-infrastructure \
    --dry-run=client -o yaml | kubectl apply -f -

# Redis secrets
kubectl create secret generic redis-credentials \
    --from-literal=password="$REDIS_PASSWORD" \
    --namespace=nxr-infrastructure \
    --dry-run=client -o yaml | kubectl apply -f -

# Kafka secrets (if needed)
kubectl create secret generic kafka-credentials \
    --from-literal=username=kafka \
    --from-literal=password="$KAFKA_PASSWORD" \
    --namespace=nxr-infrastructure \
    --dry-run=client -o yaml | kubectl apply -f -

# Application secrets
kubectl create secret generic app-secrets \
    --from-literal=jwt-secret="$JWT_SECRET" \
    --from-literal=encryption-key="$ENCRYPTION_KEY" \
    --namespace=nxr \
    --dry-run=client -o yaml | kubectl apply -f -

# API Gateway secrets
kubectl create secret generic api-gateway-secrets \
    --from-literal=jwt-secret="$JWT_SECRET" \
    --namespace=nxr \
    --dry-run=client -o yaml | kubectl apply -f -

# Keycloak secrets
kubectl create secret generic keycloak-secrets \
    --from-literal=admin-password="$(generate_password)" \
    --namespace=nxr-auth \
    --dry-run=client -o yaml | kubectl apply -f -

# Apply secret templates
echo "📝 Applying secret templates..."
kubectl apply -f infrastructure/kubernetes/secrets/ || true

echo ""
echo "✅ Kubernetes Secrets setup complete!"
echo ""
echo "📋 Created Secrets:"
echo "  - mysql-credentials (nxr-infrastructure)"
echo "  - redis-credentials (nxr-infrastructure)"
echo "  - kafka-credentials (nxr-infrastructure)"
echo "  - app-secrets (nxr)"
echo "  - api-gateway-secrets (nxr)"
echo "  - keycloak-secrets (nxr-auth)"
echo ""
echo "💡 To view secrets:"
echo "  kubectl get secrets -n nxr-infrastructure"
echo "  kubectl get secret mysql-credentials -n nxr-infrastructure -o yaml"
echo ""
echo "💡 To update a secret:"
echo "  kubectl create secret generic mysql-credentials --from-literal=password=newpassword --dry-run=client -o yaml | kubectl apply -f -"

