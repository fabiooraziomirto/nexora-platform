"""Matter attribute subscription loop.

Subscribes to attribute changes from python-matter-server for all commissioned
devices. On each change:
  - Publishes telemetry to Kafka (mapped via CLUSTER_METRIC_MAP)
  - Updates the device shadow reported state via device-service HTTP
"""
import asyncio
import json
import logging
import time
from typing import Any

import httpx

from matter_bridge.core import config
from matter_bridge.core.commission import _sessions

logger = logging.getLogger("matter-bridge.attribute_watcher")

# Map Matter cluster attribute paths to Nexora metric names + units.
# Value transformations are applied before publishing (e.g. /100 for temperature).
CLUSTER_METRIC_MAP: dict[str, tuple[str, str, float]] = {
    # (cluster.attribute): (metric_name, unit, multiplier)
    "TemperatureMeasurement.MeasuredValue": ("temperature_celsius", "celsius", 0.01),
    "RelativeHumidityMeasurement.MeasuredValue": ("humidity_percent", "percent", 0.01),
    "PressureMeasurement.MeasuredValue": ("pressure_hpa", "hpa", 0.1),
    "OnOff.OnOff": ("power_state", "bool", 1.0),
    "LevelControl.CurrentLevel": ("brightness_level", "level", 1.0),
    "ElectricalMeasurement.ActivePower": ("power_watts", "watts", 1.0),
    "IlluminanceMeasurement.MeasuredValue": ("illuminance_lux", "lux", 1.0),
    "OccupancySensing.Occupancy": ("occupancy", "bool", 1.0),
}

# Kafka producer reference (set by main.py at startup)
_kafka_producer: Any = None

_watcher_task: asyncio.Task | None = None


def set_kafka_producer(producer: Any) -> None:
    global _kafka_producer
    _kafka_producer = producer


def _node_id_to_device_id(node_id: int) -> str | None:
    """Look up a commissioned device_id by Matter node_id."""
    for s in _sessions.values():
        if s.get("node_id") == node_id and s.get("status") == "commissioned":
            return s.get("device_id")
    return None


async def start_watcher(matter_client: Any) -> None:
    """Start background attribute subscription task."""
    global _watcher_task
    if matter_client is None:
        logger.info("No matter-server client — attribute watcher disabled (mock mode)")
        return
    _watcher_task = asyncio.create_task(_supervised_watch_loop(matter_client), name="attribute-watcher")


async def _supervised_watch_loop(matter_client: Any) -> None:
    """Supervised loop: restarts _watch_loop on transient errors with backoff."""
    backoff = 5
    while True:
        try:
            await _watch_loop(matter_client)
            return  # clean cancellation — do not restart
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error("Attribute watcher crashed (%s) — restarting in %ds", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


async def _watch_loop(matter_client: Any) -> None:
    """Subscribe to attribute changes and dispatch them to Nexora."""
    logger.info("Attribute watcher started")
    try:
        async for event in matter_client.subscribe_events():
            if event.get("event") != "attribute_updated":
                continue
            await _handle_attribute_change(event)
    except asyncio.CancelledError:
        logger.info("Attribute watcher stopped")
        raise  # propagate so supervisor knows it's a clean stop


async def _handle_attribute_change(event: dict) -> None:
    node_id: int = event.get("node_id", 0)
    cluster: str = event.get("cluster_name", "")
    attribute: str = event.get("attribute_name", "")
    raw_value = event.get("value")

    device_id = _node_id_to_device_id(node_id)
    if not device_id:
        return

    attr_key = f"{cluster}.{attribute}"
    now_iso = _utc_iso()

    # Update shadow reported state (always, for any attribute)
    shadow_payload = {cluster: {attribute: raw_value}}
    asyncio.create_task(
        _patch_shadow_reported(device_id, shadow_payload),
        name=f"shadow-{device_id}-{cluster}",
    )

    # Publish telemetry only for mapped metrics
    if attr_key in CLUSTER_METRIC_MAP:
        metric_name, unit, multiplier = CLUSTER_METRIC_MAP[attr_key]
        try:
            value = float(raw_value) * multiplier
        except (TypeError, ValueError):
            return

        await _publish_telemetry(device_id, metric_name, value, unit, now_iso)


async def _patch_shadow_reported(device_id: str, state: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{config.DEVICE_SERVICE_URL}/api/v2/devices/{device_id}/shadow/reported",
                json={"state": state},
            )
    except Exception as exc:
        logger.warning("Failed to update shadow device=%s: %s", device_id, exc)


async def _publish_telemetry(
    device_id: str,
    metric: str,
    value: float,
    unit: str,
    ts_iso: str,
) -> None:
    if _kafka_producer is None or not config.KAFKA_ENABLED:
        return
    topic = f"{config.KAFKA_TOPIC_PREFIX}.device.telemetry.ingested"
    payload = {
        "event_type": "device.telemetry.ingested",
        "service": "matter-bridge",
        "resource": "device",
        "action": "telemetry.ingested",
        "resource_id": device_id,
        "payload": {
            "device_id": device_id,
            "sample_count": 1,
            "metrics": {metric: 1},
            "samples": [{"metric": metric, "value": value, "unit": unit, "ts": ts_iso}],
            "ingested_at": ts_iso,
        },
        "occurred_at": ts_iso,
    }
    try:
        await _kafka_producer.send_and_wait(
            topic,
            json.dumps(payload).encode("utf-8"),
        )
    except Exception as exc:
        logger.warning("Kafka publish failed topic=%s: %s", topic, exc)


def _utc_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
