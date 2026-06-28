"""RFC 8628 device pairing flow for nexora-agent.

Steps:
  1. POST /api/v2/devices/announce  → device_code, user_code, expires_in
  2. Display user_code to operator (console or physical display)
  3. Poll GET /api/v2/devices/announce/poll until approved or expired
  4. On approval: device_id + bootstrap_token returned
  5. POST /api/v2/agents/register with bootstrap_token → confirms device_id
  6. Persist credentials via credentials.py
"""
import asyncio
import logging
import sys
from typing import Callable

import httpx

from nexora_agent import config, credentials

logger = logging.getLogger("nexora-agent.pairing")


class PairingError(Exception):
    pass


class PairingExpired(PairingError):
    pass


class PairingDenied(PairingError):
    pass


async def run_pairing(
    server_url: str,
    gateway_url: str,
    device_name: str,
    device_type: str = "linux-agent",
    on_user_code: Callable[[str, str], None] | None = None,
) -> dict:
    """Full RFC 8628 pairing flow. Returns the saved credentials dict.

    Args:
        server_url: device-service base URL
        gateway_url: nexora-edge base URL
        device_name: human-readable name shown to the owner in the UI
        device_type: device type tag (default: linux-agent)
        on_user_code: callback(user_code, verification_uri) to display the code
    """
    async with httpx.AsyncClient(base_url=server_url, timeout=15.0) as client:
        # Step 1: announce
        resp = await client.post("/api/v2/devices/announce", json={
            "name": device_name,
            "device_type": device_type,
            "connection_protocol": "nexora-agent",
        })
        resp.raise_for_status()
        announcement = resp.json()

    device_code: str = announcement["device_code"]
    user_code: str = announcement["user_code"]
    expires_in: int = announcement.get("expires_in", 300)
    poll_interval: float = float(announcement.get("interval", config.DISCOVERY_POLL_INTERVAL))
    verification_uri: str = announcement.get("verification_uri", f"{server_url}/pair")

    logger.info("Pairing started — user_code=%s", user_code)

    if on_user_code:
        on_user_code(user_code, verification_uri)
    else:
        _print_pairing_banner(user_code, verification_uri)

    # Step 2: poll
    deadline = asyncio.get_event_loop().time() + expires_in
    async with httpx.AsyncClient(base_url=server_url, timeout=15.0) as client:
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(poll_interval)
            resp = await client.get(
                "/api/v2/devices/announce/poll",
                params={"device_code": device_code},
            )
            if resp.status_code == 200:
                result = resp.json()
                status = result.get("status", "pending")
                if status == "approved":
                    bootstrap_token: str = result["bootstrap_token"]
                    device_id: str = result["device_id"]
                    break
                elif status == "denied":
                    raise PairingDenied("Pairing was denied by the owner")
                # else "pending" — keep polling
            elif resp.status_code == 404:
                raise PairingExpired("Pairing session expired or not found")
            else:
                logger.warning("Poll returned %s — retrying", resp.status_code)
        else:
            raise PairingExpired(f"Pairing expired after {expires_in}s without approval")

    # Step 3: register agent
    async with httpx.AsyncClient(base_url=server_url, timeout=15.0) as client:
        resp = await client.post(
            "/api/v2/agents/register",
            json={
                "name": device_name,
                "device_type": device_type,
                "connection_protocol": "nexora-agent",
                "protocol_meta": {
                    "agent_version": _agent_version(),
                    "platform": _platform_info(),
                },
            },
            headers={"X-Bootstrap-Token": bootstrap_token},
        )
        resp.raise_for_status()
        reg = resp.json()
        confirmed_device_id: str = reg["device_id"]

    creds = {
        "device_id": confirmed_device_id,
        "bootstrap_token": bootstrap_token,
        "server_url": server_url,
        "gateway_url": gateway_url,
        "device_name": device_name,
        "device_type": device_type,
    }
    credentials.save(creds)
    logger.info("Pairing complete — device_id=%s", confirmed_device_id)
    return creds


def _print_pairing_banner(user_code: str, verification_uri: str) -> None:
    border = "=" * 52
    print(f"\n{border}", file=sys.stderr)
    print("  Nexora Agent — Device Pairing", file=sys.stderr)
    print(border, file=sys.stderr)
    print(f"  Activation code:  {user_code}", file=sys.stderr)
    print(f"  Visit:            {verification_uri}", file=sys.stderr)
    print(f"  Enter the code above to approve this device.", file=sys.stderr)
    print(f"{border}\n", file=sys.stderr)


def _agent_version() -> str:
    try:
        from importlib.metadata import version
        return version("nexora-agent")
    except Exception:
        return "unknown"


def _platform_info() -> dict:
    import platform
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "node": platform.node(),
    }
