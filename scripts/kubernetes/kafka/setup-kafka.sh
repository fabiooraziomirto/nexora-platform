#!/bin/bash
# Setup script for Kafka cluster

set -e

echo "📨 Setting up Kafka cluster for Nxr v2.0"

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
kubectl create namespace nxr-infrastructure --dry-run=client -o yaml | kubectl apply -f -

# Install Kafka using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing Kafka using Helm..."
    
    helm repo add bitnami https://charts.bitnami.com/bitnami
    helm repo update
    
    # Install Kafka with Zookeeper
    helm install kafka bitnami/kafka \
        --namespace nxr-infrastructure \
        --set replicas=3 \
        --set persistence.enabled=true \
        --set persistence.storageClass=local-path \
        --set persistence.size=20Gi \
        --set zookeeper.enabled=true \
        --set zookeeper.replicaCount=3 \
        --set zookeeper.persistence.enabled=true \
        --set zookeeper.persistence.storageClass=local-path \
        --set zookeeper.persistence.size=10Gi \
        --set metrics.kafka.enabled=true \
        --set metrics.kafka.serviceMonitor.enabled=true \
        --set metrics.kafka.serviceMonitor.namespace=nxr-monitoring \
        --set metrics.jmx.enabled=true \
        --set metrics.jmx.serviceMonitor.enabled=true \
        --set metrics.jmx.serviceMonitor.namespace=nxr-monitoring \
        --wait
    
    echo "✅ Kafka cluster installed via Helm"
else
    echo "❌ Helm is required for Kafka installation"
    echo "Please install Helm: https://helm.sh/docs/intro/install/"
    exit 1
fi

# Apply Kafka custom resources
echo "📝 Applying Kafka custom resources..."
kubectl apply -f infrastructure/kubernetes/kafka/ || true

# Wait for Kafka to be ready
echo "⏳ Waiting for Kafka to be ready..."
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=kafka \
    -n nxr-infrastructure \
    --timeout=300s

# Create base topics
echo "📝 Creating base Kafka topics..."
./scripts/kubernetes/kafka/create-topics.sh

# Verify installation
echo ""
echo "📋 Kafka Cluster Status:"
kubectl get pods -n nxr-infrastructure | grep kafka

echo ""
echo "✅ Kafka cluster setup complete!"
echo ""
echo "📋 Kafka Connection Info:"
echo "  Bootstrap Servers: kafka.nxr-infrastructure.svc.cluster.local:9092"
echo "  Zookeeper: kafka-zookeeper.nxr-infrastructure.svc.cluster.local:2181"
echo ""
echo "📝 Next steps:"
echo "  1. List topics:"
echo "     kubectl exec -it kafka-0 -n nxr-infrastructure -- kafka-topics.sh --list --bootstrap-server localhost:9092"
echo ""
echo "  2. Create custom topic:"
echo "     kubectl exec -it kafka-0 -n nxr-infrastructure -- kafka-topics.sh --create --topic my-topic --bootstrap-server localhost:9092 --partitions 3 --replication-factor 3"

