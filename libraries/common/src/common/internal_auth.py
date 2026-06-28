"""Internal service-to-service authentication for Nexora.

Two mechanisms are supported:

  1. X-Internal-Key  — a shared cluster secret (INTERNAL_SERVICE_KEY env var).
     Used for service-to-service calls where no user context is propagated
     (e.g. bridge → execution-service callback).

  2. X-Bootstrap-Token  — the device/bridge pairing token already used by
     the /agents/register endpoint. Reused for device-originated calls
     (telemetry, heartbeat, callback).

When INTERNAL_SERVICE_KEY is not set (dev mode), all validation passes.
When set, at least one valid credential must be present.

Usage — receiving side (FastAPI):

    from common.internal_auth import require_internal

    @app.post("/api/v2/executions/{execution_id}/callback")
    async def callback(execution_id: str, _: None = Depends(require_internal)):
        ...

Usage — sending side:

    from common.internal_auth import internal_headers

    async with httpx.AsyncClient() as client:
        await client.post(url, json=body, headers=internal_headers())
"""
import os
import secrets
import time
from typing import Annotated

from fastapi import Header, HTTPException, Depends

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Shared cluster secret — same value across all internal services.
# Empty string = dev mode (no validation).
INTERNAL_SERVICE_KEY: str = os.getenv("INTERNAL_SERVICE_KEY", "")

# Bootstrap tokens (re-used for device-originated calls).
# Format: "token_id:secret:expiry_epoch,..." (same as AGENT_BOOTSTRAP_TOKENS)
_BOOTSTRAP_TOKENS_RAW: str = os.getenv(
    "AGENT_BOOTSTRAP_TOKENS",
    os.getenv("AGENT_BOOTSTRAP_TOKEN", ""),
)


# ---------------------------------------------------------------------------
# Helpers for callers (sending side)
# ---------------------------------------------------------------------------

def internal_headers() -> dict[str, str]:
    """Return headers to attach to all internal HTTP calls.

    Add to httpx requests:
        headers=internal_headers()
    """
    if INTERNAL_SERVICE_KEY:
        return {"X-Internal-Key": INTERNAL_SERVICE_KEY}
    return {}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _is_valid_internal_key(value: str | None) -> bool:
    if not INTERNAL_SERVICE_KEY:
        return True  # dev mode — no key configured
    return bool(value) and secrets.compare_digest(value, INTERNAL_SERVICE_KEY)


def _is_valid_bootstrap_token(token: str | None) -> bool:
    """Return True if the token matches any configured bootstrap entry."""
    if not _BOOTSTRAP_TOKENS_RAW:
        return not INTERNAL_SERVICE_KEY  # dev mode
    if not token:
        return False
    for entry in _BOOTSTRAP_TOKENS_RAW.split(","):
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


# ---------------------------------------------------------------------------
# FastAPI dependencies (receiving side)
# ---------------------------------------------------------------------------

async def require_internal(
    x_internal_key: Annotated[str | None, Header()] = None,
) -> None:
    """Dependency: accept only requests carrying a valid X-Internal-Key header."""
    if not _is_valid_internal_key(x_internal_key):
        raise HTTPException(status_code=403, detail="Missing or invalid internal service key")


async def require_internal_or_bootstrap(
    x_internal_key: Annotated[str | None, Header()] = None,
    x_bootstrap_token: Annotated[str | None, Header()] = None,
) -> None:
    """Dependency: accept X-Internal-Key (service) OR X-Bootstrap-Token (device/bridge)."""
    if _is_valid_internal_key(x_internal_key):
        return
    if _is_valid_bootstrap_token(x_bootstrap_token):
        return
    raise HTTPException(status_code=403, detail="Missing or invalid internal authentication")
