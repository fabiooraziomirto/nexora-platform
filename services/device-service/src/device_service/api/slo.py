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


class SLOAssistantMetric(BaseModel):
    metric: str
    violations: int
    latest_observed_value: Optional[float] = None
    threshold: Optional[float] = None
    operator: Optional[str] = None
    severity: str
    recommendation: str


class SLOAssistantResponse(BaseModel):
    device_id: str
    hours: int
    total_violations: int
    status: str
    top_metrics: list[SLOAssistantMetric]
    recommendations: list[str]
    suggested_runbook_steps: list[dict]


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


@router.get("/devices/{device_id}/slos/assistant", response_model=SLOAssistantResponse)
async def slo_assistant(
    device_id: UUID,
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """Return actionable remediation hints based on recent SLO violations."""
    await _assert_device_exists(device_id, db)

    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(SLOViolation)
        .where(
            and_(
                SLOViolation.device_id == str(device_id),
                SLOViolation.violated_at >= since,
            )
        )
        .order_by(SLOViolation.violated_at.desc())
        .limit(limit)
    )
    violations = result.scalars().all()

    if not violations:
        return SLOAssistantResponse(
            device_id=str(device_id),
            hours=hours,
            total_violations=0,
            status="healthy",
            top_metrics=[],
            recommendations=[
                "No recent SLO violations detected. Keep current thresholds and monitor trend weekly.",
            ],
            suggested_runbook_steps=[
                {"name": "health-check", "execution_type": "command", "command": "echo health-ok"},
            ],
        )

    slo_rows = await db.execute(
        select(DeviceSLO).where(DeviceSLO.device_id == str(device_id))
    )
    slo_by_id = {s.id: s for s in slo_rows.scalars().all()}

    metric_agg: dict[str, dict] = {}
    for v in violations:
        data = metric_agg.setdefault(v.metric, {
            "violations": 0,
            "latest_observed_value": v.observed_value,
            "threshold": v.threshold,
            "operator": v.operator,
        })
        data["violations"] += 1

    top_items = sorted(metric_agg.items(), key=lambda x: x[1]["violations"], reverse=True)[:5]
    top_metrics: list[SLOAssistantMetric] = []
    recommendations: list[str] = []
    runbook_steps: list[dict] = []

    for metric, data in top_items:
        count = int(data["violations"])
        severity = "high" if count >= 5 else "medium" if count >= 2 else "low"

        operator = str(data.get("operator") or "")
        threshold = data.get("threshold")
        latest_value = data.get("latest_observed_value")

        if operator in {"lt", "lte"}:
            rec = f"Reduce {metric} pressure: latest {latest_value} breaches {operator} {threshold}."
        elif operator in {"gt", "gte"}:
            rec = f"Increase {metric} floor: latest {latest_value} breaches {operator} {threshold}."
        else:
            rec = f"Stabilize {metric}: latest {latest_value} deviates from expected threshold {threshold}."

        top_metrics.append(SLOAssistantMetric(
            metric=metric,
            violations=count,
            latest_observed_value=latest_value,
            threshold=threshold,
            operator=operator,
            severity=severity,
            recommendation=rec,
        ))

        recommendations.append(f"{metric}: {rec}")
        runbook_steps.append({
            "name": f"diagnose-{metric}",
            "execution_type": "command",
            "command": f"echo diagnose-{metric}",
        })

    # Add a generic verification step at the end.
    runbook_steps.append({
        "name": "verify-slo-stability",
        "execution_type": "command",
        "command": "echo verify-slo-stability",
    })

    return SLOAssistantResponse(
        device_id=str(device_id),
        hours=hours,
        total_violations=len(violations),
        status="attention_required",
        top_metrics=top_metrics,
        recommendations=recommendations,
        suggested_runbook_steps=runbook_steps,
    )
