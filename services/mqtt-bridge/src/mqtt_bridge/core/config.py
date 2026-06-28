import os

MQTT_HOST: str = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME: str | None = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD: str | None = os.getenv("MQTT_PASSWORD")

# TLS: set MQTT_TLS=true and optionally MQTT_CA_CERT path
MQTT_TLS: bool = os.getenv("MQTT_TLS", "false").lower() == "true"
MQTT_CA_CERT: str | None = os.getenv("MQTT_CA_CERT")

# Topic conventions (Nexora-native MQTT protocol):
#
#   Telemetry:  {PREFIX}/devices/{device_id}/telemetry
#               Payload: {"metric": "temperature", "value": 22.5, "unit": "celsius"}
#               or array: [{"metric":..., "value":...}, ...]
#
#   State:      {PREFIX}/devices/{device_id}/state
#               Payload: arbitrary JSON → merged into device shadow reported
#
#   Commands:   {PREFIX}/devices/{device_id}/commands   (bridge publishes, device subscribes)
#               Payload: {"execution_id": "...", "command": "...", "args": {...}}
#
#   Register:   {PREFIX}/devices/{device_id}/register
#               Payload: {"name": "...", "device_type": "...", "capabilities": {...}}
#               Device sends this once at boot to register/re-register itself.
MQTT_TOPIC_PREFIX: str = os.getenv("MQTT_TOPIC_PREFIX", "nexora")

DEVICE_SERVICE_URL: str = os.getenv("DEVICE_SERVICE_URL", "http://device-service:8000")
EXECUTION_SERVICE_URL: str = os.getenv("EXECUTION_SERVICE_URL", "http://execution-service:8002")

AGENT_BOOTSTRAP_TOKEN: str = os.getenv(
    "AGENT_BOOTSTRAP_TOKEN", "bridge:bridge-secret"
)

KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_PREFIX: str = os.getenv("KAFKA_TOPIC_PREFIX", "nxr")
KAFKA_ENABLED: bool = os.getenv("KAFKA_ENABLED", "true").lower() == "true"

ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
PORT: int = int(os.getenv("PORT", "8009"))

# Auto-register unknown devices that publish without a prior /register message.
# The device_id is taken from the topic segment; name defaults to the device_id.
AUTO_REGISTER: bool = os.getenv("MQTT_AUTO_REGISTER", "true").lower() == "true"
