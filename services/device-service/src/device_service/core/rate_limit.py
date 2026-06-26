"""Rate limiting for device-service.

Uses slowapi (a Starlette/FastAPI wrapper around the `limits` library).
Limits are keyed on the client IP by default; agent endpoints use device_id
from the path to key per-device, preventing one device from DoS-ing others.

Configured limits (all sliding-window, overridable via env vars):
  - RATE_LIMIT_TELEMETRY_INGEST   default 60/minute
  - RATE_LIMIT_TELEMETRY_QUERY    default 120/minute
  - RATE_LIMIT_HEARTBEAT          default 30/minute
  - RATE_LIMIT_REGISTER           default 10/minute

Set RATE_LIMIT_ENABLED=false to disable all limits (e.g. for benchmarking).
"""
import os
from slowapi import Limiter
from slowapi.util import get_remote_address

_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() not in ("false", "0", "no")

# Limit strings — raise via env vars for benchmarks / load tests
LIMIT_TELEMETRY_INGEST = os.getenv("RATE_LIMIT_TELEMETRY_INGEST", "60/minute")
LIMIT_TELEMETRY_QUERY  = os.getenv("RATE_LIMIT_TELEMETRY_QUERY",  "120/minute")
LIMIT_HEARTBEAT        = os.getenv("RATE_LIMIT_HEARTBEAT",        "30/minute")
LIMIT_REGISTER         = os.getenv("RATE_LIMIT_REGISTER",         "10/minute")

# When disabled: use a trivially high limit so the decorator is still valid
if not _ENABLED:
    LIMIT_TELEMETRY_INGEST = "100000/minute"
    LIMIT_TELEMETRY_QUERY  = "100000/minute"
    LIMIT_HEARTBEAT        = "100000/minute"
    LIMIT_REGISTER         = "100000/minute"

# Default key function: client IP (X-Forwarded-For → fallback to socket addr)
limiter = Limiter(key_func=get_remote_address)


def key_by_device_id(request) -> str:  # type: ignore[no-untyped-def]
    """Key rate limit by device_id path parameter (falls back to IP)."""
    device_id = request.path_params.get("device_id")
    if device_id:
        return str(device_id)
    return get_remote_address(request)
