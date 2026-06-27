import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import asyncio
import json
import logging
import time
from typing import Any
from uuid import uuid4

import aiokafka
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest
from sqlalchemy import func, select
from common.audit import emit_audit_event
from common.auth.context import RequestAuthenticator, auth_settings_from_env, current_user_from_request

from network_service.core.config import (
    AUTH_DEV_BYPASS_ENABLED, AUTH_ENABLED,
    ENVIRONMENT, KAFKA_BOOTSTRAP_SERVERS, KAFKA_ENABLED, KAFKA_REQUIRED,
)
from network_service.core.database import Base, engine, SessionLocal, ensure_port_columns
from network_service.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL
import network_service.core.events as _events
from network_service.models.port import Port

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("network-service")
AUTH_SETTINGS = auth_settings_from_env()
authenticator = RequestAuthenticator(AUTH_SETTINGS)

app = FastAPI(title="Network Service", version="0.1.0")


@app.on_event("startup")
async def startup() -> None:
    if ENVIRONMENT == "production" and not AUTH_ENABLED:
        raise RuntimeError("AUTH_ENABLED=false is not allowed when ENVIRONMENT=production")
    if AUTH_DEV_BYPASS_ENABLED:
        if ENVIRONMENT == "production":
            raise RuntimeError("AUTH_DEV_BYPASS_ENABLED=true is not allowed when ENVIRONMENT=production")
        logger.warning("AUTH DEV BYPASS ENABLED — NOT FOR PRODUCTION")
    Base.metadata.create_all(bind=engine)
    ensure_port_columns()
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
        "network-service", request.method, request.url.path, str(response.status_code)
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        "network-service", request.method, request.url.path
    ).observe(elapsed)
    logger.info(json.dumps({
        "service": "network-service",
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
    return {"status": "healthy", "service": "network-service"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(select(func.count()).select_from(Port))
    return {"status": "ready", "service": "network-service", "database": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")


_VALID_PORT_STATUSES = {"created", "attached", "detached", "failed"}


def _port_to_dict(p: Port) -> dict[str, Any]:
    return {
        "id": p.id,
        "device_id": p.device_id,
        "network_id": p.network_id,
        "status": p.status,
        "ip_address": p.ip_address,
        "owner_id": p.owner_id,
        "tenant_id": p.tenant_id,
    }


@app.get("/api/v2/ports")
async def list_ports(request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        q = select(Port)
        if not user.is_platform_admin(AUTH_SETTINGS):
            q = q.where(Port.tenant_id == user.tenant_id)
        items = db.execute(q).scalars().all()
    return {"items": [_port_to_dict(p) for p in items], "total": len(items)}


@app.post("/api/v2/ports", status_code=201)
async def create_port(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    port_id = str(uuid4())
    port = Port(
        id=port_id,
        device_id=payload.get("device_id"),
        network_id=payload.get("network_id"),
        status="created",
        ip_address=payload.get("ip_address"),
        owner_id=user.user_id,
        tenant_id=user.tenant_id,
    )
    with SessionLocal() as db:
        db.add(port)
        db.commit()
    response = _port_to_dict(port)
    emit_audit_event(
        service="network-service",
        action="port.created",
        resource_type="port",
        resource_id=port.id,
        tenant_id=port.tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )
    await _events.publish_event("created", port.id, response)
    return response


@app.get("/api/v2/ports/{port_id}")
async def get_port(port_id: str, request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        port = db.get(Port, port_id)
    if not port:
        raise HTTPException(status_code=404, detail="port not found")
    if port.tenant_id and port.tenant_id != user.tenant_id and not user.is_platform_admin(AUTH_SETTINGS):
        raise HTTPException(status_code=404, detail="port not found")
    return _port_to_dict(port)


@app.patch("/api/v2/ports/{port_id}")
async def update_port(port_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        port = db.get(Port, port_id)
        if not port:
            raise HTTPException(status_code=404, detail="port not found")
        if port.tenant_id and port.tenant_id != user.tenant_id and not user.is_platform_admin(AUTH_SETTINGS):
            raise HTTPException(status_code=404, detail="port not found")
        if "status" in payload and payload["status"]:
            if payload["status"] not in _VALID_PORT_STATUSES:
                raise HTTPException(status_code=400, detail=f"invalid status, must be one of {sorted(_VALID_PORT_STATUSES)}")
            port.status = payload["status"]
        if "ip_address" in payload:
            port.ip_address = payload["ip_address"]
        if "network_id" in payload:
            port.network_id = payload["network_id"]
        db.commit()
        db.refresh(port)
    response = _port_to_dict(port)
    emit_audit_event(
        service="network-service",
        action="port.updated",
        resource_type="port",
        resource_id=port.id,
        tenant_id=port.tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )
    await _events.publish_event("updated", port_id, response)
    return response


@app.delete("/api/v2/ports/{port_id}", status_code=204)
async def delete_port(port_id: str, request: Request) -> None:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        port = db.get(Port, port_id)
        if not port:
            raise HTTPException(status_code=404, detail="port not found")
        if port.tenant_id and port.tenant_id != user.tenant_id and not user.is_platform_admin(AUTH_SETTINGS):
            raise HTTPException(status_code=404, detail="port not found")
        deleted_payload = _port_to_dict(port)
        db.delete(port)
        db.commit()
    emit_audit_event(
        service="network-service",
        action="port.deleted",
        resource_type="port",
        resource_id=port_id,
        tenant_id=deleted_payload.get("tenant_id"),
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )
    await _events.publish_event("deleted", port_id, deleted_payload)
