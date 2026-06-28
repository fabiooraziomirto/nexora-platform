import os

ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

# matter-server WebSocket URL (python-matter-server process)
MATTER_SERVER_URL: str = os.getenv("MATTER_SERVER_URL", "ws://localhost:5580/ws")

# Nexora service URLs
DEVICE_SERVICE_URL: str = os.getenv("DEVICE_SERVICE_URL", "http://device-service:8000")
EXECUTION_SERVICE_URL: str = os.getenv("EXECUTION_SERVICE_URL", "http://execution-service:8002")

# Bootstrap token used when registering Matter devices on behalf of owners
# Format: "id:secret" — must match an entry in device-service AGENT_BOOTSTRAP_TOKENS
# IMPORTANT: override via AGENT_BOOTSTRAP_TOKEN env var in production; the default
# is a well-known value committed to source and must NOT be used outside dev/CI.
AGENT_BOOTSTRAP_TOKEN: str = os.getenv(
    "AGENT_BOOTSTRAP_TOKEN", "bridge:bridge-secret"
)

if AGENT_BOOTSTRAP_TOKEN == "bridge:bridge-secret" and ENVIRONMENT != "development":
    import warnings
    warnings.warn(
        "AGENT_BOOTSTRAP_TOKEN is set to the insecure default. "
        "Set the AGENT_BOOTSTRAP_TOKEN environment variable before deploying.",
        stacklevel=1,
    )

# Kafka
KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_PREFIX: str = os.getenv("KAFKA_TOPIC_PREFIX", "nxr")
KAFKA_ENABLED: bool = os.getenv("KAFKA_ENABLED", "true").lower() == "true"

PORT: int = int(os.getenv("PORT", "8008"))

INTERNAL_SERVICE_KEY: str = os.getenv("INTERNAL_SERVICE_KEY", "")
