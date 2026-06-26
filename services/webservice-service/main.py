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
import jwt as _pyjwt
from jwt import PyJWKClient as _PyJWKClient
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import generate_latest
from sqlalchemy import func, select

from webservice_service.core.config import (
    AUTH_DEV_BYPASS_ENABLED, AUTH_DEV_TOKEN, AUTH_ENABLED, AUTH_WRITE_ROLE,
    ENVIRONMENT, KAFKA_BOOTSTRAP_SERVERS, KAFKA_ENABLED, KAFKA_REQUIRED, KEYCLOAK_ISSUER,
)
from webservice_service.core.database import Base, engine, SessionLocal
from webservice_service.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL
import webservice_service.core.events as _events
from webservice_service.models.webservice import Webservice, _VALID_STATUSES as _VALID_WS_STATUSES

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("webservice-service")

app = FastAPI(title="Webservice Service", version="0.1.0")


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


_jwks_client: "_PyJWKClient | None" = None


def _get_jwks_client() -> "_PyJWKClient | None":
    global _jwks_client
    if _jwks_client is None and KEYCLOAK_ISSUER:
        jwks_url = KEYCLOAK_ISSUER.rstrip("/") + "/protocol/openid-connect/certs"
        _jwks_client = _PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    client = _get_jwks_client()
    if client:
        try:
            signing_key = client.get_signing_key_from_jwt(token)
            return _pyjwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                options={"verify_exp": True},
                issuer=KEYCLOAK_ISSUER or None,
            )
        except Exception:
            return None
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
        "webservice-service", request.method, request.url.path, str(response.status_code)
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        "webservice-service", request.method, request.url.path
    ).observe(elapsed)
    logger.info(json.dumps({
        "service": "webservice-service",
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
    return {"status": "healthy", "service": "webservice-service"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(select(func.count()).select_from(Webservice))
    return {"status": "ready", "service": "webservice-service", "database": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")


def _ws_to_dict(w: Webservice) -> dict[str, Any]:
    return {
        "id": w.id,
        "device_id": w.device_id,
        "port": w.port,
        "status": w.status,
        "hostname": w.hostname,
        "tls_enabled": w.tls_enabled if w.tls_enabled is not None else True,
    }


@app.get("/api/v2/webservices")
async def list_webservices() -> dict[str, Any]:
    with SessionLocal() as db:
        items = db.execute(select(Webservice)).scalars().all()
    return {"items": [_ws_to_dict(w) for w in items], "total": len(items)}


@app.post("/api/v2/webservices", status_code=201)
async def create_webservice(payload: dict[str, Any]) -> dict[str, Any]:
    status = payload.get("status", "enabled")
    if status not in _VALID_WS_STATUSES:
        raise HTTPException(status_code=400, detail=f"invalid status, must be one of {sorted(_VALID_WS_STATUSES)}")
    webservice_id = str(uuid4())
    webservice = Webservice(
        id=webservice_id,
        device_id=payload.get("device_id"),
        port=payload.get("port", 443),
        status=status,
        hostname=payload.get("hostname"),
        tls_enabled=payload.get("tls_enabled", True),
    )
    with SessionLocal() as db:
        db.add(webservice)
        db.commit()
    response = _ws_to_dict(webservice)
    await _events.publish_event("created", webservice.id, response)
    return response


@app.get("/api/v2/webservices/{webservice_id}")
async def get_webservice(webservice_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        webservice = db.get(Webservice, webservice_id)
    if not webservice:
        raise HTTPException(status_code=404, detail="webservice not found")
    return _ws_to_dict(webservice)


@app.patch("/api/v2/webservices/{webservice_id}")
async def update_webservice(webservice_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        webservice = db.get(Webservice, webservice_id)
        if not webservice:
            raise HTTPException(status_code=404, detail="webservice not found")
        if "device_id" in payload:
            webservice.device_id = payload.get("device_id")
        if "port" in payload and payload.get("port") is not None:
            webservice.port = int(payload["port"])
        if "status" in payload and payload.get("status"):
            if payload["status"] not in _VALID_WS_STATUSES:
                raise HTTPException(status_code=400, detail=f"invalid status, must be one of {sorted(_VALID_WS_STATUSES)}")
            webservice.status = payload["status"]
        if "hostname" in payload:
            webservice.hostname = payload["hostname"]
        if "tls_enabled" in payload:
            webservice.tls_enabled = bool(payload["tls_enabled"])
        db.commit()
        db.refresh(webservice)
    response = _ws_to_dict(webservice)
    await _events.publish_event("updated", webservice.id, response)
    return response


@app.delete("/api/v2/webservices/{webservice_id}", status_code=204)
async def delete_webservice(webservice_id: str) -> None:
    with SessionLocal() as db:
        webservice = db.get(Webservice, webservice_id)
        if not webservice:
            raise HTTPException(status_code=404, detail="webservice not found")
        deleted_payload = _ws_to_dict(webservice)
        db.delete(webservice)
        db.commit()
    await _events.publish_event("deleted", webservice_id, deleted_payload)
