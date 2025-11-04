#!/bin/bash
# Setup script for MySQL/MariaDB HA (OpenStack Compatible)

set -e

echo "🗄️  Setting up MySQL/MariaDB HA for Stack4Things v2.0"

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

# Install MySQL/MariaDB using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing MariaDB using Helm..."
    
    helm repo add bitnami https://charts.bitnami.com/bitnami
    helm repo update
    
    # Install MariaDB with HA configuration
    helm install mariadb bitnami/mariadb \
        --namespace stack4things-infrastructure \
        --set architecture=replication \
        --set auth.rootPassword=rootpassword \
        --set auth.database=stack4things \
        --set auth.username=stack4things \
        --set auth.password=stack4things \
        --set primary.persistence.enabled=true \
        --set primary.persistence.storageClass=local-path \
        --set primary.persistence.size=20Gi \
        --set secondary.replicaCount=2 \
        --set secondary.persistence.enabled=true \
        --set secondary.persistence.storageClass=local-path \
        --set secondary.persistence.size=20Gi \
        --set service.type=ClusterIP \
        --set primary.service.type=ClusterIP \
        --set metrics.enabled=true \
        --set metrics.serviceMonitor.enabled=true \
        --set metrics.serviceMonitor.namespace=stack4things-monitoring \
        --wait
    
    echo "✅ MariaDB HA installed via Helm"
else
    echo "❌ Helm is required for MySQL/MariaDB HA installation"
    echo "Please install Helm: https://helm.sh/docs/intro/install/"
    exit 1
fi

# Apply MySQL custom resources
echo "📝 Applying MySQL custom resources..."
kubectl apply -f infrastructure/kubernetes/database/mysql/ || true

# Wait for MySQL to be ready
echo "⏳ Waiting for MySQL to be ready..."
kubectl wait --for=condition=ready pod \
    -l app.kubernetes.io/name=mariadb \
    -n stack4things-infrastructure \
    --timeout=300s

# Get MySQL root password
MYSQL_ROOT_PASSWORD=$(kubectl get secret --namespace stack4things-infrastructure mariadb -o jsonpath="{.data.mariadb-root-password}" | base64 -d)

echo ""
echo "✅ MySQL/MariaDB HA setup complete!"
echo ""
echo "📋 MySQL Connection Info:"
echo "  Host: mariadb.stack4things-infrastructure.svc.cluster.local"
echo "  Port: 3306"
echo "  Database: stack4things"
echo "  Username: stack4things"
echo "  Password: stack4things"
echo "  Root Password: $MYSQL_ROOT_PASSWORD"
echo ""
echo "📝 Next steps:"
echo "  1. Setup ProxySQL for connection pooling:"
echo "     ./scripts/kubernetes/database/setup-proxysql.sh"
echo ""
echo "  2. Setup backup automation:"
echo "     ./scripts/kubernetes/database/setup-backup.sh"
echo ""
echo "  3. Run database migrations:"
echo "     cd services/device-service && poetry run alembic upgrade head"

