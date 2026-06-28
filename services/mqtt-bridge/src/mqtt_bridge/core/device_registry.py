"""Device registry — tracks MQTT device_ids known to Nexora.

Maps topic-extracted device_id → nexora device_id (same value in the Nexora-native
convention; may differ if device publishes a custom id that needs normalising).

Handles auto-registration for devices that start publishing without a prior
/register message.
"""
import logging
from typing import Any

import httpx

from mqtt_bridge.core import config

logger = logging.getLogger("mqtt-bridge.registry")

# In-memory set of device_ids already confirmed in device-service.
_known: set[str] = set()


async def ensure_registered(device_id: str, name: str | None = None, device_type: str = "mqtt") -> bool:
    """Ensure device_id is registered on device-service; register if not.

    Returns True if device is now registered, False on failure.
    """
    if device_id in _known:
        return True

    payload = {
        "name": name or device_id,
        "device_type": device_type,
        "connection_protocol": "mqtt",
        "protocol_meta": {"mqtt_client_id": device_id},
    }
    headers = {"X-Bootstrap-Token": config.AGENT_BOOTSTRAP_TOKEN}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{config.DEVICE_SERVICE_URL}/api/v2/agents/register",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
        _known.add(device_id)
        logger.info("Auto-registered MQTT device %s", device_id)
        return True
    except Exception as exc:
        logger.warning("Failed to register MQTT device %s: %s", device_id, exc)
        return False


def mark_known(device_id: str) -> None:
    _known.add(device_id)


def is_known(device_id: str) -> bool:
    return device_id in _known
