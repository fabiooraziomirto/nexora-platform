#!/bin/bash
# Setup script for MySQL backup automation

set -e

echo "💾 Setting up MySQL backup automation"

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

# Check if MySQL/MariaDB is installed
if ! kubectl get svc mariadb -n stack4things-infrastructure &> /dev/null; then
    echo "⚠️  MySQL/MariaDB not found. Installing it first..."
    ./scripts/kubernetes/database/setup-mysql.sh
fi

# Apply backup CronJob
echo "📝 Applying backup CronJob..."
kubectl apply -f infrastructure/kubernetes/database/backup/

# Verify installation
echo ""
echo "📋 Backup CronJob Status:"
kubectl get cronjob -n stack4things-infrastructure | grep mysql-backup

echo ""
echo "✅ MySQL backup automation setup complete!"
echo ""
echo "📋 Backup Configuration:"
echo "  Schedule: Daily at 2:00 AM"
echo "  Retention: 7 days"
echo "  Storage: PVC (mysql-backup-storage)"
echo ""
echo "🔍 Check backups:"
echo "  kubectl get cronjob mysql-backup -n stack4things-infrastructure"
echo "  kubectl get pvc mysql-backup-storage -n stack4things-infrastructure"
echo ""
echo "📥 Restore backup:"
echo "  ./scripts/kubernetes/database/restore-backup.sh <backup-file>"

