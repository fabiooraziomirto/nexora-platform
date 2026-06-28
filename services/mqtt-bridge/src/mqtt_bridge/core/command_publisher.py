"""Kafka → MQTT command publisher.

Consumes nxr.execution.dispatched for MQTT devices and publishes the command
to the device's MQTT command topic:
  {MQTT_TOPIC_PREFIX}/devices/{device_id}/commands
"""
import asyncio
import json
import logging
import time
from typing import Any

import httpx

from mqtt_bridge.core import config

logger = logging.getLogger("mqtt-bridge.commands")

_consumer_task: asyncio.Task | None = None


async def start_consumer(kafka_consumer: Any, mqtt_publish_fn: Any) -> None:
    global _consumer_task
    if kafka_consumer is None:
        logger.info("No Kafka consumer — command publisher disabled")
        return
    _consumer_task = asyncio.create_task(
        _consume_loop(kafka_consumer, mqtt_publish_fn),
        name="mqtt-command-consumer",
    )


async def _consume_loop(kafka_consumer: Any, mqtt_publish_fn: Any) -> None:
    logger.info("MQTT command consumer started")
    try:
        async for msg in kafka_consumer:
            try:
                event = json.loads(msg.value)
                payload = event.get("payload", {})
                device_id: str = payload.get("device_id", "")
                execution_id: str = payload.get("execution_id", "")

                # Only handle MQTT-protocol devices (checked by caller or filtered here)
                asyncio.create_task(
                    _dispatch(mqtt_publish_fn, device_id, execution_id, payload),
                    name=f"mqtt-dispatch-{execution_id}",
                )
            except Exception as exc:
                logger.error("Failed to process Kafka message: %s", exc)
    except asyncio.CancelledError:
        logger.info("MQTT command consumer stopped")
    except Exception as exc:
        logger.error("Kafka consumer error: %s", exc)


async def _dispatch(
    mqtt_publish_fn: Any,
    device_id: str,
    execution_id: str,
    payload: dict,
) -> None:
    topic = f"{config.MQTT_TOPIC_PREFIX}/devices/{device_id}/commands"
    message = {
        "execution_id": execution_id,
        "command": payload.get("command"),
        "args": payload.get("args", {}),
        "execution_type": payload.get("execution_type", "command"),
    }

    await _execution_callback(execution_id, "running")

    try:
        await mqtt_publish_fn(topic, json.dumps(message))
        logger.info("MQTT command published eid=%s device=%s", execution_id, device_id)
        await _execution_callback(
            execution_id, "succeeded",
            stdout=f"Command published to {topic}",
        )
    except Exception as exc:
        logger.error("MQTT publish failed eid=%s: %s", execution_id, exc)
        await _execution_callback(execution_id, "failed", stderr=str(exc))


async def _execution_callback(
    execution_id: str,
    status: str,
    stdout: str | None = None,
    stderr: str | None = None,
) -> None:
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
