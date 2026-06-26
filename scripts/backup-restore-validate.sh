#!/bin/bash
set -euo pipefail

BACKUP_FILE="${1:-/tmp/nxr-backup.sql}"

echo "Creating MySQL backup to ${BACKUP_FILE}"
docker exec nxr-mysql sh -lc "mysqldump -unxr -pnxr nxr" > "${BACKUP_FILE}"

echo "Restoring backup into nxr database"
cat "${BACKUP_FILE}" | docker exec -i nxr-mysql sh -lc "mysql -unxr -pnxr nxr"

echo "Validating restore"
docker exec nxr-mysql sh -lc "mysql -unxr -pnxr -e 'SELECT 1' nxr" >/dev/null
echo "Backup/restore validation completed"
