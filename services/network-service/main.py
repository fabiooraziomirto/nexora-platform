import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import asyncio
import base64
import json
import logging
import time
from typing import Any
from uuid import uuid4

import aiokafka
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import generate_latest
from sqlalchemy import func, select

from network_service.core.config import (
    AUTH_DEV_BYPASS_ENABLED, AUTH_DEV_TOKEN, AUTH_ENABLED, AUTH_WRITE_ROLE,
    ENVIRONMENT, KAFKA_BOOTSTRAP_SERVERS, KAFKA_ENABLED, KAFKA_REQUIRED, KEYCLOAK_ISSUER,
)
from network_service.core.database import Base, engine, SessionLocal
from network_service.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL
import network_service.core.events as _events
from network_service.models.port import Port

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("network-service")

app = FastAPI(title="Network Service", version="0.1.0")


@app.on_event("startup")
async def startup() -> None:
    if AUTH_DEV_BYPASS_ENABLED:
        if ENVIRONMENT == "production":
            raise RuntimeError("AUTH_DEV_BYPASS_ENABLED=true is not allowed when ENVIRONMENT=production")
        logger.warning("AUTH DEV BYPASS ENABLED — NOT FOR PRODUCTION")
    Base.metadata.create_all(bind=engine)
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


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        data = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
        return json.loads(data)
    except Exception:
        return None


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not AUTH_ENABLED:
        return await call_next(request)
    if request.url.path in {"/health", "/ready", "/metrics"}:
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "missing bearer token"})
    token = auth.split(" ", 1)[1]
    if AUTH_DEV_BYPASS_ENABLED and token == AUTH_DEV_TOKEN:
        return await call_next(request)
    payload = _decode_jwt_payload(token)
    if not payload:
        return JSONResponse(status_code=401, content={"detail": "invalid token"})
    exp = payload.get("exp")
    if exp and float(exp) < time.time():
        return JSONResponse(status_code=401, content={"detail": "token expired"})
    if KEYCLOAK_ISSUER and payload.get("iss") != KEYCLOAK_ISSUER:
        return JSONResponse(status_code=401, content={"detail": "invalid issuer"})
    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        realm_access = payload.get("realm_access", {})
        roles = set(realm_access.get("roles", []))
        if AUTH_WRITE_ROLE and AUTH_WRITE_ROLE not in roles:
            return JSONResponse(status_code=403, content={"detail": "forbidden"})
    return await call_next(request)


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


@app.get("/api/v2/ports")
async def list_ports() -> dict[str, Any]:
    with SessionLocal() as db:
        items = db.execute(select(Port)).scalars().all()
        payload = [{"id": p.id, "device_id": p.device_id, "network_id": p.network_id, "status": p.status} for p in items]
    return {"items": payload, "total": len(payload)}


@app.post("/api/v2/ports", status_code=201)
async def create_port(payload: dict[str, Any]) -> dict[str, Any]:
    port_id = str(uuid4())
    port = Port(
        id=port_id,
        device_id=payload.get("device_id"),
        network_id=payload.get("network_id"),
        status="created",
    )
    with SessionLocal() as db:
        db.add(port)
        db.commit()
    response = {"id": port.id, "device_id": port.device_id, "network_id": port.network_id, "status": port.status}
    await _events.publish_event("created", port.id, response)
    return response


@app.get("/api/v2/ports/{port_id}")
async def get_port(port_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        port = db.get(Port, port_id)
    if not port:
        raise HTTPException(status_code=404, detail="port not found")
    return {"id": port.id, "device_id": port.device_id, "network_id": port.network_id, "status": port.status}


@app.delete("/api/v2/ports/{port_id}", status_code=204)
async def delete_port(port_id: str) -> None:
    with SessionLocal() as db:
        port = db.get(Port, port_id)
        if not port:
            raise HTTPException(status_code=404, detail="port not found")
        deleted_payload = {"id": port.id, "device_id": port.device_id, "network_id": port.network_id, "status": port.status}
        db.delete(port)
        db.commit()
    await _events.publish_event("deleted", port_id, deleted_payload)
