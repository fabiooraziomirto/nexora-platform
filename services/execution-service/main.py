import os
from typing import Any
import base64
import json
import time
import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4
import aiokafka
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import PlainTextResponse
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from sqlalchemy import Column, String, Integer, Text, DateTime, create_engine, func, select, and_
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
AGENT_CALLBACK_SECRET = os.getenv("AGENT_CALLBACK_SECRET", "")
CALLBACK_REPLAY_TTL_SECONDS = int(os.getenv("CALLBACK_REPLAY_TTL_SECONDS", "900"))
CALLBACK_REPLAY_REQUIRED = os.getenv("CALLBACK_REPLAY_REQUIRED", "false").lower() == "true"
MAX_EXECUTIONS_PER_DEVICE = int(os.getenv("MAX_EXECUTIONS_PER_DEVICE", "32"))
EXECUTION_DISPATCHED_TIMEOUT_SECONDS = int(os.getenv("EXECUTION_DISPATCHED_TIMEOUT_SECONDS", "300"))
EXECUTION_RUNNING_TIMEOUT_SECONDS = int(os.getenv("EXECUTION_RUNNING_TIMEOUT_SECONDS", "3600"))
EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS = int(os.getenv("EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS", "5"))
TERMINAL_STATUSES = frozenset({"succeeded", "failed", "timeout", "cancelled"})
VALID_STATUSES = frozenset({"queued", "dispatched", "running", "succeeded", "failed", "timeout", "cancelled"})
ACTIVE_STATUSES = frozenset({"queued", "dispatched", "running"})
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
    correlation_id = Column(String(64), nullable=True)
    idempotency_key = Column(String(128), nullable=True, unique=True, index=True)
    exit_code = Column(Integer, nullable=True)
    result_stdout = Column(Text, nullable=True)
    result_stderr = Column(Text, nullable=True)
    tenant_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, nullable=True)
    dispatched_at = Column(DateTime, nullable=True)
    running_at = Column(DateTime, nullable=True)


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"dispatched", "cancelled"},
    "dispatched": {"running", "failed", "timeout", "cancelled"},
    "running": {"succeeded", "failed", "timeout", "cancelled"},
}

_NEW_COLUMNS: list[tuple[str, str]] = [
    ("correlation_id", "VARCHAR(64)"),
    ("idempotency_key", "VARCHAR(128)"),
    ("exit_code", "INTEGER"),
    ("result_stdout", "TEXT"),
    ("result_stderr", "TEXT"),
    ("tenant_id", "VARCHAR(64)"),
    ("created_at", "TIMESTAMP"),
    ("dispatched_at", "TIMESTAMP"),
    ("running_at", "TIMESTAMP"),
]

ACTIVE_EXECUTIONS_GAUGE = Gauge(
    "s4t_active_executions",
    "Number of active (non-terminal) executions",
    ["service"],
)


def _ensure_execution_columns() -> None:
    from sqlalchemy import inspect as sa_inspect, text
    inspector = sa_inspect(engine)
    existing = {col["name"] for col in inspector.get_columns("executions")}
    with engine.begin() as conn:
        for col_name, col_type in _NEW_COLUMNS:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE executions ADD COLUMN {col_name} {col_type}"))
                logger.info("Added column %s to executions table", col_name)


def _transition_allowed(from_status: str, to_status: str) -> bool:
    return to_status in _ALLOWED_TRANSITIONS.get(from_status, set())


def _execution_to_dict(e: Execution) -> dict[str, Any]:
    return {
        "id": e.id,
        "device_id": e.device_id,
        "command": e.command,
        "status": e.status,
        "correlation_id": e.correlation_id,
        "idempotency_key": e.idempotency_key,
        "exit_code": e.exit_code,
        "result_stdout": e.result_stdout,
        "result_stderr": e.result_stderr,
        "tenant_id": e.tenant_id,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "dispatched_at": e.dispatched_at.isoformat() if e.dispatched_at else None,
        "running_at": e.running_at.isoformat() if e.running_at else None,
    }


_CALLBACK_ALLOWED_FIELDS = frozenset({"status", "exit_code", "stdout", "stderr", "callback_key"})


def _validate_callback_payload(payload: dict[str, Any]) -> str | None:
    unknown = set(payload.keys()) - _CALLBACK_ALLOWED_FIELDS
    if unknown:
        return f"unknown fields: {', '.join(sorted(unknown))}"
    status = payload.get("status")
    if status is not None and status not in VALID_STATUSES:
        return f"invalid status: {status}"
    return None


def _check_and_store_callback_key(db, execution: Execution, key: str | None) -> str | None:
    if not CALLBACK_REPLAY_REQUIRED:
        return None
    if not key:
        return "callback_key is required"
    return None


def _count_active_for_device(db, device_id: str) -> int:
    return db.execute(
        select(func.count()).select_from(Execution).where(
            and_(Execution.device_id == device_id, Execution.status.in_(ACTIVE_STATUSES))
        )
    ).scalar() or 0


def _audit_log(action: str, execution_id: str, detail: str = "") -> None:
    logger.info(
        json.dumps({
            "audit": True,
            "service": "execution-service",
            "action": action,
            "execution_id": execution_id,
            "detail": detail,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    )


def _make_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _timeout_loop() -> None:
    while True:
        await asyncio.sleep(EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS)
        try:
            now = datetime.now(timezone.utc)
            with SessionLocal() as db:
                candidates = db.execute(
                    select(Execution).where(Execution.status.in_({"dispatched", "running"}))
                ).scalars().all()
                for ex in candidates:
                    elapsed = None
                    if ex.status == "dispatched" and ex.dispatched_at:
                        elapsed = (now - _make_aware(ex.dispatched_at)).total_seconds()
                        threshold = EXECUTION_DISPATCHED_TIMEOUT_SECONDS
                    elif ex.status == "running" and ex.running_at:
                        elapsed = (now - _make_aware(ex.running_at)).total_seconds()
                        threshold = EXECUTION_RUNNING_TIMEOUT_SECONDS
                    if elapsed is not None and elapsed > threshold:
                        ex.status = "timeout"
                        _audit_log("timeout", ex.id, f"elapsed={elapsed:.1f}s threshold={threshold}s")
                db.commit()
        except Exception:
            logger.exception("Timeout check iteration failed")


@app.on_event("startup")
async def startup() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_execution_columns()
    asyncio.create_task(_timeout_loop())
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
        payload = [_execution_to_dict(e) for e in items]
    return {"items": payload, "total": len(payload)}


@app.post("/api/v2/executions", status_code=201)
async def create_execution(
    payload: dict[str, Any],
    request: Request,
    x_tenant_id: str | None = Header(None),
) -> dict[str, Any]:
    idempotency_key = payload.get("idempotency_key")
    with SessionLocal() as db:
        if idempotency_key:
            existing = db.execute(
                select(Execution).where(Execution.idempotency_key == idempotency_key)
            ).scalar_one_or_none()
            if existing:
                return _execution_to_dict(existing)

        device_id = payload.get("device_id")
        if device_id:
            active_count = _count_active_for_device(db, device_id)
            if active_count >= MAX_EXECUTIONS_PER_DEVICE:
                raise HTTPException(
                    status_code=429,
                    detail=f"device {device_id} has {active_count} active executions (limit {MAX_EXECUTIONS_PER_DEVICE})",
                )

        execution_id = str(uuid4())
        now = datetime.now(timezone.utc)
        execution = Execution(
            id=execution_id,
            device_id=device_id,
            command=payload.get("command", "noop"),
            status="queued",
            correlation_id=str(uuid4()),
            idempotency_key=idempotency_key,
            tenant_id=x_tenant_id,
            created_at=now,
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        response = _execution_to_dict(execution)

    _audit_log("created", execution.id)
    await _publish_event("created", execution.id, response)
    return response


@app.get("/api/v2/executions/{execution_id}")
async def get_execution(execution_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="execution not found")
    return _execution_to_dict(execution)


@app.delete("/api/v2/executions/{execution_id}", status_code=204)
async def delete_execution(execution_id: str) -> None:
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="execution not found")
        deleted_payload = _execution_to_dict(execution)
        db.delete(execution)
        db.commit()
    _audit_log("deleted", execution_id)
    await _publish_event("deleted", execution_id, deleted_payload)


@app.post("/api/v2/executions/{execution_id}/dispatch")
async def dispatch_execution(execution_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="execution not found")
        if not _transition_allowed(execution.status, "dispatched"):
            raise HTTPException(
                status_code=409,
                detail=f"cannot transition from {execution.status} to dispatched",
            )
        execution.status = "dispatched"
        execution.dispatched_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(execution)
        response = _execution_to_dict(execution)
    envelope = {
        "execution_id": execution.id,
        "device_id": execution.device_id,
        "command": execution.command,
        "correlation_id": execution.correlation_id,
    }
    _audit_log("dispatched", execution_id)
    await _publish_event("dispatched", execution.id, envelope)
    return response


@app.post("/api/v2/executions/{execution_id}/callback")
async def callback_execution(execution_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    error = _validate_callback_payload(payload)
    if error:
        raise HTTPException(status_code=422, detail=error)

    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=422, detail="status is required")

    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="execution not found")

        key_err = _check_and_store_callback_key(db, execution, payload.get("callback_key"))
        if key_err:
            raise HTTPException(status_code=422, detail=key_err)

        if not _transition_allowed(execution.status, new_status):
            raise HTTPException(
                status_code=409,
                detail=f"cannot transition from {execution.status} to {new_status}",
            )

        execution.status = new_status
        if new_status == "running":
            execution.running_at = datetime.now(timezone.utc)
        if "exit_code" in payload:
            execution.exit_code = payload["exit_code"]
        if "stdout" in payload:
            execution.result_stdout = payload["stdout"]
        if "stderr" in payload:
            execution.result_stderr = payload["stderr"]

        db.commit()
        db.refresh(execution)
        response = _execution_to_dict(execution)

    _audit_log("callback", execution_id, f"new_status={new_status}")
    await _publish_event("callback", execution.id, response)
    return response


@app.post("/api/v2/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="execution not found")
        if not _transition_allowed(execution.status, "cancelled"):
            raise HTTPException(
                status_code=409,
                detail=f"cannot transition from {execution.status} to cancelled",
            )
        execution.status = "cancelled"
        db.commit()
        db.refresh(execution)
        response = _execution_to_dict(execution)
    _audit_log("cancelled", execution_id)
    await _publish_event("cancelled", execution.id, response)
    return response
