"""WebSocket tunnel to nexora-edge gateway.

Responsibilities:
  - Maintain a persistent WebSocket connection to /api/v2/agents/ws/{device_id}
  - Send heartbeats to device-service every HEARTBEAT_INTERVAL seconds
  - Receive "control" messages and dispatch them via executor.execute()
  - Send "ack" messages after each execution
  - On reconnect: drain the offline queue
  - Exponential backoff on connection errors (base=2s, max=60s)
  - Notify systemd watchdog via sd_notify if available
"""
import asyncio
import json
import logging
import math
import time
from typing import Any

import httpx
import websockets
import websockets.exceptions

from nexora_agent import config, credentials, executor, offline_queue, telemetry

logger = logging.getLogger("nexora-agent.tunnel")


def _auth_headers(creds: dict) -> dict[str, str]:
    """Return authentication headers for all internal calls from this device.

    Uses the bootstrap token stored at pairing time as a persistent device
    credential (X-Bootstrap-Token). The receiving services validate it against
    AGENT_BOOTSTRAP_TOKENS.
    """
    token = creds.get("bootstrap_token", "")
    if token:
        return {"X-Bootstrap-Token": token}
    return {}


async def run(creds: dict) -> None:
    """Main tunnel loop. Runs forever, reconnecting on failure."""
    device_id: str = creds["device_id"]
    server_url: str = creds["server_url"]
    gateway_url: str = creds["gateway_url"]
    ws_url = _ws_url(gateway_url) + f"/api/v2/agents/ws/{device_id}"

    auth = _auth_headers(creds)

    # Start background tasks
    asyncio.create_task(
        telemetry.flush_loop(device_id, server_url),
        name="telemetry-flush",
    )
    asyncio.create_task(
        _heartbeat_loop(device_id, server_url, auth),
        name="heartbeat",
    )

    backoff = config.RECONNECT_BACKOFF_BASE
    attempt = 0

    while True:
        attempt += 1
        logger.info("Connecting to gateway (attempt=%d) %s", attempt, ws_url)
        try:
            async with websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=10,
                open_timeout=15,
            ) as ws:
                logger.info("WebSocket tunnel established — device_id=%s", device_id)
                _sd_notify("READY=1\nSTATUS=Connected to gateway")
                backoff = config.RECONNECT_BACKOFF_BASE  # reset on success

                # Register session with gateway
                await _register_session(device_id, server_url, gateway_url, auth)

                # Drain anything queued while offline
                await offline_queue.drain(
                    send_telemetry_fn=lambda p: _send_telemetry(p, device_id, server_url, auth),
                    send_callback_fn=lambda p: _send_callback(p, server_url, auth),
                )

                # Main receive loop
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        logger.warning("Invalid JSON from gateway: %r", raw[:200])
                        continue

                    msg_type = msg.get("type")
                    if msg_type == "control":
                        asyncio.create_task(
                            _handle_control(ws, msg, device_id, server_url, auth),
                            name=f"exec-{msg.get('execution_id', 'unknown')}",
                        )
                    elif msg_type == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                    else:
                        logger.debug("Unhandled message type: %s", msg_type)

        except websockets.exceptions.ConnectionClosedOK:
            logger.info("Gateway closed connection cleanly — reconnecting")
        except websockets.exceptions.ConnectionClosedError as exc:
            logger.warning("WebSocket connection lost: %s", exc)
        except OSError as exc:
            logger.warning("Network error: %s", exc)
        except Exception as exc:
            logger.error("Tunnel error: %s", exc)

        _sd_notify(f"STATUS=Reconnecting in {backoff:.0f}s")
        logger.info("Reconnecting in %.1fs", backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, config.RECONNECT_BACKOFF_MAX)


async def _handle_control(ws, msg: dict, device_id: str, server_url: str, auth: dict) -> None:
    execution_id: str = msg.get("execution_id", "")
    logger.info("Control message received eid=%s", execution_id)

    # Immediately report "running"
    await _send_callback_direct(
        execution_id, "running", server_url, stdout=None, stderr=None, auth=auth
    )

    # Execute
    dispatch = msg.get("payload", msg)
    dispatch["execution_type"] = dispatch.get("execution_type", msg.get("execution_type", "command"))
    result = await executor.execute(dispatch)

    # ACK to gateway (removes from replay buffer)
    try:
        await ws.send(json.dumps({"type": "ack", "execution_id": execution_id}))
    except Exception as exc:
        logger.warning("ACK send failed eid=%s: %s", execution_id, exc)

    # Final callback to execution-service
    ok = await _send_callback_direct(
        execution_id,
        result["status"],
        server_url,
        stdout=result.get("stdout"),
        stderr=result.get("stderr"),
        exit_code=result.get("exit_code"),
        auth=auth,
    )
    if not ok:
        offline_queue.enqueue("callback", {
            "execution_id": execution_id,
            "status": result["status"],
            "stdout": result.get("stdout"),
            "stderr": result.get("stderr"),
            "exit_code": result.get("exit_code"),
        })


async def _send_callback_direct(
    execution_id: str,
    status: str,
    server_url: str,
    stdout: str | None,
    stderr: str | None,
    exit_code: int | None = None,
    auth: dict | None = None,
) -> bool:
    body: dict = {"status": status}
    if stdout:
        body["stdout"] = stdout
    if stderr:
        body["stderr"] = stderr
    if exit_code is not None:
        body["exit_code"] = exit_code
    try:
        async with httpx.AsyncClient(base_url=server_url, timeout=10.0) as client:
            resp = await client.post(
                f"/api/v2/executions/{execution_id}/callback", json=body, headers=auth or {}
            )
            return resp.status_code in (200, 202, 204)
    except Exception as exc:
        logger.warning("Callback failed eid=%s: %s", execution_id, exc)
        return False


async def _send_callback(payload: dict, server_url: str, auth: dict | None = None) -> bool:
    execution_id = payload.get("execution_id", "")
    return await _send_callback_direct(
        execution_id,
        payload.get("status", "failed"),
        server_url,
        payload.get("stdout"),
        payload.get("stderr"),
        payload.get("exit_code"),
        auth=auth,
    )


async def _send_telemetry(payload: dict, device_id: str, server_url: str, auth: dict | None = None) -> bool:
    try:
        async with httpx.AsyncClient(base_url=server_url, timeout=10.0) as client:
            resp = await client.post(
                f"/api/v2/devices/{device_id}/telemetry",
                json={"samples": payload.get("samples", [])},
                headers=auth or {},
            )
            return resp.status_code in (200, 202)
    except Exception:
        return False


async def _register_session(device_id: str, server_url: str, gateway_url: str, auth: dict | None = None) -> None:
    try:
        async with httpx.AsyncClient(base_url=gateway_url, timeout=10.0) as client:
            await client.post("/api/v2/agents/sessions/register", json={
                "device_id": device_id,
                "capabilities": _capabilities(),
            }, headers=auth or {})
    except Exception as exc:
        logger.warning("Session register failed: %s", exc)


async def _heartbeat_loop(device_id: str, server_url: str, auth: dict | None = None) -> None:
    while True:
        await asyncio.sleep(config.HEARTBEAT_INTERVAL)
        try:
            async with httpx.AsyncClient(base_url=server_url, timeout=10.0) as client:
                await client.post(
                    f"/api/v2/agents/sessions/{device_id}/heartbeat",
                    headers=auth or {},
                )
        except Exception as exc:
            logger.debug("Heartbeat failed: %s", exc)


def _capabilities() -> dict:
    caps: dict = {
        "protocol": "nexora-agent",
        "wasm": config.RUNTIME_ENABLED,
        "hardware": config.HARDWARE_ENABLED,
    }
    if config.HARDWARE_ENABLED:
        try:
            from nexora_agent.hardware import sensors
            caps["sensors"] = sensors.discover()
        except Exception:
            caps["sensors"] = []
    return caps


def _ws_url(gateway_url: str) -> str:
    base = gateway_url.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://"):]
    return "ws://" + base.lstrip("http://")


def _sd_notify(state: str) -> None:
    """Send systemd sd_notify message if running under systemd."""
    try:
        import sdnotify  # type: ignore[import]
        sdnotify.SystemdNotifier().notify(state)
    except Exception:
        pass
