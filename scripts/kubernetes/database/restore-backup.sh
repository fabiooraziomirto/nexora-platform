#!/bin/bash
# Restore MySQL backup script

set -e

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "❌ Usage: $0 <backup-file>"
    echo "Example: $0 mysql-backup-2024-01-01-020000.sql.gz"
    exit 1
fi

echo "📥 Restoring MySQL backup: $BACKUP_FILE"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is required but not installed."
    exit 1
fi

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Get MySQL root password
MYSQL_ROOT_PASSWORD=$(kubectl get secret --namespace nxr-infrastructure mariadb -o jsonpath="{.data.mariadb-root-password}" | base64 -d)

# Copy backup file to a pod
echo "📋 Copying backup file to MySQL pod..."
POD_NAME=$(kubectl get pods -n nxr-infrastructure -l app.kubernetes.io/name=mariadb -o jsonpath='{.items[0].metadata.name}')
kubectl cp "$BACKUP_FILE" "nxr-infrastructure/$POD_NAME:/tmp/backup.sql.gz"

# Restore backup
echo "🔄 Restoring backup..."
if [[ "$BACKUP_FILE" == *.gz ]]; then
    kubectl exec -n nxr-infrastructure "$POD_NAME" -- \
        bash -c "gunzip -c /tmp/backup.sql.gz | mysql -uroot -p$MYSQL_ROOT_PASSWORD nxr"
else
    kubectl exec -n nxr-infrastructure "$POD_NAME" -- \
        bash -c "mysql -uroot -p$MYSQL_ROOT_PASSWORD nxr < /tmp/backup.sql"
fi

# Cleanup
kubectl exec -n nxr-infrastructure "$POD_NAME" -- \
    rm -f /tmp/backup.sql.gz /tmp/backup.sql

echo "✅ Backup restored successfully!"

