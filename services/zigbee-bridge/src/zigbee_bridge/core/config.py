import os

# zigbee2mqtt connects to a Mosquitto broker — the zigbee-bridge reads from it.
MQTT_HOST: str = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME: str | None = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD: str | None = os.getenv("MQTT_PASSWORD")

# zigbee2mqtt base topic (configured in zigbee2mqtt's configuration.yaml)
# Default: "zigbee2mqtt"
Z2M_BASE_TOPIC: str = os.getenv("Z2M_BASE_TOPIC", "zigbee2mqtt")

# Nexora services
DEVICE_SERVICE_URL: str = os.getenv("DEVICE_SERVICE_URL", "http://device-service:8000")
EXECUTION_SERVICE_URL: str = os.getenv("EXECUTION_SERVICE_URL", "http://execution-service:8002")
AGENT_BOOTSTRAP_TOKEN: str = os.getenv("AGENT_BOOTSTRAP_TOKEN", "bridge:bridge-secret")

KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_PREFIX: str = os.getenv("KAFKA_TOPIC_PREFIX", "nxr")
KAFKA_ENABLED: bool = os.getenv("KAFKA_ENABLED", "true").lower() == "true"

ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
PORT: int = int(os.getenv("PORT", "8010"))

# zigbee2mqtt topics used by the bridge:
#
#  SUBSCRIBE:
#   {Z2M_BASE_TOPIC}/bridge/devices          → device list on startup / join
#   {Z2M_BASE_TOPIC}/bridge/event            → join/leave/rename events
#   {Z2M_BASE_TOPIC}/{friendly_name}         → periodic device state messages
#
#  PUBLISH (commands):
#   {Z2M_BASE_TOPIC}/{friendly_name}/set     → set device state (OnOff, brightness, …)
#   {Z2M_BASE_TOPIC}/bridge/request/permit_join → allow pairing

INTERNAL_SERVICE_KEY: str = os.getenv("INTERNAL_SERVICE_KEY", "")
