#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "[postalpha] starting docker stack (smoke profile)"
docker compose -f docker-compose.dev.yml -f docker-compose.smoke.yml up -d --build

cleanup() {
  echo "[postalpha] tearing down stack"
  docker compose -f docker-compose.dev.yml -f docker-compose.smoke.yml down -v || true
}
trap cleanup EXIT

echo "[postalpha] waiting services"
sleep 15

echo "[postalpha] health checks"
curl -fsS http://localhost:8000/health >/dev/null
curl -fsS http://localhost:8001/health >/dev/null
curl -fsS http://localhost:8002/health >/dev/null
curl -fsS http://localhost:8003/health >/dev/null
curl -fsS http://localhost:8004/health >/dev/null
curl -fsS http://localhost:8005/health >/dev/null
curl -fsS http://localhost:8006/health >/dev/null

echo "[postalpha] running contract tests"
python3 scripts/contract-tests-api.py

echo "[postalpha] running cross-service flow"
bash scripts/integration-cross-service.sh

echo "[postalpha] running chaos drill"
bash scripts/chaos-drill.sh

echo "[postalpha] running backup/restore validation"
bash scripts/backup-restore-validate.sh /tmp/nxr-backup.sql

echo "[postalpha] all post-alpha validations completed"
