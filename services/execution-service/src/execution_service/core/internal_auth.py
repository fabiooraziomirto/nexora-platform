"""Internal service-to-service auth for execution-service.

Mirrors libraries/common/src/common/internal_auth.py — kept local because
execution-service is a flat-pattern service with its own dependency graph.
"""
import secrets
import time

from fastapi import Header, HTTPException

from execution_service.core.config import INTERNAL_SERVICE_KEY, AGENT_BOOTSTRAP_TOKENS


def internal_headers() -> dict[str, str]:
    """Return headers to attach to all internal outbound HTTP calls."""
    if INTERNAL_SERVICE_KEY:
        return {"X-Internal-Key": INTERNAL_SERVICE_KEY}
    return {}


def _valid_internal_key(value: str | None) -> bool:
    if not INTERNAL_SERVICE_KEY:
        return True  # dev mode — no key configured
    return bool(value) and secrets.compare_digest(value, INTERNAL_SERVICE_KEY)


def _valid_bootstrap_token(token: str | None) -> bool:
    if not AGENT_BOOTSTRAP_TOKENS:
        return not INTERNAL_SERVICE_KEY  # dev mode
    if not token:
        return False
    for entry in AGENT_BOOTSTRAP_TOKENS.split(","):
        parts = entry.strip().split(":")
        if len(parts) < 2:
            continue
        token_id, secret = parts[0], parts[1]
        expiry = int(parts[2]) if len(parts) > 2 else 0
        candidate = f"{token_id}:{secret}"
        if secrets.compare_digest(token, candidate):
            if expiry == 0 or time.time() < expiry:
                return True
    return False


async def require_internal_or_bootstrap(
    x_internal_key: str | None = Header(default=None),
    x_bootstrap_token: str | None = Header(default=None),
) -> None:
    """FastAPI dependency: accept X-Internal-Key (service) OR X-Bootstrap-Token (device/bridge)."""
    if _valid_internal_key(x_internal_key):
        return
    if _valid_bootstrap_token(x_bootstrap_token):
        return
    raise HTTPException(status_code=403, detail="Missing or invalid internal authentication")
