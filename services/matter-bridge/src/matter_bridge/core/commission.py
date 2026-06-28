"""Matter commissioning state machine.

Manages in-progress and completed commissioning sessions, delegates to
the python-matter-server client for CHIP operations, and registers the
resulting device on device-service.
"""
import asyncio
import logging
import time
from typing import Any

import httpx

from matter_bridge.core import config

logger = logging.getLogger("matter-bridge.commission")

# In-memory commissioning registry: commissioning_id → state dict.
# In production this would be Redis-backed, but for the initial implementation
# in-memory is sufficient since a single bridge instance manages one fabric.
_sessions: dict[str, dict[str, Any]] = {}

# Monotonically incrementing node ID for CHIP fabric assignment.
# matter-server may assign IDs automatically; this is a fallback.
_next_node_id: int = 1


def _alloc_node_id() -> int:
    global _next_node_id
    nid = _next_node_id
    _next_node_id += 1
    return nid


def get_session(commissioning_id: str) -> dict[str, Any] | None:
    return _sessions.get(commissioning_id)


def list_sessions() -> list[dict[str, Any]]:
    return list(_sessions.values())


async def start_commissioning(
    commissioning_id: str,
    setup_code: str | None,
    manual_code: str | None,
    name: str,
    description: str | None,
    owner_id: str,
    tenant_id: str | None,
    matter_client: Any | None,
) -> dict[str, Any]:
    """Register a pending session and kick off the commissioning task."""
    node_id = _alloc_node_id()
    session = {
        "commissioning_id": commissioning_id,
        "status": "pending",
        "node_id": node_id,
        "device_id": None,
        "error": None,
        "name": name,
        "description": description,
        "owner_id": owner_id,
        "tenant_id": tenant_id,
        "started_at": time.time(),
    }
    _sessions[commissioning_id] = session

    asyncio.create_task(
        _run_commissioning(session, setup_code, manual_code, matter_client),
        name=f"commission-{commissioning_id}",
    )

    return session


async def _run_commissioning(
    session: dict[str, Any],
    setup_code: str | None,
    manual_code: str | None,
    matter_client: Any | None,
) -> None:
    """Execute the CHIP commissioning flow and register the device on success."""
    commissioning_id = session["commissioning_id"]
    node_id = session["node_id"]

    try:
        if matter_client is not None:
            code = setup_code or manual_code
            logger.info("Starting CHIP commissioning cid=%s node=%s", commissioning_id, node_id)
            await matter_client.commission_with_code(code, node_id)
            logger.info("CHIP commissioning complete cid=%s", commissioning_id)

            node_info = await matter_client.get_node(node_id)
            protocol_meta = _extract_protocol_meta(node_id, node_info)
        else:
            logger.info("Mock commissioning (no matter-server) cid=%s", commissioning_id)
            await asyncio.sleep(0.5)
            protocol_meta = {
                "fabric_id": "nexora-dev",
                "node_id": node_id,
                "endpoints": [
                    {"id": 0, "clusters": ["BasicInformation", "GeneralCommissioning"]},
                    {"id": 1, "clusters": ["OnOff", "LevelControl", "TemperatureMeasurement"]},
                ],
                "attributes": {
                    "BasicInformation.NodeLabel": session["name"],
                    "OnOff.OnOff": False,
                    "LevelControl.CurrentLevel": 254,
                    "TemperatureMeasurement.MeasuredValue": 2200,  # 22.00 °C × 100
                },
            }

        device_id = await _register_device(session, protocol_meta)

        session["status"] = "commissioned"
        session["device_id"] = device_id
        logger.info("Commissioning succeeded cid=%s device=%s", commissioning_id, device_id)

    except Exception as exc:
        session["status"] = "failed"
        session["error"] = str(exc)
        logger.error("Commissioning failed cid=%s: %s", commissioning_id, exc)


def _extract_protocol_meta(node_id: int, node_info: Any) -> dict:
    """Convert python-matter-server node info into Nexora protocol_meta."""
    endpoints = []
    attributes: dict = {}

    try:
        for ep_id, ep in (node_info.endpoints or {}).items():
            cluster_names = list(ep.clusters.keys()) if ep.clusters else []
            endpoints.append({"id": ep_id, "clusters": cluster_names})
            for cluster_name, cluster in (ep.clusters or {}).items():
                for attr_name, attr_val in (cluster.attributes or {}).items():
                    try:
                        attributes[f"{cluster_name}.{attr_name}"] = attr_val
                    except Exception:
                        pass
    except Exception as exc:
        logger.warning("Could not extract full node info: %s", exc)

    return {
        "fabric_id": "nexora",
        "node_id": node_id,
        "endpoints": endpoints,
        "attributes": attributes,
    }


async def _register_device(session: dict[str, Any], protocol_meta: dict) -> str:
    """Call device-service /agents/register to create the Matter device record."""
    payload = {
        "name": session["name"],
        "device_type": "matter",
        "metadata": {
            "commissioned_by": session.get("owner_id"),
            "commissioning_id": session["commissioning_id"],
        },
        "connection_protocol": "matter",
        "protocol_meta": protocol_meta,
        "owner_id": session.get("owner_id"),
        "tenant_id": session.get("tenant_id"),
    }
    headers = {"X-Bootstrap-Token": config.AGENT_BOOTSTRAP_TOKEN}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{config.DEVICE_SERVICE_URL}/api/v2/agents/register",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    return data["device_id"]
