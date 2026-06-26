#!/usr/bin/env bash
set -euo pipefail

HORIZON_API_DIR=${HORIZON_API_DIR:-/usr/share/openstack-dashboard/openstack_dashboard/api}
HORIZON_ENABLED_DIR=${HORIZON_ENABLED_DIR:-/usr/share/openstack-dashboard/openstack_dashboard/enabled}

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -d "$HORIZON_API_DIR" ] || [ ! -d "$HORIZON_ENABLED_DIR" ]; then
  echo "[ERROR] Horizon paths not found."
  echo "Set HORIZON_API_DIR and HORIZON_ENABLED_DIR then re-run."
  exit 1
fi

echo "[INFO] Copying Nxr IoTronic adapter..."
cp "$SRC_ROOT/nexora_dashboard/api/nexora.py" "$HORIZON_API_DIR/nexora.py"
cp "$SRC_ROOT/nexora_dashboard/enabled/_60"* "$HORIZON_ENABLED_DIR/"

echo "[INFO] Done. Remember to set env vars for Apache/uWSGI:"
echo "  S4T_DEVICE_URL=http://localhost:8000"
echo "  S4T_PLUGIN_URL=http://localhost:8001"
echo "  S4T_EXECUTION_URL=http://localhost:8002"
echo "  S4T_NETWORK_URL=http://localhost:8003"
echo "  S4T_DNS_URL=http://localhost:8004"
echo "  S4T_WEBSERVICE_URL=http://localhost:8005"
echo "  S4T_FLEET_URL=http://localhost:8006"
echo "  S4T_AUTH_TOKEN=<optional bearer token>"

echo "[INFO] Restart horizon web server (apache/httpd)."
