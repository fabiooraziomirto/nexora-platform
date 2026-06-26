import os
import sys
from pathlib import Path

# Disable external/side-effecting infra before importing the app.
os.environ.setdefault("POLICY_CACHE_ENABLED", "false")
os.environ.setdefault("AUDIT_ENABLED", "false")

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
