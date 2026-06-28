import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import aiokafka
import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from common.internal_auth import _is_valid_internal_key
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest
from sqlalchemy import exc as sa_exc, func, select
from common.audit import emit_audit_event
from common.auth.context import RequestAuthenticator, auth_settings_from_env, current_user_from_request

from fleet_service.core.config import (
    AUTH_DEV_BYPASS_ENABLED, AUTH_ENABLED,
    DEVICE_SERVICE_URL, ENVIRONMENT, KAFKA_BOOTSTRAP_SERVERS, KAFKA_ENABLED,
    KAFKA_REQUIRED,
)
from fleet_service.core.database import Base, engine, SessionLocal, ensure_fleet_columns
from fleet_service.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL
import fleet_service.core.events as _events
from fleet_service.models.fleet import Fleet
from fleet_service.models.fleet_member import FleetMember

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("fleet-service")
AUTH_SETTINGS = auth_settings_from_env()
authenticator = RequestAuthenticator(AUTH_SETTINGS)

app = FastAPI(title="Fleet Service", version="0.1.0")


@app.on_event("startup")
async def startup() -> None:
    if ENVIRONMENT == "production" and not AUTH_ENABLED:
        raise RuntimeError("AUTH_ENABLED=false is not allowed when ENVIRONMENT=production")
    if AUTH_DEV_BYPASS_ENABLED:
        if ENVIRONMENT == "production":
            raise RuntimeError("AUTH_DEV_BYPASS_ENABLED=true is not allowed when ENVIRONMENT=production")
        logger.warning("AUTH DEV BYPASS ENABLED — NOT FOR PRODUCTION")
    Base.metadata.create_all(bind=engine)
    ensure_fleet_columns()
    if not KAFKA_ENABLED:
        logger.info("Kafka publisher disabled by configuration")
        return
    _events.producer = aiokafka.AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    try:
        await _events.producer.start()
    except Exception:
        logger.exception("Failed to connect Kafka producer")
        _events.producer = None
        if KAFKA_REQUIRED:
            raise


@app.on_event("shutdown")
async def shutdown() -> None:
    if _events.producer:
        await _events.producer.stop()
        _events.producer = None


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    return await authenticator.middleware(request, call_next)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or uuid4().hex
    correlation_id = request.headers.get("x-correlation-id", trace_id)
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    response.headers["x-trace-id"] = trace_id
    response.headers["x-correlation-id"] = correlation_id
    HTTP_REQUESTS_TOTAL.labels(
        "fleet-service", request.method, request.url.path, str(response.status_code)
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        "fleet-service", request.method, request.url.path
    ).observe(elapsed)
    logger.info(json.dumps({
        "service": "fleet-service",
        "trace_id": trace_id,
        "correlation_id": correlation_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_s": round(elapsed, 6),
    }))
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "fleet-service"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(select(func.count()).select_from(Fleet))
    return {"status": "ready", "service": "fleet-service", "database": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")


def _fleet_to_dict(f: Fleet) -> dict[str, Any]:
    return {
        "id": f.id,
        "name": f.name,
        "description": f.description,
        "owner_id": f.owner_id,
        "tenant_id": f.tenant_id,
    }


def _ensure_fleet_visible(fleet: Fleet | None, request: Request) -> Fleet:
    if not fleet:
        raise HTTPException(status_code=404, detail="fleet not found")
    user = current_user_from_request(request)
    if fleet.tenant_id and fleet.tenant_id != user.tenant_id and not user.is_platform_admin(AUTH_SETTINGS):
        raise HTTPException(status_code=404, detail="fleet not found")
    return fleet


@app.get("/api/v2/fleets")
async def list_fleets(request: Request, tenant_id: str | None = Query(default=None)) -> dict[str, Any]:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        q = select(Fleet)
        if user.is_platform_admin(AUTH_SETTINGS):
            if tenant_id:
                q = q.where(Fleet.tenant_id == tenant_id)
        else:
            q = q.where(Fleet.tenant_id == user.tenant_id)
        items = db.execute(q).scalars().all()
        payload = [_fleet_to_dict(f) for f in items]
    return {"items": payload, "total": len(payload)}


@app.post("/api/v2/fleets", status_code=201)
async def create_fleet(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    fleet_id = str(uuid4())
    fleet = Fleet(
        id=fleet_id,
        name=payload.get("name", "default-fleet"),
        description=payload.get("description"),
        owner_id=user.user_id,
        tenant_id=user.tenant_id,
    )
    with SessionLocal() as db:
        db.add(fleet)
        db.commit()
    response = _fleet_to_dict(fleet)
    emit_audit_event(
        service="fleet-service",
        action="fleet.created",
        resource_type="fleet",
        resource_id=fleet.id,
        tenant_id=fleet.tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )
    await _events.publish_event("created", fleet.id, response)
    return response


@app.get("/api/v2/fleets/{fleet_id}")
async def get_fleet(fleet_id: str, request: Request) -> dict[str, Any]:
    with SessionLocal() as db:
        fleet = db.get(Fleet, fleet_id)
    return _fleet_to_dict(_ensure_fleet_visible(fleet, request))


@app.patch("/api/v2/fleets/{fleet_id}")
async def update_fleet(fleet_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        fleet = db.get(Fleet, fleet_id)
        _ensure_fleet_visible(fleet, request)
        if "name" in payload and payload["name"]:
            fleet.name = payload["name"]
        if "description" in payload:
            fleet.description = payload.get("description")
        db.commit()
        db.refresh(fleet)
    response = _fleet_to_dict(fleet)
    emit_audit_event(
        service="fleet-service",
        action="fleet.updated",
        resource_type="fleet",
        resource_id=fleet.id,
        tenant_id=fleet.tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )
    await _events.publish_event("updated", fleet.id, response)
    return response


@app.delete("/api/v2/fleets/{fleet_id}", status_code=204)
async def delete_fleet(fleet_id: str, request: Request) -> None:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        fleet = db.get(Fleet, fleet_id)
        _ensure_fleet_visible(fleet, request)
        deleted_payload = _fleet_to_dict(fleet)
        db.delete(fleet)
        db.commit()
    emit_audit_event(
        service="fleet-service",
        action="fleet.deleted",
        resource_type="fleet",
        resource_id=fleet_id,
        tenant_id=deleted_payload.get("tenant_id"),
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )
    await _events.publish_event("deleted", fleet_id, deleted_payload)


# ── Fleet Membership ────────────────────────────────────────────────────────────────────────────

@app.post("/api/v2/fleets/{fleet_id}/members", status_code=201)
async def add_fleet_member(fleet_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    device_id = payload.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    with SessionLocal() as db:
        fleet = db.get(Fleet, fleet_id)
        _ensure_fleet_visible(fleet, request)
        member = FleetMember(
            id=str(uuid4()),
            fleet_id=fleet_id,
            device_id=device_id,
            joined_at=datetime.now(timezone.utc),
        )
        db.add(member)
        try:
            db.commit()
        except sa_exc.IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="device already in fleet")
        db.refresh(member)
    response = {"id": member.id, "fleet_id": member.fleet_id, "device_id": member.device_id,
                "joined_at": member.joined_at.isoformat() if member.joined_at else None}
    emit_audit_event(
        service="fleet-service",
        action="fleet.member_added",
        resource_type="fleet",
        resource_id=fleet_id,
        tenant_id=fleet.tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
        reason=f"device_id={device_id}",
    )
    await _events.publish_event("member_added", fleet_id, response)
    return response


@app.get("/api/v2/fleets/{fleet_id}/members")
async def list_fleet_members(fleet_id: str, request: Request) -> dict[str, Any]:
    with SessionLocal() as db:
        fleet = db.get(Fleet, fleet_id)
        if fleet is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Fleet not found")
        # Internal services (execution-service) call this with X-Internal-Key.
        if not _is_valid_internal_key(request.headers.get("x-internal-key")):
            _ensure_fleet_visible(fleet, request)
        members = db.execute(
            select(FleetMember).where(FleetMember.fleet_id == fleet_id)
        ).scalars().all()
        items = [
            {"id": m.id, "fleet_id": m.fleet_id, "device_id": m.device_id,
             "joined_at": m.joined_at.isoformat() if m.joined_at else None}
            for m in members
        ]
    return {"fleet_id": fleet_id, "items": items, "total": len(items)}


@app.delete("/api/v2/fleets/{fleet_id}/members/{device_id}", status_code=204)
async def remove_fleet_member(fleet_id: str, device_id: str, request: Request) -> None:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        fleet = db.get(Fleet, fleet_id)
        _ensure_fleet_visible(fleet, request)
        member = db.execute(
            select(FleetMember).where(
                FleetMember.fleet_id == fleet_id,
                FleetMember.device_id == device_id,
            )
        ).scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=404, detail="device not in fleet")
        db.delete(member)
        db.commit()
    emit_audit_event(
        service="fleet-service",
        action="fleet.member_removed",
        resource_type="fleet",
        resource_id=fleet_id,
        tenant_id=fleet.tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
        reason=f"device_id={device_id}",
    )
    await _events.publish_event("member_removed", fleet_id, {"fleet_id": fleet_id, "device_id": device_id})


@app.get("/api/v2/devices/{device_id}/fleets")
async def list_device_fleets(device_id: str, request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        rows = db.execute(
            select(FleetMember).where(FleetMember.device_id == device_id)
        ).scalars().all()
        fleet_ids = [m.fleet_id for m in rows]
        q = select(Fleet).where(Fleet.id.in_(fleet_ids))
        if not user.is_platform_admin(AUTH_SETTINGS):
            q = q.where(Fleet.tenant_id == user.tenant_id)
        fleets = db.execute(q).scalars().all()
        items = [_fleet_to_dict(f) for f in fleets]
    return {"device_id": device_id, "items": items, "total": len(items)}


# ---------------------------------------------------------------------------
# Fleet analytics — aggregate device health and telemetry across a fleet
# ---------------------------------------------------------------------------

@app.get("/api/v2/fleets/{fleet_id}/health")
async def fleet_health(fleet_id: str, request: Request) -> dict[str, Any]:
    """Aggregate online/offline/unknown health status for all fleet members.

    Calls device-service for each member in parallel and returns per-device
    status plus a fleet-level summary (online_count, offline_count, unknown_count).
    """
    with SessionLocal() as db:
        fleet = db.get(Fleet, fleet_id)
        _ensure_fleet_visible(fleet, request)
        members = db.execute(
            select(FleetMember).where(FleetMember.fleet_id == fleet_id)
        ).scalars().all()
        device_ids = [m.device_id for m in members]

    if not device_ids:
        return {
            "fleet_id": fleet_id,
            "fleet_name": fleet.name,
            "summary": {"online": 0, "offline": 0, "unknown": 0, "total": 0},
            "devices": [],
        }

    async def _fetch_device(client: httpx.AsyncClient, device_id: str) -> dict[str, Any]:
        try:
            resp = await client.get(
                f"{DEVICE_SERVICE_URL}/api/v2/devices/{device_id}",
                timeout=5.0,
            )
            if resp.status_code == 200:
                d = resp.json()
                return {
                    "device_id": device_id,
                    "name": d.get("name"),
                    "status": d.get("status", "unknown"),
                    "last_seen": d.get("last_seen"),
                    "device_type": d.get("device_type"),
                }
        except Exception:
            pass
        return {"device_id": device_id, "status": "unknown", "name": None, "last_seen": None, "device_type": None}

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_fetch_device(client, did) for did in device_ids])

    summary: dict[str, int] = {"online": 0, "offline": 0, "unknown": 0, "total": len(results)}
    for r in results:
        s = r.get("status", "unknown")
        if s == "online":
            summary["online"] += 1
        elif s == "offline":
            summary["offline"] += 1
        else:
            summary["unknown"] += 1

    return {
        "fleet_id": fleet_id,
        "fleet_name": fleet.name,
        "summary": summary,
        "devices": results,
    }


@app.get("/api/v2/fleets/{fleet_id}/telemetry/latest")
async def fleet_telemetry_latest(
    fleet_id: str,
    request: Request,
    metric: str = Query(..., description="Metric name to aggregate across the fleet"),
) -> dict[str, Any]:
    """Return the latest value of a given metric for every fleet member.

    Aggregates min/max/avg/median across devices that have reported the metric,
    and lists per-device readings. Useful for dashboards showing fleet-wide
    sensor state (e.g. temperature of all nodes).
    """
    with SessionLocal() as db:
        fleet = db.get(Fleet, fleet_id)
        _ensure_fleet_visible(fleet, request)
        members = db.execute(
            select(FleetMember).where(FleetMember.fleet_id == fleet_id)
        ).scalars().all()
        device_ids = [m.device_id for m in members]

    if not device_ids:
        return {
            "fleet_id": fleet_id,
            "metric": metric,
            "aggregate": None,
            "devices": [],
        }

    async def _fetch_latest(client: httpx.AsyncClient, device_id: str) -> dict[str, Any]:
        try:
            resp = await client.get(
                f"{DEVICE_SERVICE_URL}/api/v2/devices/{device_id}/telemetry/latest",
                timeout=5.0,
            )
            if resp.status_code == 200:
                readings = resp.json().get("readings", {})
                if metric in readings:
                    r = readings[metric]
                    return {"device_id": device_id, "value": r["value"], "ts": r["ts"], "tags": r.get("tags")}
        except Exception:
            pass
        return {"device_id": device_id, "value": None, "ts": None, "tags": None}

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_fetch_latest(client, did) for did in device_ids])

    values = [r["value"] for r in results if r["value"] is not None]
    aggregate = None
    if values:
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        median = (sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2)
        aggregate = {
            "count": n,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": round(sum(sorted_vals) / n, 6),
            "median": median,
        }

    return {
        "fleet_id": fleet_id,
        "fleet_name": fleet.name,
        "metric": metric,
        "aggregate": aggregate,
        "devices": results,
    }
