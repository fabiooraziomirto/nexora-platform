"""Zigbee device registry.

Maps zigbee2mqtt friendly_name / IEEE address → Nexora device_id.
Populated from the zigbee2mqtt/bridge/devices topic at startup and from
join events during operation.
"""
import logging
from typing import Any

import httpx

from zigbee_bridge.core import config

logger = logging.getLogger("zigbee-bridge.registry")

# friendly_name → nexora device_id
_name_to_id: dict[str, str] = {}
# ieee_address → nexora device_id
_ieee_to_id: dict[str, str] = {}


def get_device_id(friendly_name: str) -> str | None:
    return _name_to_id.get(friendly_name)


def get_by_ieee(ieee: str) -> str | None:
    return _ieee_to_id.get(ieee)


async def register_zigbee_device(
    friendly_name: str,
    ieee_address: str,
    device_type: str,
    model_id: str | None,
    vendor: str | None,
    endpoints: list[dict],
) -> str | None:
    """Register or update a Zigbee device on device-service. Returns Nexora device_id."""
    if friendly_name in _name_to_id:
        return _name_to_id[friendly_name]

    protocol_meta: dict = {
        "ieee_address": ieee_address,
        "friendly_name": friendly_name,
        "model_id": model_id,
        "vendor": vendor,
        "endpoints": endpoints,
        "source": "zigbee2mqtt",
    }

    payload = {
        "name": friendly_name,
        "device_type": device_type or "zigbee",
        "connection_protocol": "zigbee",
        "protocol_meta": protocol_meta,
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
            data = resp.json()

        device_id: str = data["device_id"]
        _name_to_id[friendly_name] = device_id
        _ieee_to_id[ieee_address] = device_id
        logger.info(
            "Registered Zigbee device name=%s ieee=%s nexora_id=%s",
            friendly_name, ieee_address, device_id,
        )
        return device_id
    except Exception as exc:
        logger.error("Failed to register Zigbee device %s: %s", friendly_name, exc)
        return None


def remove_device(friendly_name: str) -> None:
    device_id = _name_to_id.pop(friendly_name, None)
    if device_id:
        dead_ieee = [k for k, v in _ieee_to_id.items() if v == device_id]
        for k in dead_ieee:
            _ieee_to_id.pop(k, None)
        logger.info("Removed Zigbee device %s from registry", friendly_name)


def list_devices() -> list[dict[str, Any]]:
    return [{"friendly_name": n, "nexora_device_id": d} for n, d in _name_to_id.items()]
