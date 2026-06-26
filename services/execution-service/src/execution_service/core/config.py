import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./execution_service.db")
DB_CONNECT_TIMEOUT_SECONDS = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5"))

AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
AUTH_DEV_TOKEN = os.getenv("AUTH_DEV_TOKEN", "dev-token")
AUTH_DEV_BYPASS_ENABLED = os.getenv("AUTH_DEV_BYPASS_ENABLED", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "")
AUTH_WRITE_ROLE = os.getenv("AUTH_WRITE_ROLE", "writer")
# Role that grants platform-operator privileges (sees all executions, full payload)
AUTH_OPERATOR_ROLE = os.getenv("AUTH_OPERATOR_ROLE", "platform-operator")

# FaaS: URLs for capability/plugin validation during dispatch
PLUGIN_SERVICE_URL = os.getenv("PLUGIN_SERVICE_URL", "http://plugin-service:8000")
DEVICE_SERVICE_URL = os.getenv("DEVICE_SERVICE_URL", "http://device-service:8000")
FLEET_SERVICE_URL = os.getenv("FLEET_SERVICE_URL", "http://fleet-service:8000")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC_PREFIX = os.getenv("KAFKA_TOPIC_PREFIX", "nxr")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() == "true"
KAFKA_REQUIRED = os.getenv("KAFKA_REQUIRED", "false").lower() == "true"
KAFKA_RETRY_ATTEMPTS = int(os.getenv("KAFKA_RETRY_ATTEMPTS", "3"))
KAFKA_RETRY_DELAY_SECONDS = float(os.getenv("KAFKA_RETRY_DELAY_SECONDS", "0.5"))

AGENT_CALLBACK_SECRET = os.getenv("AGENT_CALLBACK_SECRET", "")
CALLBACK_REPLAY_TTL_SECONDS = int(os.getenv("CALLBACK_REPLAY_TTL_SECONDS", "900"))
CALLBACK_REPLAY_REQUIRED = os.getenv("CALLBACK_REPLAY_REQUIRED", "false").lower() == "true"

MAX_EXECUTIONS_PER_DEVICE = int(os.getenv("MAX_EXECUTIONS_PER_DEVICE", "32"))
EXECUTION_DISPATCHED_TIMEOUT_SECONDS = int(os.getenv("EXECUTION_DISPATCHED_TIMEOUT_SECONDS", "300"))
EXECUTION_RUNNING_TIMEOUT_SECONDS = int(os.getenv("EXECUTION_RUNNING_TIMEOUT_SECONDS", "3600"))
EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS = int(os.getenv("EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS", "5"))

REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "5"))

TERMINAL_STATUSES = frozenset({"succeeded", "failed", "timeout", "cancelled"})
VALID_STATUSES = frozenset({"queued", "dispatched", "running", "succeeded", "failed", "timeout", "cancelled"})
ACTIVE_STATUSES = frozenset({"queued", "dispatched", "running"})

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"dispatched", "cancelled"},
    "dispatched": {"running", "failed", "timeout", "cancelled"},
    "running": {"succeeded", "failed", "timeout", "cancelled"},
}

_CALLBACK_ALLOWED_FIELDS = frozenset({"status", "exit_code", "stdout", "stderr", "callback_key", "function_result"})
