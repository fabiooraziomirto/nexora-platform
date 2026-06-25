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
from sqlalchemy import Column, Integer, String, create_engine, func, select
from sqlalchemy.orm import declarative_base, sessionmaker

app = FastAPI(title="Webservice Service", version="0.1.0")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./webservice_service.db")
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
AUTH_DEV_BYPASS_ENABLED = os.getenv("AUTH_DEV_BYPASS_ENABLED", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "")
AUTH_WRITE_ROLE = os.getenv("AUTH_WRITE_ROLE", "writer")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC_PREFIX = os.getenv("KAFKA_TOPIC_PREFIX", "stack4things")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() == "true"
KAFKA_REQUIRED = os.getenv("KAFKA_REQUIRED", "false").lower() == "true"
KAFKA_RETRY_ATTEMPTS = int(os.getenv("KAFKA_RETRY_ATTEMPTS", "3"))
KAFKA_RETRY_DELAY_SECONDS = float(os.getenv("KAFKA_RETRY_DELAY_SECONDS", "0.5"))
logger = logging.getLogger("webservice-service")
producer: aiokafka.AIOKafkaProducer | None = None
HTTP_REQUESTS_TOTAL = Counter("s4t_http_requests_total", "Total HTTP requests", ["service", "method", "path", "status"])
HTTP_REQUEST_DURATION_SECONDS = Histogram("s4t_http_request_duration_seconds", "HTTP request duration", ["service", "method", "path"])


class Webservice(Base):
    __tablename__ = "webservices"

    id = Column(String(36), primary_key=True, index=True)
    device_id = Column(String(64), nullable=True, index=True)
    port = Column(Integer, nullable=False, default=443)
    status = Column(String(64), nullable=False, default="enabled")


@app.on_event("startup")
async def startup() -> None:
    if AUTH_DEV_BYPASS_ENABLED:
        if ENVIRONMENT == "production":
            raise RuntimeError("AUTH_DEV_BYPASS_ENABLED=true is not allowed when ENVIRONMENT=production")
        logger.warning("AUTH DEV BYPASS ENABLED — NOT FOR PRODUCTION")
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
    event_type = f"webservice.{action}"
    topic = f"{KAFKA_TOPIC_PREFIX}.{event_type}"
    event = {
        "event_type": event_type,
        "service": "webservice-service",
        "resource": "webservice",
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
    HTTP_REQUESTS_TOTAL.labels("webservice-service", request.method, request.url.path, str(response.status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels("webservice-service", request.method, request.url.path).observe(elapsed)
    logger.info(json.dumps({"service": "webservice-service", "trace_id": trace_id, "correlation_id": correlation_id, "method": request.method, "path": request.url.path, "status": response.status_code, "duration_s": round(elapsed, 6)}))
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


@app.get("/api/v2/webservices")
async def list_webservices() -> dict[str, Any]:
    with SessionLocal() as db:
        items = db.execute(select(Webservice)).scalars().all()
        payload = [{"id": w.id, "device_id": w.device_id, "port": w.port, "status": w.status} for w in items]
    return {"items": payload, "total": len(payload)}


@app.post("/api/v2/webservices", status_code=201)
async def create_webservice(payload: dict[str, Any]) -> dict[str, Any]:
    webservice_id = str(uuid4())
    webservice = Webservice(
        id=webservice_id,
        device_id=payload.get("device_id"),
        port=payload.get("port", 443),
        status="enabled",
    )
    with SessionLocal() as db:
        db.add(webservice)
        db.commit()
    response = {"id": webservice.id, "device_id": webservice.device_id, "port": webservice.port, "status": webservice.status}
    await _publish_event("created", webservice.id, response)
    return response


@app.get("/api/v2/webservices/{webservice_id}")
async def get_webservice(webservice_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        webservice = db.get(Webservice, webservice_id)
    if not webservice:
        raise HTTPException(status_code=404, detail="webservice not found")
    return {"id": webservice.id, "device_id": webservice.device_id, "port": webservice.port, "status": webservice.status}


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
            webservice.status = payload["status"]
        db.commit()
        db.refresh(webservice)
    response = {"id": webservice.id, "device_id": webservice.device_id, "port": webservice.port, "status": webservice.status}
    await _publish_event("updated", webservice.id, response)
    return response


@app.delete("/api/v2/webservices/{webservice_id}", status_code=204)
async def delete_webservice(webservice_id: str) -> None:
    with SessionLocal() as db:
        webservice = db.get(Webservice, webservice_id)
        if not webservice:
            raise HTTPException(status_code=404, detail="webservice not found")
        deleted_payload = {"id": webservice.id, "device_id": webservice.device_id, "port": webservice.port, "status": webservice.status}
        db.delete(webservice)
        db.commit()
    await _publish_event("deleted", webservice_id, deleted_payload)
