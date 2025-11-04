#!/bin/bash
# Setup script for Redis Cluster

set -e

echo "🔴 Setting up Redis Cluster for Stack4Things v2.0"

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
kubectl create namespace stack4things-infrastructure --dry-run=client -o yaml | kubectl apply -f -

# Install Redis Cluster using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing Redis Cluster using Helm..."
    
    helm repo add bitnami https://charts.bitnami.com/bitnami
    helm repo update
    
    # Install Redis with cluster mode and persistence
    helm install redis bitnami/redis \
        --namespace stack4things-infrastructure \
        --set architecture=replication \
        --set auth.enabled=true \
        --set auth.password=redispassword \
        --set master.persistence.enabled=true \
        --set master.persistence.storageClass=local-path \
        --set master.persistence.size=10Gi \
        --set replica.replicaCount=3 \
        --set replica.persistence.enabled=true \
        --set replica.persistence.storageClass=local-path \
        --set replica.persistence.size=10Gi \
        --set sentinel.enabled=true \
        --set sentinel.quorum=2 \
        --set metrics.enabled=true \
        --set metrics.serviceMonitor.enabled=true \
        --set metrics.serviceMonitor.namespace=stack4things-monitoring \
        --wait
    
    echo "✅ Redis Cluster installed via Helm"
else
    echo "❌ Helm is required for Redis Cluster installation"
    echo "Please install Helm: https://helm.sh/docs/intro/install/"
    exit 1
fi

# Apply Redis custom resources
echo "📝 Applying Redis custom resources..."
kubectl apply -f infrastructure/kubernetes/redis/ || true

# Get Redis password
REDIS_PASSWORD=$(kubectl get secret --namespace stack4things-infrastructure redis -o jsonpath="{.data.redis-password}" | base64 -d)

# Verify installation
echo ""
echo "📋 Redis Cluster Status:"
kubectl get pods -n stack4things-infrastructure | grep redis

echo ""
echo "✅ Redis Cluster setup complete!"
echo ""
echo "📋 Redis Connection Info:"
echo "  Host: redis-master.stack4things-infrastructure.svc.cluster.local"
echo "  Port: 6379"
echo "  Password: $REDIS_PASSWORD"
echo "  Sentinel: redis-sentinel.stack4things-infrastructure.svc.cluster.local:26379"
echo ""
echo "📝 Connection String:"
echo "  redis://:$REDIS_PASSWORD@redis-master.stack4things-infrastructure.svc.cluster.local:6379"
echo ""
echo "💡 Redis Sentinel is enabled for HA"
echo "💡 Persistence is enabled with 10Gi storage"

