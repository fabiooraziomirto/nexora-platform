import os
import sys

# Ensure src is on PYTHONPATH for tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("MATTER_SERVER_URL", "ws://localhost:5580/ws")
os.environ.setdefault("DEVICE_SERVICE_URL", "http://localhost:8000")
os.environ.setdefault("EXECUTION_SERVICE_URL", "http://localhost:8002")
os.environ.setdefault("AGENT_BOOTSTRAP_TOKEN", "bridge:bridge-secret")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # Import after env is set
    import importlib
    import main as app_module
    importlib.reload(app_module)
    from main import app
    return TestClient(app, raise_server_exceptions=False)
