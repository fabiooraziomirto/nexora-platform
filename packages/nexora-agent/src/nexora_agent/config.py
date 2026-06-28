"""nexora-agent runtime configuration.

Values are read from environment variables and from the credentials file
written by the pairing flow. CLI flags override env vars at startup.
"""
import os
from pathlib import Path

# Cloud endpoints
SERVER_URL: str = os.getenv("NEXORA_SERVER_URL", "http://localhost:8000")
GATEWAY_URL: str = os.getenv("NEXORA_GATEWAY_URL", "http://localhost:8007")

# Derived WebSocket URL (http → ws, https → wss)
def gateway_ws_url() -> str:
    base = GATEWAY_URL.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://"):]
    return "ws://" + base.lstrip("http://")

# Credential storage
CREDENTIALS_DIR: Path = Path(os.getenv("NEXORA_CREDENTIALS_DIR", "/etc/nexora-agent"))
CREDENTIALS_FILE: Path = CREDENTIALS_DIR / "credentials.json"

# Offline queue
QUEUE_DB_PATH: Path = Path(os.getenv("NEXORA_QUEUE_DB", "/var/lib/nexora-agent/queue.db"))

# Pairing
DISCOVERY_POLL_INTERVAL: float = float(os.getenv("NEXORA_POLL_INTERVAL", "5.0"))

# Tunnel
RECONNECT_BACKOFF_BASE: float = float(os.getenv("NEXORA_RECONNECT_BACKOFF", "2.0"))
RECONNECT_BACKOFF_MAX: float = float(os.getenv("NEXORA_RECONNECT_MAX", "60.0"))
HEARTBEAT_INTERVAL: float = float(os.getenv("NEXORA_HEARTBEAT_INTERVAL", "30.0"))

# Telemetry
TELEMETRY_FLUSH_INTERVAL: float = float(os.getenv("NEXORA_TELEMETRY_FLUSH", "10.0"))
TELEMETRY_BATCH_SIZE: int = int(os.getenv("NEXORA_TELEMETRY_BATCH", "50"))

# Executor
COMMAND_TIMEOUT: float = float(os.getenv("NEXORA_COMMAND_TIMEOUT", "60.0"))
COMMAND_MAX_OUTPUT: int = int(os.getenv("NEXORA_MAX_OUTPUT", str(64 * 1024)))  # 64 KB

# Runtime (nexora-runtime sidecar)
RUNTIME_URL: str = os.getenv("NEXORA_RUNTIME_URL", "http://127.0.0.1:9001")
RUNTIME_ENABLED: bool = os.getenv("NEXORA_RUNTIME_ENABLED", "true").lower() == "true"

# Hardware
HARDWARE_ENABLED: bool = os.getenv("NEXORA_HARDWARE_ENABLED", "false").lower() == "true"
I2C_BUS: int = int(os.getenv("NEXORA_I2C_BUS", "1"))

# Logging
LOG_LEVEL: str = os.getenv("NEXORA_LOG_LEVEL", "INFO")
