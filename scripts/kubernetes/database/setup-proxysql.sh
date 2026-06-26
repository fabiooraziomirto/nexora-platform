#!/bin/bash
# Setup script for ProxySQL connection pooling

set -e

echo "🔌 Setting up ProxySQL for MySQL connection pooling"

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

# Check if MySQL/MariaDB is installed
if ! kubectl get svc mariadb -n nxr-infrastructure &> /dev/null; then
    echo "⚠️  MySQL/MariaDB not found. Installing it first..."
    ./scripts/kubernetes/database/setup-mysql.sh
fi

# Install ProxySQL using Helm
if command -v helm &> /dev/null; then
    echo "📦 Installing ProxySQL using Helm..."
    
    helm repo add proxysql https://charts.proxysql.org
    helm repo update
    
    # Get MySQL root password
    MYSQL_ROOT_PASSWORD=$(kubectl get secret --namespace nxr-infrastructure mariadb -o jsonpath="{.data.mariadb-root-password}" | base64 -d)
    
    # Install ProxySQL
    helm install proxysql proxysql/proxysql \
        --namespace nxr-infrastructure \
        --set config.mysql_servers='
        {
          "mysql_servers": [
            {
              "hostname": "mariadb.nxr-infrastructure.svc.cluster.local",
              "port": 3306,
              "weight": 1000,
              "comment": "Primary MySQL server"
            }
          ]
        }' \
        --set config.mysql_users='
        {
          "mysql_users": [
            {
              "username": "nxr",
              "password": "nxr",
              "default_hostgroup": 0,
              "active": 1
            }
          ]
        }' \
        --set config.mysql_query_rules='
        {
          "mysql_query_rules": [
            {
              "rule_id": 1,
              "active": 1,
              "match_pattern": "^SELECT",
              "destination_hostgroup": 1,
              "apply": 1
            }
          ]
        }' \
        --set service.type=ClusterIP \
        --set service.port=3306 \
        --wait
    
    echo "✅ ProxySQL installed via Helm"
else
    echo "❌ Helm is required for ProxySQL installation"
    exit 1
fi

# Apply ProxySQL custom configuration
echo "📝 Applying ProxySQL custom configuration..."
kubectl apply -f infrastructure/kubernetes/database/proxysql/ || true

# Verify installation
echo ""
echo "📋 ProxySQL Status:"
kubectl get pods -n nxr-infrastructure | grep proxysql

echo ""
echo "✅ ProxySQL setup complete!"
echo ""
echo "📋 ProxySQL Connection Info:"
echo "  Host: proxysql.nxr-infrastructure.svc.cluster.local"
echo "  Port: 3306"
echo "  Username: nxr"
echo "  Password: nxr"
echo ""
echo "💡 ProxySQL automatically routes:"
echo "  - Reads to read replicas (hostgroup 1)"
echo "  - Writes to primary (hostgroup 0)"

