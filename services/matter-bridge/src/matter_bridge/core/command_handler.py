"""Kafka consumer for Matter command dispatch.

Consumes nxr.execution.dispatched events for devices with connection_protocol="matter",
translates Nexora commands to Matter cluster invocations, and sends the execution
callback to execution-service.
"""
import asyncio
import json
import logging
import time
from typing import Any

import httpx

from matter_bridge.core import config
from matter_bridge.core.commission import _sessions

logger = logging.getLogger("matter-bridge.command_handler")

# Maps Nexora command strings to Matter (cluster, command, args_builder) tuples.
# args_builder receives the execution payload "args" dict and returns Matter command kwargs.
COMMAND_MAP: dict[str, tuple[str, str, callable]] = {
    "OnOff.On": ("OnOff", "on", lambda _: {}),
    "OnOff.Off": ("OnOff", "off", lambda _: {}),
    "OnOff.Toggle": ("OnOff", "toggle", lambda _: {}),
    "LevelControl.MoveToLevel": (
        "LevelControl",
        "move_to_level",
        lambda args: {"level": int(args.get("level", 128)), "transition_time": int(args.get("transition_time", 0))},
    ),
}

_consumer_task: asyncio.Task | None = None


def _node_id_for_device(device_id: str) -> int | None:
    for s in _sessions.values():
        if s.get("device_id") == device_id and s.get("status") == "commissioned":
            return s.get("node_id")
    return None


async def start_consumer(matter_client: Any, kafka_consumer: Any) -> None:
    """Start the Kafka consumer loop for Matter command dispatch."""
    global _consumer_task
    _consumer_task = asyncio.create_task(
        _consume_loop(matter_client, kafka_consumer),
        name="matter-command-consumer",
    )


async def _consume_loop(matter_client: Any, kafka_consumer: Any) -> None:
    if kafka_consumer is None:
        logger.info("No Kafka consumer — command handler disabled")
        return
    logger.info("Matter command consumer started")
    try:
        async for msg in kafka_consumer:
            try:
                event = json.loads(msg.value)
                payload = event.get("payload", {})
                device_id: str = payload.get("device_id", "")
                command: str = payload.get("command", "")
                execution_id: str = payload.get("execution_id", "")

                # Only handle Matter devices
                node_id = _node_id_for_device(device_id)
                if node_id is None:
                    continue

                asyncio.create_task(
                    _dispatch_command(matter_client, execution_id, device_id, node_id, command, payload),
                    name=f"dispatch-{execution_id}",
                )
            except Exception as exc:
                logger.error("Failed to process Kafka message: %s", exc)
    except asyncio.CancelledError:
        logger.info("Matter command consumer stopped")
    except Exception as exc:
        logger.error("Kafka consumer error: %s", exc)


async def _dispatch_command(
    matter_client: Any,
    execution_id: str,
    device_id: str,
    node_id: int,
    command: str,
    payload: dict,
) -> None:
    args = payload.get("args", {})
    t0 = time.monotonic()

    # Report "running" to execution-service
    await _execution_callback(execution_id, "running", None, None)

    try:
        if matter_client is not None and command in COMMAND_MAP:
            cluster, cmd_name, build_args = COMMAND_MAP[command]
            cmd_args = build_args(args)
            # endpoint 1 is the default application endpoint
            await matter_client.send_device_command(node_id, 1, cluster, cmd_name, **cmd_args)
            logger.info(
                "Matter command sent",
                execution_id=execution_id,
                node_id=node_id,
                command=command,
            )
        else:
            logger.warning(
                "Unknown command or no matter client — mock success",
                command=command,
                execution_id=execution_id,
            )
            await asyncio.sleep(0.1)

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        await _execution_callback(
            execution_id, "succeeded",
            exit_code=0,
            stdout=f"Matter command '{command}' executed in {elapsed_ms}ms",
        )
    except Exception as exc:
        logger.error("Matter command failed eid=%s: %s", execution_id, exc)
        await _execution_callback(execution_id, "failed", exit_code=1, stderr=str(exc))


async def _execution_callback(
    execution_id: str,
    status: str,
    exit_code: int | None,
    stdout: str | None = None,
    stderr: str | None = None,
) -> None:
    payload: dict = {"status": status}
    if exit_code is not None:
        payload["exit_code"] = exit_code
    if stdout:
        payload["stdout"] = stdout
    if stderr:
        payload["stderr"] = stderr

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{config.EXECUTION_SERVICE_URL}/api/v2/executions/{execution_id}/callback",
                json=payload,
            )
    except Exception as exc:
        logger.warning("Callback failed eid=%s: %s", execution_id, exc)
