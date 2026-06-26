import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from device_service.core.database import get_db
from device_service.core.events import event_bus
from device_service.models.device import Device
from device_service.models.device_shadow import DeviceShadow

logger = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas (local — shadow-specific, not shared with device schemas)
# ---------------------------------------------------------------------------

class ShadowDesiredUpdate(BaseModel):
    state: dict


class ShadowReportedUpdate(BaseModel):
    state: dict


class ShadowResponse(BaseModel):
    device_id: str
    desired: dict | None
    reported: dict | None
    delta: dict | None
    version: int
    desired_at: datetime | None
    reported_at: datetime | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_delta(desired: dict | None, reported: dict | None) -> dict:
    """Return keys present in desired whose value differs from reported."""
    if not desired:
        return {}
    reported = reported or {}
    return {k: v for k, v in desired.items() if reported.get(k) != v}


def _shadow_to_response(s: DeviceShadow) -> ShadowResponse:
    def _j(v):
        if v is None:
            return None
        return json.loads(v) if isinstance(v, str) else v

    return ShadowResponse(
        device_id=s.device_id,
        desired=_j(s.desired),
        reported=_j(s.reported),
        delta=_j(s.delta),
        version=s.version,
        desired_at=s.desired_at,
        reported_at=s.reported_at,
    )


async def _get_or_create_shadow(device_id: str, db: AsyncSession) -> DeviceShadow:
    result = await db.execute(
        select(DeviceShadow).where(DeviceShadow.device_id == device_id)
    )
    shadow = result.scalar_one_or_none()
    if not shadow:
        now = datetime.now(timezone.utc)
        shadow = DeviceShadow(device_id=device_id, version=1, created_at=now, updated_at=now)
        db.add(shadow)
        await db.flush()
    return shadow


async def _assert_device_exists(device_id: UUID, db: AsyncSession) -> None:
    result = await db.execute(select(Device).where(Device.id == str(device_id)))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Device not found")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/devices/{device_id}/shadow", response_model=ShadowResponse)
async def get_shadow(device_id: UUID, db: AsyncSession = Depends(get_db)):
    """Return the full shadow document: desired, reported, delta, and version."""
    await _assert_device_exists(device_id, db)
    result = await db.execute(
        select(DeviceShadow).where(DeviceShadow.device_id == str(device_id))
    )
    shadow = result.scalar_one_or_none()
    if not shadow:
        # Return an empty shadow rather than 404 — device exists but has no shadow yet
        return ShadowResponse(
            device_id=str(device_id),
            desired=None,
            reported=None,
            delta=None,
            version=0,
            desired_at=None,
            reported_at=None,
        )
    return _shadow_to_response(shadow)


@router.patch("/devices/{device_id}/shadow/desired", response_model=ShadowResponse)
async def update_desired(
    device_id: UUID,
    body: ShadowDesiredUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Merge-update the desired state (cloud → device intent).

    Uses a shallow merge: existing keys not present in the update are preserved.
    Set a key to null to remove it from desired.
    """
    await _assert_device_exists(device_id, db)
    shadow = await _get_or_create_shadow(str(device_id), db)

    existing_desired: dict = json.loads(shadow.desired) if shadow.desired else {}
    # Shallow merge: null values remove the key
    merged = {**existing_desired, **body.state}
    merged = {k: v for k, v in merged.items() if v is not None}

    existing_reported: dict = json.loads(shadow.reported) if shadow.reported else {}
    delta = _compute_delta(merged, existing_reported)

    now = datetime.now(timezone.utc)
    shadow.desired = json.dumps(merged)
    shadow.delta = json.dumps(delta)
    shadow.version = (shadow.version or 0) + 1
    shadow.desired_at = now
    shadow.updated_at = now

    await db.commit()
    await db.refresh(shadow)

    logger.info("shadow.desired_updated", device_id=str(device_id), version=shadow.version,
                delta_keys=list(delta.keys()))

    if delta:
        await event_bus.publish("device.shadow.delta", {
            "device_id": str(device_id),
            "version": shadow.version,
            "delta": delta,
        })

    return _shadow_to_response(shadow)


@router.post("/devices/{device_id}/shadow/reported", response_model=ShadowResponse, status_code=200)
async def update_reported(
    device_id: UUID,
    body: ShadowReportedUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Accept a reported-state update from the edge agent.

    Typically called from the board agent after applying desired config,
    or at heartbeat time to publish current sensor/runtime readings.
    """
    await _assert_device_exists(device_id, db)
    shadow = await _get_or_create_shadow(str(device_id), db)

    existing_reported: dict = json.loads(shadow.reported) if shadow.reported else {}
    merged_reported = {**existing_reported, **body.state}
    merged_reported = {k: v for k, v in merged_reported.items() if v is not None}

    existing_desired: dict = json.loads(shadow.desired) if shadow.desired else {}
    delta = _compute_delta(existing_desired, merged_reported)

    now = datetime.now(timezone.utc)
    shadow.reported = json.dumps(merged_reported)
    shadow.delta = json.dumps(delta)
    shadow.version = (shadow.version or 0) + 1
    shadow.reported_at = now
    shadow.updated_at = now

    await db.commit()
    await db.refresh(shadow)

    logger.info("shadow.reported_updated", device_id=str(device_id), version=shadow.version,
                delta_keys=list(delta.keys()))

    # Publish delta event — lets downstream services react when desired ≠ reported
    if delta:
        await event_bus.publish("device.shadow.delta", {
            "device_id": str(device_id),
            "version": shadow.version,
            "delta": delta,
        })
    else:
        await event_bus.publish("device.shadow.synced", {
            "device_id": str(device_id),
            "version": shadow.version,
        })

    return _shadow_to_response(shadow)


@router.delete("/devices/{device_id}/shadow", status_code=204)
async def delete_shadow(device_id: UUID, db: AsyncSession = Depends(get_db)):
    """Clear all shadow state for the device (desired, reported, delta)."""
    await _assert_device_exists(device_id, db)
    result = await db.execute(
        select(DeviceShadow).where(DeviceShadow.device_id == str(device_id))
    )
    shadow = result.scalar_one_or_none()
    if shadow:
        await db.delete(shadow)
        await db.commit()
        logger.info("shadow.deleted", device_id=str(device_id))
