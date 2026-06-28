"""Telemetry buffer and flush for nexora-agent.

Collects samples from hardware drivers or user code and POSTs them in
batches to device-service. When offline, samples are pushed to the
offline queue for later replay.
"""
import asyncio
import logging
import time
from typing import Any

import httpx

from nexora_agent import config, offline_queue

logger = logging.getLogger("nexora-agent.telemetry")

# In-memory buffer: list of {"metric": str, "value": float, "unit": str|None, "ts": float}
_buffer: list[dict] = []
_lock = asyncio.Lock()


def record(metric: str, value: float, unit: str | None = None) -> None:
    """Add a single sample to the buffer (thread-safe for same event loop)."""
    _buffer.append({"metric": metric, "value": value, "unit": unit, "ts": time.time()})


async def flush(device_id: str, server_url: str) -> bool:
    """Send buffered samples to device-service. Returns True on success."""
    async with _lock:
        if not _buffer:
            return True
        batch = list(_buffer)
        _buffer.clear()

    samples = [
        {k: v for k, v in s.items() if v is not None}
        for s in batch
    ]
    payload = {"device_id": device_id, "samples": samples}

    try:
        async with httpx.AsyncClient(base_url=server_url, timeout=10.0) as client:
            resp = await client.post(
                f"/api/v2/devices/{device_id}/telemetry",
                json={"samples": samples},
            )
            if resp.status_code in (200, 202):
                logger.debug("Flushed %d telemetry samples", len(samples))
                return True
            else:
                logger.warning("Telemetry flush %s — queuing offline", resp.status_code)
                offline_queue.enqueue("telemetry", payload)
                return False
    except Exception as exc:
        logger.warning("Telemetry flush failed, queuing offline: %s", exc)
        # Put samples back into queue
        async with _lock:
            _buffer.extend(batch)
        offline_queue.enqueue("telemetry", payload)
        return False


async def flush_loop(device_id: str, server_url: str) -> None:
    """Background task: flush telemetry buffer every TELEMETRY_FLUSH_INTERVAL seconds."""
    logger.info(
        "Telemetry flush loop started (interval=%.1fs, batch=%d)",
        config.TELEMETRY_FLUSH_INTERVAL,
        config.TELEMETRY_BATCH_SIZE,
    )
    while True:
        await asyncio.sleep(config.TELEMETRY_FLUSH_INTERVAL)
        try:
            await flush(device_id, server_url)
        except Exception as exc:
            logger.error("Telemetry flush loop error: %s", exc)
