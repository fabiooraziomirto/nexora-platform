import os
from typing import Any
import base64
import json
import time
import asyncio
import logging
from uuid import uuid4
import aiokafka
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest
from sqlalchemy import Column, String, create_engine, func, select
from sqlalchemy.orm import declarative_base, sessionmaker

app = FastAPI(title="Network Service", version="0.1.0")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./network_service.db")
DB_CONNECT_TIMEOUT_SECONDS = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5"))
Base = declarative_base()
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": DB_CONNECT_TIMEOUT_SECONDS} if "mysql" in DATABASE_URL else {"timeout": DB_CONNECT_TIMEOUT_SECONDS},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
AUTH_DEV_TOKEN = os.getenv("AUTH_DEV_TOKEN", "dev-token")
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "")
AUTH_WRITE_ROLE = os.getenv("AUTH_WRITE_ROLE", "writer")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC_PREFIX = os.getenv("KAFKA_TOPIC_PREFIX", "stack4things")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() == "true"
KAFKA_REQUIRED = os.getenv("KAFKA_REQUIRED", "false").lower() == "true"
KAFKA_RETRY_ATTEMPTS = int(os.getenv("KAFKA_RETRY_ATTEMPTS", "3"))
KAFKA_RETRY_DELAY_SECONDS = float(os.getenv("KAFKA_RETRY_DELAY_SECONDS", "0.5"))
logger = logging.getLogger("network-service")
producer: aiokafka.AIOKafkaProducer | None = None
HTTP_REQUESTS_TOTAL = Counter("s4t_http_requests_total", "Total HTTP requests", ["service", "method", "path", "status"])
HTTP_REQUEST_DURATION_SECONDS = Histogram("s4t_http_request_duration_seconds", "HTTP request duration", ["service", "method", "path"])


class Port(Base):
    __tablename__ = "ports"

    id = Column(String(36), primary_key=True, index=True)
    device_id = Column(String(64), nullable=True, index=True)
    network_id = Column(String(64), nullable=True, index=True)
    status = Column(String(64), nullable=False, default="created")


@app.on_event("startup")
async def startup() -> None:
    Base.metadata.create_all(bind=engine)
    global producer
    if not KAFKA_ENABLED:
        logger.info("Kafka publisher disabled by configuration")
        return
    producer = aiokafka.AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    try:
        await producer.start()
    except Exception:
        logger.exception("Failed to connect Kafka producer")
        producer = None
        if KAFKA_REQUIRED:
            raise


@app.on_event("shutdown")
async def shutdown() -> None:
    global producer
    if producer:
        await producer.stop()
        producer = None


async def _publish_event(action: str, resource_id: str, payload: dict[str, Any]) -> None:
    if not producer:
        logger.warning("Kafka producer not available, skipping event", extra={"action": action, "resource_id": resource_id})
        return
    event_type = f"port.{action}"
    topic = f"{KAFKA_TOPIC_PREFIX}.{event_type}"
    event = {
        "event_type": event_type,
        "service": "network-service",
        "resource": "port",
        "action": action,
        "resource_id": resource_id,
        "payload": payload,
        "occurred_at": time.time(),
    }
    for attempt in range(1, KAFKA_RETRY_ATTEMPTS + 1):
        try:
            await producer.send_and_wait(topic, event, key=resource_id.encode("utf-8"))
            return
        except Exception:
            logger.exception("Kafka publish failed", extra={"attempt": attempt, "topic": topic, "resource_id": resource_id})
            if attempt < KAFKA_RETRY_ATTEMPTS:
                await asyncio.sleep(KAFKA_RETRY_DELAY_SECONDS * attempt)


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
    if token == AUTH_DEV_TOKEN:
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
    HTTP_REQUESTS_TOTAL.labels("network-service", request.method, request.url.path, str(response.status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels("network-service", request.method, request.url.path).observe(elapsed)
    logger.info(json.dumps({"service": "network-service", "trace_id": trace_id, "correlation_id": correlation_id, "method": request.method, "path": request.url.path, "status": response.status_code, "duration_s": round(elapsed, 6)}))
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
    await _publish_event("created", port.id, response)
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
    await _publish_event("deleted", port_id, deleted_payload)
