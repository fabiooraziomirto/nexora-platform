#!/bin/bash
set -euo pipefail

BACKUP_FILE="${1:-/tmp/stack4things-backup.sql}"

echo "Creating MySQL backup to ${BACKUP_FILE}"
docker exec stack4things-mysql sh -lc "mysqldump -ustack4things -pstack4things stack4things" > "${BACKUP_FILE}"

echo "Restoring backup into stack4things database"
cat "${BACKUP_FILE}" | docker exec -i stack4things-mysql sh -lc "mysql -ustack4things -pstack4things stack4things"

echo "Validating restore"
docker exec stack4things-mysql sh -lc "mysql -ustack4things -pstack4things -e 'SELECT 1' stack4things" >/dev/null
echo "Backup/restore validation completed"
