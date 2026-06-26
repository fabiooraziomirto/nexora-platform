"""Rate limiting for device-service.

Uses slowapi (a Starlette/FastAPI wrapper around the `limits` library).
Limits are keyed on the client IP by default; agent endpoints use device_id
from the path to key per-device, preventing one device from DoS-ing others.

Configured limits (all sliding-window):
  - telemetry ingest:  60 requests / minute per IP
  - agent heartbeat:   30 requests / minute per device_id
  - agent register:    10 requests / minute per IP
  - shadow desired:    30 requests / minute per IP
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Default key function: client IP (X-Forwarded-For → fallback to socket addr)
limiter = Limiter(key_func=get_remote_address)


def key_by_device_id(request) -> str:  # type: ignore[no-untyped-def]
    """Key rate limit by device_id path parameter (falls back to IP)."""
    device_id = request.path_params.get("device_id")
    if device_id:
        return str(device_id)
    return get_remote_address(request)
