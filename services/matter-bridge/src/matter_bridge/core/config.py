import os

# matter-server WebSocket URL (python-matter-server process)
MATTER_SERVER_URL: str = os.getenv("MATTER_SERVER_URL", "ws://localhost:5580/ws")

# Nexora service URLs
DEVICE_SERVICE_URL: str = os.getenv("DEVICE_SERVICE_URL", "http://device-service:8000")
EXECUTION_SERVICE_URL: str = os.getenv("EXECUTION_SERVICE_URL", "http://execution-service:8002")

# Bootstrap token used when registering Matter devices on behalf of owners
# Format: "id:secret" — must match an entry in device-service AGENT_BOOTSTRAP_TOKENS
AGENT_BOOTSTRAP_TOKEN: str = os.getenv(
    "AGENT_BOOTSTRAP_TOKEN", "bridge:bridge-secret"
)

# Kafka
KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_PREFIX: str = os.getenv("KAFKA_TOPIC_PREFIX", "nxr")
KAFKA_ENABLED: bool = os.getenv("KAFKA_ENABLED", "true").lower() == "true"

ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
PORT: int = int(os.getenv("PORT", "8008"))
