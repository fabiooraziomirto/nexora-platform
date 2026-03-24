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

app = FastAPI(title="Execution Service", version="0.1.0")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./execution_service.db")
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
logger = logging.getLogger("execution-service")
producer: aiokafka.AIOKafkaProducer | None = None
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "5"))
HTTP_REQUESTS_TOTAL = Counter(
    "s4t_http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "s4t_http_request_duration_seconds",
    "HTTP request duration",
    ["service", "method", "path"],
)


class Execution(Base):
    __tablename__ = "executions"

    id = Column(String(36), primary_key=True, index=True)
    device_id = Column(String(64), nullable=True, index=True)
    command = Column(String(255), nullable=False, default="noop")
    status = Column(String(64), nullable=False, default="queued")


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
    event_type = f"execution.{action}"
    topic = f"{KAFKA_TOPIC_PREFIX}.{event_type}"
    event = {
        "event_type": event_type,
        "service": "execution-service",
        "resource": "execution",
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
    HTTP_REQUESTS_TOTAL.labels("execution-service", request.method, request.url.path, str(response.status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels("execution-service", request.method, request.url.path).observe(elapsed)
    logger.info(
        json.dumps(
            {
                "service": "execution-service",
                "trace_id": trace_id,
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_s": round(elapsed, 6),
            }
        )
    )
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "execution-service"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(select(func.count()).select_from(Execution))
    return {"status": "ready", "service": "execution-service", "database": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")


@app.get("/api/v2/executions")
async def list_executions() -> dict[str, Any]:
    with SessionLocal() as db:
        items = db.execute(select(Execution)).scalars().all()
        payload = [
            {"id": e.id, "device_id": e.device_id, "command": e.command, "status": e.status}
            for e in items
        ]
    return {"items": payload, "total": len(payload)}


@app.post("/api/v2/executions", status_code=201)
async def create_execution(payload: dict[str, Any]) -> dict[str, Any]:
    execution_id = str(uuid4())
    execution = Execution(
        id=execution_id,
        device_id=payload.get("device_id"),
        command=payload.get("command", "noop"),
        status="queued",
    )
    with SessionLocal() as db:
        db.add(execution)
        db.commit()
    response = {
        "id": execution.id,
        "device_id": execution.device_id,
        "command": execution.command,
        "status": execution.status,
    }
    await _publish_event("created", execution.id, response)
    return response


@app.get("/api/v2/executions/{execution_id}")
async def get_execution(execution_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="execution not found")
    return {
        "id": execution.id,
        "device_id": execution.device_id,
        "command": execution.command,
        "status": execution.status,
    }


@app.delete("/api/v2/executions/{execution_id}", status_code=204)
async def delete_execution(execution_id: str) -> None:
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="execution not found")
        deleted_payload = {
            "id": execution.id,
            "device_id": execution.device_id,
            "command": execution.command,
            "status": execution.status,
        }
        db.delete(execution)
        db.commit()
    await _publish_event("deleted", execution_id, deleted_payload)
