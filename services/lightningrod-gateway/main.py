import os
import json
import time
import asyncio
import logging
from typing import Any
from uuid import uuid4

import aiokafka
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest

app = FastAPI(title="Lightningrod Gateway", version="0.1.0")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC_PREFIX = os.getenv("KAFKA_TOPIC_PREFIX", "stack4things")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() == "true"
KAFKA_REQUIRED = os.getenv("KAFKA_REQUIRED", "false").lower() == "true"
MAX_DELIVERY_ATTEMPTS = int(os.getenv("MAX_DELIVERY_ATTEMPTS", "3"))
DELIVERY_BACKOFF_SECONDS = float(os.getenv("DELIVERY_BACKOFF_SECONDS", "0.5"))

logger = logging.getLogger("lightningrod-gateway")

producer: aiokafka.AIOKafkaProducer | None = None
consumer: aiokafka.AIOKafkaConsumer | None = None
_consumer_task: asyncio.Task | None = None

agent_sessions: dict[str, dict[str, Any]] = {}
dispatch_cache: dict[str, dict[str, Any]] = {}
delivery_attempts: dict[str, int] = {}
delivery_last_error: dict[str, str] = {}

DISPATCH_EVENTS_TOTAL = Counter(
    "s4t_lr_dispatch_events_total",
    "Total dispatch events consumed from Kafka",
    ["service"],
)
DELIVERY_ATTEMPTS_TOTAL = Counter(
    "s4t_lr_delivery_attempts_total",
    "Total delivery attempts to edge agents",
    ["service", "device_id"],
)
DELIVERY_FAILURES_TOTAL = Counter(
    "s4t_lr_delivery_failures_total",
    "Total delivery failures after retries exhausted",
    ["service", "device_id"],
)
AGENT_SESSIONS_GAUGE = Gauge(
    "s4t_lr_agent_sessions",
    "Number of currently registered agent sessions",
    ["service"],
)
PENDING_DISPATCH_GAUGE = Gauge(
    "s4t_lr_pending_dispatches",
    "Number of pending dispatches in cache",
    ["service"],
)
PER_DEVICE_PENDING_GAUGE = Gauge(
    "s4t_lr_per_device_pending_dispatches",
    "Pending dispatches per device",
    ["service", "device_id"],
)
REQUEST_DURATION = Histogram(
    "s4t_lr_request_duration_seconds",
    "HTTP request duration",
    ["service", "method", "path"],
)


async def _consume_dispatched() -> None:
    global consumer
    topic = f"{KAFKA_TOPIC_PREFIX}.execution.dispatched"
    consumer = aiokafka.AIOKafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="lightningrod-gateway",
        auto_offset_reset="latest",
    )
    try:
        await consumer.start()
        logger.info("Kafka consumer started on topic %s", topic)
    except Exception:
        logger.exception("Failed to start Kafka consumer")
        consumer = None
        if KAFKA_REQUIRED:
            raise
        return

    try:
        async for msg in consumer:
            event = msg.value
            execution_id = event.get("resource_id") or event.get("execution_id") or str(uuid4())
            device_id = event.get("payload", {}).get("device_id")

            dispatch_cache[execution_id] = {
                "execution_id": execution_id,
                "device_id": device_id,
                "event": event,
                "received_at": time.time(),
            }
            delivery_attempts[execution_id] = 0
            delivery_last_error[execution_id] = ""

            DISPATCH_EVENTS_TOTAL.labels("lightningrod-gateway").inc()
            PENDING_DISPATCH_GAUGE.labels("lightningrod-gateway").set(len(dispatch_cache))
            if device_id:
                device_pending = sum(
                    1 for d in dispatch_cache.values() if d.get("device_id") == device_id
                )
                PER_DEVICE_PENDING_GAUGE.labels("lightningrod-gateway", device_id).set(device_pending)

            logger.info("Dispatch event cached: execution_id=%s device_id=%s", execution_id, device_id)
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Kafka consumer loop error")
    finally:
        if consumer:
            await consumer.stop()
            consumer = None


async def _publish_event(action: str, resource_id: str, payload: dict[str, Any]) -> None:
    if not producer:
        logger.warning("Kafka producer not available, skipping event", extra={"action": action, "resource_id": resource_id})
        return
    event_type = f"execution.{action}"
    topic = f"{KAFKA_TOPIC_PREFIX}.{event_type}"
    event = {
        "event_type": event_type,
        "service": "lightningrod-gateway",
        "resource": "execution",
        "action": action,
        "resource_id": resource_id,
        "payload": payload,
        "occurred_at": time.time(),
    }
    try:
        await producer.send_and_wait(topic, event, key=resource_id.encode("utf-8"))
    except Exception:
        logger.exception("Failed to publish %s event for %s", action, resource_id)


@app.on_event("startup")
async def startup() -> None:
    global producer, _consumer_task
    if not KAFKA_ENABLED:
        logger.info("Kafka disabled by configuration")
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

    _consumer_task = asyncio.create_task(_consume_dispatched())


@app.on_event("shutdown")
async def shutdown() -> None:
    global producer, _consumer_task
    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
        _consumer_task = None
    if producer:
        await producer.stop()
        producer = None


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or uuid4().hex
    correlation_id = request.headers.get("x-correlation-id", trace_id)
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    response.headers["x-trace-id"] = trace_id
    response.headers["x-correlation-id"] = correlation_id
    REQUEST_DURATION.labels("lightningrod-gateway", request.method, request.url.path).observe(elapsed)
    logger.info(
        json.dumps(
            {
                "service": "lightningrod-gateway",
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
    return {"status": "healthy", "service": "lightningrod-gateway"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    kafka_ok = producer is not None or not KAFKA_ENABLED
    if not kafka_ok:
        raise HTTPException(status_code=503, detail="Kafka producer not available")
    return {
        "status": "ready",
        "service": "lightningrod-gateway",
        "kafka": "ok" if producer else "disabled",
        "sessions": len(agent_sessions),
    }


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")


@app.post("/api/v2/agents/sessions/register", status_code=201)
async def register_agent_session(payload: dict[str, Any]) -> dict[str, Any]:
    device_id = payload.get("device_id")
    if not device_id:
        raise HTTPException(status_code=422, detail="device_id is required")

    now = time.time()
    session = {
        "device_id": device_id,
        "registered_at": now,
        "last_seen": now,
        "metadata": {k: v for k, v in payload.items() if k != "device_id"},
    }
    agent_sessions[device_id] = session
    AGENT_SESSIONS_GAUGE.labels("lightningrod-gateway").set(len(agent_sessions))
    logger.info("Agent session registered: device_id=%s", device_id)
    return session


@app.post("/api/v2/agents/sessions/{device_id}/heartbeat")
async def heartbeat(device_id: str) -> dict[str, Any]:
    session = agent_sessions.get(device_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    session["last_seen"] = time.time()
    return {"device_id": device_id, "last_seen": session["last_seen"]}


@app.get("/api/v2/agents/sessions/{device_id}")
async def get_session(device_id: str) -> dict[str, Any]:
    session = agent_sessions.get(device_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@app.post("/api/v2/deliver/{execution_id}")
async def deliver(execution_id: str) -> dict[str, Any]:
    cached = dispatch_cache.get(execution_id)
    if not cached:
        raise HTTPException(status_code=404, detail="dispatch not found in cache")

    device_id = cached.get("device_id", "unknown")
    session = agent_sessions.get(device_id) if device_id != "unknown" else None

    attempts = delivery_attempts.get(execution_id, 0)

    for attempt in range(attempts + 1, MAX_DELIVERY_ATTEMPTS + 1):
        delivery_attempts[execution_id] = attempt
        DELIVERY_ATTEMPTS_TOTAL.labels("lightningrod-gateway", device_id).inc()

        if session:
            dispatch_cache.pop(execution_id, None)
            delivery_attempts.pop(execution_id, None)
            delivery_last_error.pop(execution_id, None)
            PENDING_DISPATCH_GAUGE.labels("lightningrod-gateway").set(len(dispatch_cache))
            if device_id != "unknown":
                device_pending = sum(
                    1 for d in dispatch_cache.values() if d.get("device_id") == device_id
                )
                PER_DEVICE_PENDING_GAUGE.labels("lightningrod-gateway", device_id).set(device_pending)
            return {
                "execution_id": execution_id,
                "device_id": device_id,
                "status": "delivered",
                "attempts": attempt,
            }

        error_msg = f"no active session for device {device_id}"
        delivery_last_error[execution_id] = error_msg
        logger.warning(
            "Delivery attempt %d/%d failed for execution %s: %s",
            attempt, MAX_DELIVERY_ATTEMPTS, execution_id, error_msg,
        )

        if attempt < MAX_DELIVERY_ATTEMPTS:
            await asyncio.sleep(DELIVERY_BACKOFF_SECONDS * attempt)

    DELIVERY_FAILURES_TOTAL.labels("lightningrod-gateway", device_id).inc()

    await _publish_event("delivery_failed", execution_id, {
        "execution_id": execution_id,
        "device_id": device_id,
        "attempts": MAX_DELIVERY_ATTEMPTS,
        "last_error": delivery_last_error.get(execution_id, ""),
    })

    dispatch_cache.pop(execution_id, None)
    delivery_attempts.pop(execution_id, None)
    PENDING_DISPATCH_GAUGE.labels("lightningrod-gateway").set(len(dispatch_cache))
    if device_id != "unknown":
        device_pending = sum(
            1 for d in dispatch_cache.values() if d.get("device_id") == device_id
        )
        PER_DEVICE_PENDING_GAUGE.labels("lightningrod-gateway", device_id).set(device_pending)

    raise HTTPException(
        status_code=502,
        detail={
            "execution_id": execution_id,
            "device_id": device_id,
            "status": "delivery_failed",
            "attempts": MAX_DELIVERY_ATTEMPTS,
            "last_error": delivery_last_error.get(execution_id, ""),
        },
    )
