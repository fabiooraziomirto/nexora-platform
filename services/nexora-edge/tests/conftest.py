import os
import sys
from pathlib import Path

# Disable external infra before importing the app.
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("OTEL_ENABLED", "false")

_SERVICE_ROOT = Path(__file__).resolve().parent.parent
_SRC = _SERVICE_ROOT / "src"
for p in (str(_SERVICE_ROOT), str(_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)
