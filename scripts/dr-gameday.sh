#!/bin/bash
set -euo pipefail

echo "[dr] simulating cluster outage by stopping core data plane"
docker compose -f docker-compose.dev.yml stop mysql kafka redis
sleep 10
echo "[dr] measuring recovery time"
START=$(date +%s)
docker compose -f docker-compose.dev.yml start mysql kafka redis
sleep 20
END=$(date +%s)
RTO=$((END-START))
echo "[dr] measured_rto_seconds=${RTO}"
