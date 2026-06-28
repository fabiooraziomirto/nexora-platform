import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("MQTT_HOST", "localhost")
os.environ.setdefault("DEVICE_SERVICE_URL", "http://localhost:8000")
os.environ.setdefault("EXECUTION_SERVICE_URL", "http://localhost:8002")
os.environ.setdefault("AGENT_BOOTSTRAP_TOKEN", "bridge:bridge-secret")
