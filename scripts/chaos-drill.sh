#!/bin/bash
set -euo pipefail

echo "Starting chaos drill: stop kafka and verify service readiness degradation"
docker compose -f docker-compose.dev.yml stop kafka
sleep 5
curl -fsS http://localhost:8002/ready || true
curl -fsS http://localhost:8003/ready || true
echo "Recovering kafka"
docker compose -f docker-compose.dev.yml start kafka
sleep 10
curl -fsS http://localhost:8002/health >/dev/null
curl -fsS http://localhost:8003/health >/dev/null
echo "Chaos drill completed"
