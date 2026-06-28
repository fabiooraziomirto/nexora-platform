#!/usr/bin/env bash
# install-agent.sh — Install nexora-agent on a Linux ARM/x86 device.
#
# Usage:
#   curl -sSL https://your-nexora-server/install-agent.sh | bash -s -- \
#       --server https://cloud.nexora.io \
#       --gateway https://gw.nexora.io \
#       --name "my-rpi"
#
# Or locally:
#   bash scripts/install-agent.sh --server http://device-service:8000 --gateway http://nexora-edge:8007

set -euo pipefail

NEXORA_SERVER=""
NEXORA_GATEWAY=""
DEVICE_NAME=""
INSTALL_DIR="/opt/nexora-agent"
VENV_DIR="$INSTALL_DIR/venv"
PACKAGE_SOURCE="nexora-agent"   # pip package name or local path
INSTALL_RUNTIME=false
SKIP_PAIR=false

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --server)    NEXORA_SERVER="$2";  shift 2 ;;
        --gateway)   NEXORA_GATEWAY="$2"; shift 2 ;;
        --name)      DEVICE_NAME="$2";    shift 2 ;;
        --runtime)   INSTALL_RUNTIME=true; shift ;;
        --skip-pair) SKIP_PAIR=true;       shift ;;
        --source)    PACKAGE_SOURCE="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Defaults
DEVICE_NAME="${DEVICE_NAME:-$(hostname)}"

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    echo "Error: this script must be run as root (sudo)." >&2
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found. Install it first." >&2
    exit 1
fi

PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_MAJOR=3
REQUIRED_MINOR=11

if python3 -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
    true
else
    echo "Error: Python 3.11+ required (found $PYTHON_VER)." >&2
    exit 1
fi

echo "=== Nexora Agent Installer ==="
echo "  Device name: $DEVICE_NAME"
echo "  Server:      ${NEXORA_SERVER:-<not set — configure after install>}"
echo "  Gateway:     ${NEXORA_GATEWAY:-<not set — configure after install>}"
echo "  Install dir: $INSTALL_DIR"
echo ""

# ---------------------------------------------------------------------------
# Create system user
# ---------------------------------------------------------------------------
if ! id nexora-agent &>/dev/null; then
    echo "[1/6] Creating system user nexora-agent..."
    useradd --system --no-create-home --shell /usr/sbin/nologin nexora-agent
else
    echo "[1/6] System user nexora-agent already exists."
fi

# Add to gpio/i2c groups if they exist (Raspberry Pi)
for grp in gpio i2c spi dialout tpm; do
    if getent group "$grp" &>/dev/null; then
        usermod -aG "$grp" nexora-agent 2>/dev/null || true
    fi
done

# ---------------------------------------------------------------------------
# Create directories
# ---------------------------------------------------------------------------
echo "[2/6] Creating directories..."
mkdir -p "$INSTALL_DIR" /etc/nexora-agent /var/lib/nexora-agent
chown nexora-agent:nexora-agent /etc/nexora-agent /var/lib/nexora-agent
chmod 750 /etc/nexora-agent /var/lib/nexora-agent

# ---------------------------------------------------------------------------
# Install Python virtualenv + package
# ---------------------------------------------------------------------------
echo "[3/6] Installing nexora-agent package..."
if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install "$PACKAGE_SOURCE" -q

if $INSTALL_RUNTIME; then
    echo "      Installing nexora-runtime..."
    "$VENV_DIR/bin/pip" install nexora-runtime -q || true
fi

# Symlink CLI
ln -sf "$VENV_DIR/bin/nexora-agent" /usr/local/bin/nexora-agent

# ---------------------------------------------------------------------------
# Write env file
# ---------------------------------------------------------------------------
echo "[4/6] Writing configuration..."
cat > /etc/nexora-agent/agent.env <<EOF
NEXORA_SERVER_URL=${NEXORA_SERVER}
NEXORA_GATEWAY_URL=${NEXORA_GATEWAY}
NEXORA_CREDENTIALS_DIR=/etc/nexora-agent
NEXORA_QUEUE_DB=/var/lib/nexora-agent/queue.db
NEXORA_LOG_LEVEL=INFO
EOF
chmod 640 /etc/nexora-agent/agent.env
chown nexora-agent:nexora-agent /etc/nexora-agent/agent.env

# ---------------------------------------------------------------------------
# Install systemd unit
# ---------------------------------------------------------------------------
echo "[5/6] Installing systemd service..."
UNIT_SRC="$(dirname "$(readlink -f "$0")")/../packages/nexora-agent/nexora-agent.service"
if [[ -f "$UNIT_SRC" ]]; then
    cp "$UNIT_SRC" /etc/systemd/system/nexora-agent.service
else
    # Inline unit if running from curl pipe
    cat > /etc/systemd/system/nexora-agent.service <<'UNIT'
[Unit]
Description=Nexora IoT Edge Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/local/bin/nexora-agent start
Restart=always
RestartSec=10
WatchdogSec=90
User=nexora-agent
StateDirectory=nexora-agent
ConfigurationDirectory=nexora-agent
ConfigurationDirectoryMode=0700
StandardOutput=journal
StandardError=journal
SyslogIdentifier=nexora-agent
EnvironmentFile=-/etc/nexora-agent/agent.env
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/etc/nexora-agent /var/lib/nexora-agent

[Install]
WantedBy=multi-user.target
UNIT
fi

systemctl daemon-reload
systemctl enable nexora-agent

# ---------------------------------------------------------------------------
# Pair
# ---------------------------------------------------------------------------
if ! $SKIP_PAIR && [[ -n "$NEXORA_SERVER" ]]; then
    echo "[6/6] Starting device pairing..."
    echo ""
    # Run as root temporarily (credentials will be written to /etc/nexora-agent)
    NEXORA_SERVER_URL="$NEXORA_SERVER" \
    NEXORA_GATEWAY_URL="$NEXORA_GATEWAY" \
    NEXORA_CREDENTIALS_DIR=/etc/nexora-agent \
    nexora-agent pair --server "$NEXORA_SERVER" --gateway "$NEXORA_GATEWAY" --name "$DEVICE_NAME"
    chown nexora-agent:nexora-agent /etc/nexora-agent/credentials.json 2>/dev/null || true
    chmod 600 /etc/nexora-agent/credentials.json 2>/dev/null || true

    echo ""
    echo "Starting nexora-agent service..."
    systemctl start nexora-agent
    echo ""
    systemctl status nexora-agent --no-pager || true
else
    echo "[6/6] Skipping pairing (run 'nexora-agent pair' manually)."
    echo ""
    echo "=== Installation complete ==="
    echo ""
    echo "Next steps:"
    echo "  1. Edit /etc/nexora-agent/agent.env with your server URLs"
    echo "  2. Run: nexora-agent pair --server <URL> --gateway <URL>"
    echo "  3. Run: systemctl start nexora-agent"
fi

echo ""
echo "=== Done. Useful commands ==="
echo "  nexora-agent status        — check pairing state"
echo "  nexora-agent logs          — tail journal"
echo "  systemctl status nexora-agent"
