"""SLO (Service Level Objective) definition and violation tracking.

Operators define per-device metric assertions; when telemetry is ingested the
engine evaluates each SLO and records a SLOViolation on breach.

CRUD:
  POST   /devices/{id}/slos               — define an SLO
  GET    /devices/{id}/slos               — list SLOs for device
  PATCH  /devices/{id}/slos/{slo_id}      — update threshold / enable / disable
  DELETE /devices/{id}/slos/{slo_id}      — remove SLO
  GET    /devices/{id}/slos/violations    — recent violations (last 24 h default)
"""
import operator as _op
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from device_service.core.database import get_db
from device_service.core.events import event_bus
from device_service.models.device import Device
from device_service.models.device_slo import DeviceSLO, SLOViolation

logger = structlog.get_logger()
router = APIRouter()

_OPERATORS = {
    "lt": _op.lt,
    "lte": _op.le,
    "gt": _op.gt,
    "gte": _op.ge,
    "eq": _op.eq,
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SLOCreate(BaseModel):
    metric: str = Field(..., min_length=1, max_length=128)
    operator: str = Field(..., pattern="^(lt|lte|gt|gte|eq)$")
    threshold: float
    description: Optional[str] = None


class SLOUpdate(BaseModel):
    operator: Optional[str] = Field(None, pattern="^(lt|lte|gt|gte|eq)$")
    threshold: Optional[float] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class SLOResponse(BaseModel):
    id: str
    device_id: str
    metric: str
    operator: str
    threshold: float
    description: Optional[str]
    enabled: bool
    created_at: datetime


class SLOViolationResponse(BaseModel):
    id: str
    slo_id: str
    device_id: str
    metric: str
    observed_value: float
    threshold: float
    operator: str
    violated_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _assert_device_exists(device_id: UUID, db: AsyncSession) -> None:
    result = await db.execute(select(Device).where(Device.id == str(device_id)))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Device not found")


def _slo_to_response(s: DeviceSLO) -> SLOResponse:
    return SLOResponse(
        id=s.id,
        device_id=s.device_id,
        metric=s.metric,
        operator=s.operator,
        threshold=s.threshold,
        description=s.description,
        enabled=s.enabled,
        created_at=s.created_at,
    )


def _violation_to_response(v: SLOViolation) -> SLOViolationResponse:
    return SLOViolationResponse(
        id=v.id,
        slo_id=v.slo_id,
        device_id=v.device_id,
        metric=v.metric,
        observed_value=v.observed_value,
        threshold=v.threshold,
        operator=v.operator,
        violated_at=v.violated_at,
    )


async def evaluate_slos(
    device_id: str,
    samples: list[tuple[str, float, datetime]],  # (metric, value, ts)
    db: AsyncSession,
) -> list[SLOViolation]:
    """Check samples against enabled SLOs; persist and return violations."""
    result = await db.execute(
        select(DeviceSLO).where(
            and_(DeviceSLO.device_id == device_id, DeviceSLO.enabled.is_(True))
        )
    )
    slos = result.scalars().all()
    if not slos:
        return []

    # Build index: metric → list[DeviceSLO]
    slo_index: dict[str, list[DeviceSLO]] = {}
    for slo in slos:
        slo_index.setdefault(slo.metric, []).append(slo)

    violations: list[SLOViolation] = []
    for metric, value, ts in samples:
        for slo in slo_index.get(metric, []):
            fn = _OPERATORS.get(slo.operator)
            if fn is None:
                continue
            if not fn(value, slo.threshold):
                v = SLOViolation(
                    id=str(uuid4()),
                    slo_id=slo.id,
                    device_id=device_id,
                    metric=metric,
                    observed_value=value,
                    threshold=slo.threshold,
                    operator=slo.operator,
                    violated_at=ts,
                )
                db.add(v)
                violations.append(v)

    if violations:
        await db.flush()

    return violations


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/devices/{device_id}/slos", response_model=SLOResponse, status_code=201)
async def create_slo(
    device_id: UUID,
    body: SLOCreate,
    db: AsyncSession = Depends(get_db),
):
    """Define a new SLO for a device metric."""
    await _assert_device_exists(device_id, db)
    slo = DeviceSLO(
        id=str(uuid4()),
        device_id=str(device_id),
        metric=body.metric,
        operator=body.operator,
        threshold=body.threshold,
        description=body.description,
        enabled=True,
    )
    db.add(slo)
    await db.commit()
    await db.refresh(slo)
    logger.info("slo.created", device_id=str(device_id), metric=body.metric,
                operator=body.operator, threshold=body.threshold)
    return _slo_to_response(slo)


@router.get("/devices/{device_id}/slos", response_model=list[SLOResponse])
async def list_slos(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all SLOs defined for a device."""
    await _assert_device_exists(device_id, db)
    result = await db.execute(
        select(DeviceSLO).where(DeviceSLO.device_id == str(device_id))
        .order_by(DeviceSLO.created_at.desc())
    )
    return [_slo_to_response(s) for s in result.scalars().all()]


@router.patch("/devices/{device_id}/slos/{slo_id}", response_model=SLOResponse)
async def update_slo(
    device_id: UUID,
    slo_id: str,
    body: SLOUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an SLO's threshold, operator, or enabled state."""
    await _assert_device_exists(device_id, db)
    result = await db.execute(
        select(DeviceSLO).where(
            and_(DeviceSLO.id == slo_id, DeviceSLO.device_id == str(device_id))
        )
    )
    slo = result.scalar_one_or_none()
    if not slo:
        raise HTTPException(status_code=404, detail="SLO not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(slo, field, value)
    await db.commit()
    await db.refresh(slo)
    return _slo_to_response(slo)


@router.delete("/devices/{device_id}/slos/{slo_id}", status_code=204)
async def delete_slo(
    device_id: UUID,
    slo_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove an SLO definition (violations history is preserved)."""
    await _assert_device_exists(device_id, db)
    result = await db.execute(
        select(DeviceSLO).where(
            and_(DeviceSLO.id == slo_id, DeviceSLO.device_id == str(device_id))
        )
    )
    slo = result.scalar_one_or_none()
    if slo:
        await db.delete(slo)
        await db.commit()


@router.get("/devices/{device_id}/slos/violations", response_model=list[SLOViolationResponse])
async def list_violations(
    device_id: UUID,
    hours: int = Query(24, ge=1, le=720),
    metric: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """Return recent SLO violations for a device (default: last 24 h)."""
    await _assert_device_exists(device_id, db)
    since = datetime.utcnow() - timedelta(hours=hours)
    conditions = [
        SLOViolation.device_id == str(device_id),
        SLOViolation.violated_at >= since,
    ]
    if metric:
        conditions.append(SLOViolation.metric == metric)
    result = await db.execute(
        select(SLOViolation)
        .where(and_(*conditions))
        .order_by(SLOViolation.violated_at.desc())
        .limit(limit)
    )
    return [_violation_to_response(v) for v in result.scalars().all()]
