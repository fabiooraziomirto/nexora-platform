#!/bin/bash
set -euo pipefail

BASE_DEVICE_URL="${BASE_DEVICE_URL:-http://localhost:8000}"
BASE_NETWORK_URL="${BASE_NETWORK_URL:-http://localhost:8003}"
BASE_DNS_URL="${BASE_DNS_URL:-http://localhost:8004}"
BASE_WEBSERVICE_URL="${BASE_WEBSERVICE_URL:-http://localhost:8005}"

echo "Running cross-service integration flow: device -> network -> dns -> webservice"

device_id=$(
  curl -fsS -X POST "${BASE_DEVICE_URL}/api/v2/devices" \
    -H "Content-Type: application/json" \
    -d '{"name":"flow-device","device_type":"sensor","description":"integration-flow"}' \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])'
)
echo "Created device: ${device_id}"
curl -fsS "${BASE_DEVICE_URL}/api/v2/devices/${device_id}" >/dev/null

port_id=$(
  curl -fsS -X POST "${BASE_NETWORK_URL}/api/v2/ports" \
    -H "Content-Type: application/json" \
    -d "{\"device_id\":\"${device_id}\",\"network_id\":\"flow-net\"}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])'
)
echo "Created network port: ${port_id}"
curl -fsS "${BASE_NETWORK_URL}/api/v2/ports/${port_id}" >/dev/null

record_id=$(
  curl -fsS -X POST "${BASE_DNS_URL}/api/v2/dns/records" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${device_id}.iot.local\",\"type\":\"A\",\"value\":\"10.0.0.20\"}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])'
)
echo "Created dns record: ${record_id}"
curl -fsS "${BASE_DNS_URL}/api/v2/dns/records/${record_id}" >/dev/null

webservice_id=$(
  curl -fsS -X POST "${BASE_WEBSERVICE_URL}/api/v2/webservices" \
    -H "Content-Type: application/json" \
    -d "{\"device_id\":\"${device_id}\",\"port\":8443}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])'
)
echo "Created webservice: ${webservice_id}"
curl -fsS "${BASE_WEBSERVICE_URL}/api/v2/webservices/${webservice_id}" >/dev/null

echo "Cross-service integration flow completed successfully"
