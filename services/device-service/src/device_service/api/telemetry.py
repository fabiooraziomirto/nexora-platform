"""Telemetry ingestion and query endpoints.

Devices push time-series readings here; operators query historical windows.

Ingest:  POST /devices/{id}/telemetry          — one or many samples in one call
Query:   GET  /devices/{id}/telemetry          — paginated, filterable by metric + time window
Latest:  GET  /devices/{id}/telemetry/latest   — most-recent value per metric
"""
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from device_service.core.database import get_db
from device_service.core.events import event_bus
from device_service.core.rate_limit import limiter
from device_service.models.device import Device
from device_service.models.device_telemetry import DeviceTelemetry

logger = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TelemetrySample(BaseModel):
    metric: str = Field(..., min_length=1, max_length=128, description="Metric name, e.g. 'temperature'")
    value: float
    ts: Optional[datetime] = Field(None, description="Sample timestamp (UTC). Defaults to server time.")
    tags: Optional[dict] = None


class TelemetryIngestRequest(BaseModel):
    samples: list[TelemetrySample] = Field(..., min_length=1, max_length=500)


class TelemetrySampleResponse(BaseModel):
    id: str
    device_id: str
    metric: str
    value: float
    ts: datetime
    tags: Optional[dict]


class TelemetryQueryResponse(BaseModel):
    device_id: str
    metric: Optional[str]
    samples: list[TelemetrySampleResponse]
    count: int
    from_ts: Optional[datetime]
    to_ts: Optional[datetime]


class TelemetryLatestResponse(BaseModel):
    device_id: str
    readings: dict[str, dict]  # metric -> {value, ts, tags}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _assert_device_exists(device_id: UUID, db: AsyncSession) -> None:
    result = await db.execute(select(Device).where(Device.id == str(device_id)))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Device not found")


def _row_to_response(row: DeviceTelemetry) -> TelemetrySampleResponse:
    tags = None
    if row.tags:
        try:
            tags = json.loads(row.tags)
        except (ValueError, TypeError):
            tags = None
    return TelemetrySampleResponse(
        id=row.id,
        device_id=row.device_id,
        metric=row.metric,
        value=row.value,
        ts=row.ts,
        tags=tags,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/devices/{device_id}/telemetry", status_code=202)
@limiter.limit("60/minute")
async def ingest_telemetry(
    request: Request,
    device_id: UUID,
    body: TelemetryIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest one or more telemetry samples from a device.

    Accepts up to 500 samples per call. Timestamps default to server UTC if omitted.
    Returns a 202 with a summary of ingested sample counts per metric.
    """
    await _assert_device_exists(device_id, db)

    now = datetime.now(timezone.utc)
    rows = []
    for s in body.samples:
        ts = s.ts or now
        # Strip timezone info for DB storage (stored as UTC naive)
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        rows.append(DeviceTelemetry(
            id=str(uuid4()),
            device_id=str(device_id),
            metric=s.metric,
            value=s.value,
            ts=ts,
            tags=json.dumps(s.tags) if s.tags else None,
        ))

    db.add_all(rows)
    await db.commit()

    metrics_summary: dict[str, int] = {}
    for r in rows:
        metrics_summary[r.metric] = metrics_summary.get(r.metric, 0) + 1

    logger.info(
        "telemetry.ingested",
        device_id=str(device_id),
        samples=len(rows),
        metrics=list(metrics_summary.keys()),
    )

    await event_bus.publish(
        "device.telemetry.ingested",
        {
            "device_id": str(device_id),
            "sample_count": len(rows),
            "metrics": metrics_summary,
            "ingested_at": now.isoformat(),
        },
    )

    return {"device_id": str(device_id), "ingested": len(rows), "metrics": metrics_summary}


@router.get("/devices/{device_id}/telemetry", response_model=TelemetryQueryResponse)
@limiter.limit("120/minute")
async def query_telemetry(
    request: Request,
    device_id: UUID,
    metric: Optional[str] = Query(None, description="Filter by metric name"),
    from_ts: Optional[datetime] = Query(None, description="Start of time window (UTC)"),
    to_ts: Optional[datetime] = Query(None, description="End of time window (UTC). Defaults to now."),
    hours: Optional[int] = Query(None, ge=1, le=720, description="Shorthand: last N hours (ignored if from_ts set)"),
    limit: int = Query(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Query telemetry samples for a device.

    Defaults to the last 24 hours when no time window is provided.
    """
    await _assert_device_exists(device_id, db)

    now_naive = datetime.utcnow()

    # Resolve time window
    if from_ts is None:
        h = hours if hours is not None else 24
        from_ts_naive = now_naive - timedelta(hours=h)
    else:
        from_ts_naive = from_ts.replace(tzinfo=None) if from_ts.tzinfo else from_ts

    if to_ts is None:
        to_ts_naive = now_naive
    else:
        to_ts_naive = to_ts.replace(tzinfo=None) if to_ts.tzinfo else to_ts

    conditions = [
        DeviceTelemetry.device_id == str(device_id),
        DeviceTelemetry.ts >= from_ts_naive,
        DeviceTelemetry.ts <= to_ts_naive,
    ]
    if metric:
        conditions.append(DeviceTelemetry.metric == metric)

    query = (
        select(DeviceTelemetry)
        .where(and_(*conditions))
        .order_by(DeviceTelemetry.ts.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.scalars().all()

    return TelemetryQueryResponse(
        device_id=str(device_id),
        metric=metric,
        samples=[_row_to_response(r) for r in rows],
        count=len(rows),
        from_ts=from_ts_naive,
        to_ts=to_ts_naive,
    )


@router.get("/devices/{device_id}/telemetry/latest", response_model=TelemetryLatestResponse)
@limiter.limit("120/minute")
async def latest_telemetry(
    request: Request,
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return the most-recent value for each metric reported by the device."""
    await _assert_device_exists(device_id, db)

    # Subquery: max ts per metric for this device
    sub = (
        select(DeviceTelemetry.metric, func.max(DeviceTelemetry.ts).label("max_ts"))
        .where(DeviceTelemetry.device_id == str(device_id))
        .group_by(DeviceTelemetry.metric)
        .subquery()
    )
    query = select(DeviceTelemetry).join(
        sub,
        and_(
            DeviceTelemetry.device_id == str(device_id),
            DeviceTelemetry.metric == sub.c.metric,
            DeviceTelemetry.ts == sub.c.max_ts,
        ),
    )
    result = await db.execute(query)
    rows = result.scalars().all()

    readings: dict[str, dict] = {}
    for row in rows:
        tags = None
        if row.tags:
            try:
                tags = json.loads(row.tags)
            except (ValueError, TypeError):
                pass
        readings[row.metric] = {"value": row.value, "ts": row.ts.isoformat(), "tags": tags}

    return TelemetryLatestResponse(device_id=str(device_id), readings=readings)
