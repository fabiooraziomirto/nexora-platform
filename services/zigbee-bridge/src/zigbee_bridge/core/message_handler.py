"""zigbee2mqtt message dispatcher.

Handles three topic classes:
  1. zigbee2mqtt/bridge/devices   → bulk device inventory (startup + joins)
  2. zigbee2mqtt/bridge/event     → single device join/leave events
  3. zigbee2mqtt/{friendly_name}  → periodic device state (telemetry + shadow)
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from zigbee_bridge.core import config
from zigbee_bridge.core.device_registry import (
    get_device_id,
    register_zigbee_device,
    remove_device,
)

logger = logging.getLogger("zigbee-bridge.handler")

# ---------------------------------------------------------------------------
# Mapping from Zigbee state keys to Nexora metric names + units.
# These are the most common keys from zigbee2mqtt device state messages.
# ---------------------------------------------------------------------------
ZIGBEE_METRIC_MAP: dict[str, tuple[str, str]] = {
    "temperature": ("temperature_celsius", "celsius"),
    "humidity": ("humidity_percent", "percent"),
    "pressure": ("pressure_hpa", "hpa"),
    "illuminance": ("illuminance_lux", "lux"),
    "illuminance_lux": ("illuminance_lux", "lux"),
    "co2": ("co2_ppm", "ppm"),
    "voc": ("voc_ppb", "ppb"),
    "pm25": ("pm25_ugm3", "ugm3"),
    "occupancy": ("occupancy", "bool"),
    "contact": ("door_contact", "bool"),
    "water_leak": ("water_leak", "bool"),
    "smoke": ("smoke", "bool"),
    "gas": ("gas", "bool"),
    "battery": ("battery_percent", "percent"),
    "voltage": ("voltage_mv", "mv"),
    "current": ("current_ma", "ma"),
    "power": ("power_watts", "watts"),
    "energy": ("energy_kwh", "kwh"),
    "linkquality": ("link_quality", "lqi"),
}

# State keys that are set as shadow reported but NOT as numeric telemetry
SHADOW_ONLY_KEYS = {"state", "brightness", "color_temp", "color", "effect", "mode", "fan_mode"}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None


async def handle_message(topic: str, payload: bytes) -> None:
    base = config.Z2M_BASE_TOPIC

    if topic == f"{base}/bridge/devices":
        data = _parse(payload)
        if isinstance(data, list):
            for device_info in data:
                await _process_device_info(device_info)
        return

    if topic == f"{base}/bridge/event":
        data = _parse(payload)
        if isinstance(data, dict):
            await _process_bridge_event(data)
        return

    # Device state message: zigbee2mqtt/{friendly_name}
    # Strip base prefix and any /availability or /set suffixes
    if not topic.startswith(f"{base}/"):
        return
    remainder = topic[len(base) + 1:]
    # Ignore sub-topics like device/set, device/get, device/availability
    if "/" in remainder:
        return

    friendly_name = remainder
    data = _parse(payload)
    if isinstance(data, dict):
        await _process_device_state(friendly_name, data)


async def _process_device_info(info: dict) -> None:
    """Register a device from zigbee2mqtt bridge/devices list."""
    friendly_name: str = info.get("friendly_name", "")
    ieee: str = info.get("ieee_address", "")
    if not friendly_name or not ieee or friendly_name == "Coordinator":
        return

    definition = info.get("definition") or {}
    model_id = definition.get("model")
    vendor = definition.get("vendor")
    device_type = _infer_device_type(definition)

    endpoints = []
    for ep_id, ep_data in (info.get("endpoints") or {}).items():
        clusters_in = ep_data.get("clusters", {}).get("input", [])
        clusters_out = ep_data.get("clusters", {}).get("output", [])
        endpoints.append({
            "id": ep_id,
            "input_clusters": clusters_in,
            "output_clusters": clusters_out,
        })

    await register_zigbee_device(
        friendly_name=friendly_name,
        ieee_address=ieee,
        device_type=device_type,
        model_id=model_id,
        vendor=vendor,
        endpoints=endpoints,
    )


async def _process_bridge_event(event: dict) -> None:
    """Handle zigbee2mqtt bridge events (device_joined, device_leave, etc.)."""
    event_type = event.get("type", "")
    device_info = event.get("data", {})

    if event_type in ("device_joined", "device_interview_successful"):
        await _process_device_info(device_info)
    elif event_type in ("device_leave", "device_removed"):
        friendly_name = device_info.get("friendly_name", "")
        if friendly_name:
            remove_device(friendly_name)


async def _process_device_state(friendly_name: str, state: dict) -> None:
    """Translate a zigbee2mqtt device state message to telemetry + shadow."""
    device_id = get_device_id(friendly_name)
    if device_id is None:
        # Unknown device — it may not have appeared in bridge/devices yet
        logger.debug("Unknown device '%s' — skipping state update", friendly_name)
        return

    samples = []
    shadow_state: dict = {}

    for key, raw_value in state.items():
        # Always include in shadow
        shadow_state[key] = raw_value

        if key in ZIGBEE_METRIC_MAP:
            metric_name, unit = ZIGBEE_METRIC_MAP[key]
            try:
                value = float(int(raw_value) if isinstance(raw_value, bool) else raw_value)
            except (TypeError, ValueError):
                continue
            samples.append({"metric": metric_name, "value": value, "unit": unit})

    ts = _utc_iso()

    if samples:
        await _ingest_telemetry(device_id, samples)

    if shadow_state:
        await _update_shadow(device_id, shadow_state)


async def _ingest_telemetry(device_id: str, samples: list[dict]) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{config.DEVICE_SERVICE_URL}/api/v2/devices/{device_id}/telemetry",
                json={"samples": samples},
            )
            if resp.status_code not in (200, 202):
                logger.warning("Telemetry ingest %s for device %s", resp.status_code, device_id)
    except Exception as exc:
        logger.error("Telemetry ingest failed device=%s: %s", device_id, exc)


async def _update_shadow(device_id: str, state: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{config.DEVICE_SERVICE_URL}/api/v2/devices/{device_id}/shadow/reported",
                json={"state": state},
            )
    except Exception as exc:
        logger.error("Shadow update failed device=%s: %s", device_id, exc)


def _infer_device_type(definition: dict) -> str:
    """Guess a human-readable device type from zigbee2mqtt definition exposes."""
    exposes = definition.get("exposes", [])
    feature_names = set()
    for exp in exposes:
        feature_names.add(exp.get("name", exp.get("type", "")))

    if "temperature" in feature_names:
        return "temperature-sensor"
    if "occupancy" in feature_names:
        return "motion-sensor"
    if "contact" in feature_names:
        return "contact-sensor"
    if "state" in feature_names and "brightness" in feature_names:
        return "dimmable-light"
    if "state" in feature_names:
        return "smart-plug"
    if "energy" in feature_names or "power" in feature_names:
        return "power-meter"
    return "zigbee"
