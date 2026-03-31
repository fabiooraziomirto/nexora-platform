#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADAPTER_DIR="$ROOT_DIR/tools/iotronic-ui-adapter"

HORIZON_API_DIR=${HORIZON_API_DIR:-/usr/share/openstack-dashboard/openstack_dashboard/api}
HORIZON_ENABLED_DIR=${HORIZON_ENABLED_DIR:-/usr/share/openstack-dashboard/openstack_dashboard/enabled}

if [ ! -d "$HORIZON_API_DIR" ] || [ ! -d "$HORIZON_ENABLED_DIR" ]; then
  echo "[ERROR] Horizon directories not found."
  echo "Set HORIZON_API_DIR and HORIZON_ENABLED_DIR to your Horizon install paths."
  exit 1
fi

echo "[INFO] Installing Stack4Things adapter into Horizon..."
install -m 0644 "$ADAPTER_DIR/iotronic_ui/api/iotronic.py" "$HORIZON_API_DIR/iotronic.py"

echo "[INFO] Adapter API installed: $HORIZON_API_DIR/iotronic.py"
echo "[INFO] Ensure IoTronic panel files (_60*.py) are present in: $HORIZON_ENABLED_DIR"

echo "[INFO] Recommended env vars for Horizon runtime:"
echo "  S4T_DEVICE_URL=http://localhost:8000"
echo "  S4T_PLUGIN_URL=http://localhost:8001"
echo "  S4T_NETWORK_URL=http://localhost:8003"
echo "  S4T_WEBSERVICE_URL=http://localhost:8005"
echo "  S4T_FLEET_URL=http://localhost:8006"
echo "  S4T_AUTH_TOKEN=<keycloak access token if AUTH_ENABLED=true>"
echo "  S4T_TENANT_ID=<optional tenant>"

echo "[INFO] Restart Horizon web server (apache/httpd/uwsgi)."
