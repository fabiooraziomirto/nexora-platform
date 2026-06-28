"""MQTT message dispatcher.

Parses incoming MQTT messages and routes them to the appropriate Nexora API:
  - /register  → device-service agent registration
  - /telemetry → device-service telemetry ingest
  - /state     → device-service shadow reported update
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from mqtt_bridge.core import config
from mqtt_bridge.core.device_registry import ensure_registered, is_known, mark_known

logger = logging.getLogger("mqtt-bridge.handler")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_payload(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


async def handle_message(topic: str, payload: bytes) -> None:
    """Route an incoming MQTT message based on its topic suffix."""
    prefix = config.MQTT_TOPIC_PREFIX
    parts = topic.split("/")

    # Expected: {prefix}/devices/{device_id}/{action}
    if len(parts) < 4 or parts[0] != prefix or parts[1] != "devices":
        return

    device_id = parts[2]
    action = parts[3]

    data = _parse_payload(payload)
    if data is None:
        logger.warning("Non-JSON payload on topic %s — ignored", topic)
        return

    if action == "register":
        await _handle_register(device_id, data)
    elif action == "telemetry":
        await _handle_telemetry(device_id, data)
    elif action == "state":
        await _handle_state(device_id, data)
    else:
        logger.debug("Unknown action '%s' on topic %s — ignored", action, topic)


async def _handle_register(device_id: str, data: dict) -> None:
    """Device self-registers (or re-registers) at boot."""
    name = data.get("name", device_id)
    device_type = data.get("device_type", "mqtt")
    capabilities = data.get("capabilities")
    protocol_meta = {"mqtt_client_id": device_id, **data.get("protocol_meta", {})}

    payload: dict = {
        "name": name,
        "device_type": device_type,
        "connection_protocol": "mqtt",
        "protocol_meta": protocol_meta,
    }
    if capabilities:
        payload["capabilities"] = capabilities

    headers = {"X-Bootstrap-Token": config.AGENT_BOOTSTRAP_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{config.DEVICE_SERVICE_URL}/api/v2/agents/register",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
        mark_known(device_id)
        logger.info("MQTT device registered device_id=%s name=%s", device_id, name)
    except Exception as exc:
        logger.error("Registration failed device_id=%s: %s", device_id, exc)


async def _handle_telemetry(device_id: str, data: Any) -> None:
    """Ingest telemetry samples into device-service."""
    if not config.AUTO_REGISTER:
        if not is_known(device_id):
            logger.debug("AUTO_REGISTER disabled — ignoring unknown device %s", device_id)
            return
    else:
        await ensure_registered(device_id)

    # Normalise: accept single sample dict or list of samples
    if isinstance(data, dict):
        samples = [data]
    elif isinstance(data, list):
        samples = data
    else:
        logger.warning("Unexpected telemetry payload type on device %s", device_id)
        return

    # Validate and normalise each sample
    normalised = []
    for s in samples:
        if not isinstance(s, dict):
            continue
        metric = s.get("metric")
        value = s.get("value")
        if metric is None or value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        sample: dict = {"metric": str(metric), "value": value}
        if "ts" in s:
            sample["ts"] = s["ts"]
        if "tags" in s and isinstance(s["tags"], dict):
            sample["tags"] = s["tags"]
        if "unit" in s:
            sample["unit"] = str(s["unit"])
        normalised.append(sample)

    if not normalised:
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{config.DEVICE_SERVICE_URL}/api/v2/devices/{device_id}/telemetry",
                json={"samples": normalised},
            )
            if resp.status_code == 404:
                # Device deleted; remove from known set and re-register
                from mqtt_bridge.core.device_registry import _known
                _known.discard(device_id)
                await ensure_registered(device_id)
            elif resp.status_code not in (200, 202):
                logger.warning(
                    "Telemetry ingest returned %s for device %s", resp.status_code, device_id
                )
    except Exception as exc:
        logger.error("Telemetry ingest failed device=%s: %s", device_id, exc)


async def _handle_state(device_id: str, data: dict) -> None:
    """Merge incoming state dict into the device shadow reported state."""
    if not isinstance(data, dict):
        return

    await ensure_registered(device_id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{config.DEVICE_SERVICE_URL}/api/v2/devices/{device_id}/shadow/reported",
                json={"state": data},
            )
    except Exception as exc:
        logger.error("Shadow update failed device=%s: %s", device_id, exc)
