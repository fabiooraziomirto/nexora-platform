"""Kafka → zigbee2mqtt command handler.

Consumes nxr.execution.dispatched for Zigbee devices and publishes the command
to zigbee2mqtt's set topic:
  {Z2M_BASE_TOPIC}/{friendly_name}/set
"""
import asyncio
import json
import logging
from typing import Any

import httpx

from zigbee_bridge.core import config
from zigbee_bridge.core.device_registry import _name_to_id

logger = logging.getLogger("zigbee-bridge.commands")

# Maps Nexora command strings to zigbee2mqtt set payloads.
COMMAND_MAP: dict[str, dict] = {
    "OnOff.On": {"state": "ON"},
    "OnOff.Off": {"state": "OFF"},
    "OnOff.Toggle": {"state": "TOGGLE"},
}

_consumer_task: asyncio.Task | None = None


def _device_id_to_friendly_name(device_id: str) -> str | None:
    for name, nid in _name_to_id.items():
        if nid == device_id:
            return name
    return None


async def start_consumer(kafka_consumer: Any, mqtt_publish_fn: Any) -> None:
    global _consumer_task
    if kafka_consumer is None:
        logger.info("No Kafka consumer — Zigbee command handler disabled")
        return
    _consumer_task = asyncio.create_task(
        _consume_loop(kafka_consumer, mqtt_publish_fn),
        name="zigbee-command-consumer",
    )


async def _consume_loop(kafka_consumer: Any, mqtt_publish_fn: Any) -> None:
    logger.info("Zigbee command consumer started")
    try:
        async for msg in kafka_consumer:
            try:
                event = json.loads(msg.value)
                payload = event.get("payload", {})
                device_id: str = payload.get("device_id", "")
                execution_id: str = payload.get("execution_id", "")

                asyncio.create_task(
                    _dispatch(mqtt_publish_fn, device_id, execution_id, payload),
                    name=f"zigbee-dispatch-{execution_id}",
                )
            except Exception as exc:
                logger.error("Failed to process Kafka message: %s", exc)
    except asyncio.CancelledError:
        logger.info("Zigbee command consumer stopped")
    except Exception as exc:
        logger.error("Kafka consumer error: %s", exc)


async def _dispatch(
    mqtt_publish_fn: Any,
    device_id: str,
    execution_id: str,
    payload: dict,
) -> None:
    friendly_name = _device_id_to_friendly_name(device_id)
    if friendly_name is None:
        logger.warning("No friendly_name for device_id=%s — cannot dispatch", device_id)
        await _callback(execution_id, "failed", stderr=f"Unknown Zigbee device {device_id}")
        return

    command: str = payload.get("command", "")
    args: dict = payload.get("args", {})

    # Build z2m set payload
    if command in COMMAND_MAP:
        z2m_payload = dict(COMMAND_MAP[command])
    else:
        # Pass args directly as the set payload (allows arbitrary attribute sets)
        z2m_payload = args if args else {"state": command}

    # Merge extra args (e.g. brightness, color_temp) if present alongside a known command
    if args and command in COMMAND_MAP:
        z2m_payload.update(args)

    topic = f"{config.Z2M_BASE_TOPIC}/{friendly_name}/set"

    await _callback(execution_id, "running")
    try:
        await mqtt_publish_fn(topic, json.dumps(z2m_payload))
        logger.info("Zigbee command sent eid=%s device=%s cmd=%s", execution_id, friendly_name, command)
        await _callback(execution_id, "succeeded", stdout=f"Sent to {topic}: {z2m_payload}")
    except Exception as exc:
        logger.error("Zigbee command failed eid=%s: %s", execution_id, exc)
        await _callback(execution_id, "failed", stderr=str(exc))


async def _callback(execution_id: str, status: str, stdout: str | None = None, stderr: str | None = None) -> None:
    body: dict = {"status": status}
    if stdout:
        body["stdout"] = stdout
    if stderr:
        body["stderr"] = stderr
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{config.EXECUTION_SERVICE_URL}/api/v2/executions/{execution_id}/callback",
                json=body,
            )
    except Exception as exc:
        logger.warning("Callback failed eid=%s: %s", execution_id, exc)
