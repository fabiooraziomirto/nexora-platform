import os
import json
import time
import asyncio
import logging
from typing import Any
from uuid import uuid4

import aiokafka
import redis.asyncio as aioredis
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

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").lower() == "true"
REDIS_REQUIRED = os.getenv("REDIS_REQUIRED", "false").lower() == "true"
# Heartbeat-based TTL: session expires if not refreshed within this window.
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "300"))
# Dispatch TTL matches EXECUTION_RUNNING_TIMEOUT_SECONDS in execution-service.
DISPATCH_TTL_SECONDS = int(os.getenv("DISPATCH_TTL_SECONDS", "3600"))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("lightningrod-gateway")

producer: aiokafka.AIOKafkaProducer | None = None
consumer: aiokafka.AIOKafkaConsumer | None = None
_consumer_task: asyncio.Task | None = None
redis_client: aioredis.Redis | None = None

# Local in-memory fallback — used only when Redis is disabled or unreachable.
# With fallback active the gateway is NOT horizontally scalable (single-instance only).
_local_sessions: dict[str, dict[str, Any]] = {}
_local_dispatches: dict[str, dict[str, Any]] = {}

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
# End-to-end dispatch latency: from kafka_dispatched_at in the event envelope
# to the moment the gateway successfully delivers to the agent via /deliver.
# Buckets tuned for IoT command dispatch (expected range: 10ms–10s).
DISPATCH_LATENCY = Histogram(
    "s4t_execution_dispatch_latency_seconds",
    "End-to-end dispatch latency from Kafka publish to agent delivery",
    ["service"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float("inf")),
)
# Phase 1a: time from Kafka publish (producer-side) to broker timestamp on the record.
# With default CreateTime this reflects producer serialisation time (~sub-ms).
# Enable LogAppendTime on the topic for true network+commit lag measurement:
#   kafka-configs.sh --bootstrap-server kafka:29092 --entity-type topics \
#     --entity-name stack4things.execution.dispatched --alter \
#     --add-config message.timestamp.type=LogAppendTime
# Negative values indicate clock skew between producer host and broker; they are
# recorded (not dropped) so operators can detect and quantify systematic skew.
BROKER_COMMIT_LAG = Histogram(
    "s4t_lr_kafka_broker_lag_seconds",
    "Lag between producer kafka_dispatched_at and Kafka broker record timestamp (msg.timestamp)",
    ["service"],
    buckets=(-0.1, -0.025, -0.005, -0.001, 0.0, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, float("inf")),
)
# Phase 1b: time from Kafka publish to gateway consumer receiving the message.
KAFKA_INGESTION_LATENCY = Histogram(
    "s4t_lr_kafka_ingestion_latency_seconds",
    "Kafka broker-to-consumer ingestion latency for dispatch events",
    ["service"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, float("inf")),
)
# Phase 2: time the dispatch event waits in the gateway cache before delivery.
QUEUE_WAIT = Histogram(
    "s4t_lr_dispatch_queue_wait_seconds",
    "Time a dispatch event waits in the gateway cache before agent delivery",
    ["service"],
    buckets=(0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float("inf")),
)


# ---------------------------------------------------------------------------
# Redis-backed store helpers
# Each helper falls back to the local dicts on any Redis error so the gateway
# degrades gracefully instead of crashing. A warning is emitted on each
# fallback so the condition is visible in logs/alerts.
# ---------------------------------------------------------------------------

def _rkey_session(device_id: str) -> str:
    return f"gateway:session:{device_id}"


def _rkey_dispatch(execution_id: str) -> str:
    return f"gateway:dispatch:{execution_id}"


async def _session_get(device_id: str) -> dict[str, Any] | None:
    if redis_client is not None:
        try:
            raw = await redis_client.get(_rkey_session(device_id))
            return json.loads(raw) if raw else None
        except Exception:
            logger.warning("Redis error in _session_get device=%s, falling back to local", device_id)
    return _local_sessions.get(device_id)


async def _session_set(device_id: str, session: dict[str, Any]) -> None:
    if redis_client is not None:
        try:
            await redis_client.setex(_rkey_session(device_id), SESSION_TTL_SECONDS, json.dumps(session))
            return
        except Exception:
            logger.warning("Redis error in _session_set device=%s, falling back to local", device_id)
    _local_sessions[device_id] = session


async def _session_count() -> int:
    if redis_client is not None:
        try:
            return len(await redis_client.keys("gateway:session:*"))
        except Exception:
            logger.warning("Redis error in _session_count, falling back to local")
    return len(_local_sessions)


async def _dispatch_get(execution_id: str) -> dict[str, Any] | None:
    if redis_client is not None:
        try:
            raw = await redis_client.get(_rkey_dispatch(execution_id))
            return json.loads(raw) if raw else None
        except Exception:
            logger.warning("Redis error in _dispatch_get exec=%s, falling back to local", execution_id)
    return _local_dispatches.get(execution_id)


async def _dispatch_set(execution_id: str, data: dict[str, Any]) -> None:
    if redis_client is not None:
        try:
            await redis_client.setex(_rkey_dispatch(execution_id), DISPATCH_TTL_SECONDS, json.dumps(data))
            return
        except Exception:
            logger.warning("Redis error in _dispatch_set exec=%s, falling back to local", execution_id)
    _local_dispatches[execution_id] = data


async def _dispatch_delete(execution_id: str) -> None:
    if redis_client is not None:
        try:
            await redis_client.delete(_rkey_dispatch(execution_id))
            return
        except Exception:
            logger.warning("Redis error in _dispatch_delete exec=%s, falling back to local", execution_id)
    _local_dispatches.pop(execution_id, None)


async def _dispatch_count() -> int:
    if redis_client is not None:
        try:
            return len(await redis_client.keys("gateway:dispatch:*"))
        except Exception:
            logger.warning("Redis error in _dispatch_count, falling back to local")
    return len(_local_dispatches)


async def _dispatch_count_for_device(device_id: str) -> int:
    # O(N dispatches) — acceptable for research/emulator scale.
    # For production at scale, maintain a per-device set in Redis instead.
    if redis_client is not None:
        try:
            keys = await redis_client.keys("gateway:dispatch:*")
            count = 0
            for key in keys:
                raw = await redis_client.get(key)
                if raw:
                    data = json.loads(raw)
                    if data.get("device_id") == device_id:
                        count += 1
            return count
        except Exception:
            logger.warning("Redis error in _dispatch_count_for_device device=%s, falling back to local", device_id)
    return sum(1 for d in _local_dispatches.values() if d.get("device_id") == device_id)


# ---------------------------------------------------------------------------
# Kafka consumer
# ---------------------------------------------------------------------------

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
            gateway_received_at = time.time()
            event = msg.value
            execution_id = event.get("resource_id") or event.get("execution_id") or str(uuid4())
            device_id = event.get("payload", {}).get("device_id")

            # msg.timestamp is epoch-milliseconds assigned by Kafka (CreateTime by default,
            # LogAppendTime if broker is configured with log.message.timestamp.type=LogAppendTime).
            kafka_broker_ts: float | None = (
                msg.timestamp / 1000.0 if msg.timestamp and msg.timestamp > 0 else None
            )

            # Phase 1b: Kafka publish → gateway consumer receive.
            # kafka_dispatched_at is injected by execution-service; fall back to
            # occurred_at for events from older service versions.
            kafka_dispatched_at: float | None = (
                event.get("payload", {}).get("kafka_dispatched_at")
                or event.get("occurred_at")
            )

            broker_commit_lag_s: float | None = None
            kafka_ingestion_s: float | None = None

            if kafka_dispatched_at is not None:
                kafka_ingestion_s = gateway_received_at - float(kafka_dispatched_at)
                KAFKA_INGESTION_LATENCY.labels("lightningrod-gateway").observe(kafka_ingestion_s)

                if kafka_broker_ts is not None:
                    broker_commit_lag_s = kafka_broker_ts - float(kafka_dispatched_at)
                    BROKER_COMMIT_LAG.labels("lightningrod-gateway").observe(broker_commit_lag_s)

                logger.info(json.dumps({
                    "event": "dispatch_kafka_ingested",
                    "service": "lightningrod-gateway",
                    "execution_id": execution_id,
                    "device_id": device_id,
                    "kafka_dispatched_at": kafka_dispatched_at,
                    "kafka_broker_timestamp": kafka_broker_ts,
                    "gateway_received_at": gateway_received_at,
                    "kafka_broker_lag_s": round(broker_commit_lag_s, 6) if broker_commit_lag_s is not None else None,
                    "kafka_ingestion_s": round(kafka_ingestion_s, 6),
                }))

            dispatch_data = {
                "execution_id": execution_id,
                "device_id": device_id,
                "event": event,
                "received_at": gateway_received_at,
                "kafka_broker_timestamp": kafka_broker_ts,
                "delivery_attempts": 0,
                "delivery_last_error": "",
            }
            await _dispatch_set(execution_id, dispatch_data)

            DISPATCH_EVENTS_TOTAL.labels("lightningrod-gateway").inc()
            PENDING_DISPATCH_GAUGE.labels("lightningrod-gateway").set(await _dispatch_count())
            if device_id:
                PER_DEVICE_PENDING_GAUGE.labels("lightningrod-gateway", device_id).set(
                    await _dispatch_count_for_device(device_id)
                )

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


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup() -> None:
    global producer, _consumer_task, redis_client

    if REDIS_ENABLED:
        try:
            redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
            await redis_client.ping()
            logger.info("Redis connected: %s", REDIS_URL)
        except Exception:
            logger.exception("Failed to connect to Redis")
            redis_client = None
            if REDIS_REQUIRED:
                raise
            logger.warning(
                "Redis unavailable — using in-memory fallback. "
                "Gateway is NOT horizontally scalable in this mode."
            )
    else:
        logger.info("Redis disabled by configuration — using in-memory store (single-instance only)")

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
    global producer, _consumer_task, redis_client
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
    if redis_client:
        await redis_client.aclose()
        redis_client = None


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "lightningrod-gateway"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    kafka_ok = producer is not None or not KAFKA_ENABLED
    if not kafka_ok:
        raise HTTPException(status_code=503, detail="Kafka producer not available")
    sessions = await _session_count()
    redis_status = "ok" if redis_client is not None else ("disabled" if not REDIS_ENABLED else "degraded")
    return {
        "status": "ready",
        "service": "lightningrod-gateway",
        "kafka": "ok" if producer else "disabled",
        "redis": redis_status,
        "sessions": sessions,
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
    await _session_set(device_id, session)
    AGENT_SESSIONS_GAUGE.labels("lightningrod-gateway").set(await _session_count())
    logger.info("Agent session registered: device_id=%s", device_id)
    return session


@app.post("/api/v2/agents/sessions/{device_id}/heartbeat")
async def heartbeat(device_id: str) -> dict[str, Any]:
    session = await _session_get(device_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    session["last_seen"] = time.time()
    # _session_set also resets the Redis TTL, keeping the session alive.
    await _session_set(device_id, session)
    return {"device_id": device_id, "last_seen": session["last_seen"]}


@app.get("/api/v2/agents/sessions/{device_id}")
async def get_session(device_id: str) -> dict[str, Any]:
    session = await _session_get(device_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@app.post("/api/v2/deliver/{execution_id}")
async def deliver(execution_id: str) -> dict[str, Any]:
    cached = await _dispatch_get(execution_id)
    if not cached:
        raise HTTPException(status_code=404, detail="dispatch not found in cache")

    device_id = cached.get("device_id", "unknown")
    session = await _session_get(device_id) if device_id != "unknown" else None
    attempts = cached.get("delivery_attempts", 0)

    for attempt in range(attempts + 1, MAX_DELIVERY_ATTEMPTS + 1):
        cached["delivery_attempts"] = attempt
        await _dispatch_set(execution_id, cached)
        DELIVERY_ATTEMPTS_TOTAL.labels("lightningrod-gateway", device_id).inc()

        if session:
            delivered_at = time.time()

            # Retrieve all timing anchors from the dispatch blob.
            gateway_received_at_val: float | None = cached.get("received_at")
            kafka_broker_ts_val: float | None = cached.get("kafka_broker_timestamp")
            kafka_dispatched_at_val: float | None = (
                cached.get("event", {}).get("payload", {}).get("kafka_dispatched_at")
                or cached.get("event", {}).get("occurred_at")
            )

            queue_wait_s: float | None = None
            dispatch_latency_s: float | None = None
            kafka_ingestion_s_val: float | None = None
            kafka_broker_lag_s_val: float | None = None

            if gateway_received_at_val is not None:
                queue_wait_s = delivered_at - float(gateway_received_at_val)
                QUEUE_WAIT.labels("lightningrod-gateway").observe(queue_wait_s)

            if kafka_dispatched_at_val is not None:
                dispatch_latency_s = delivered_at - float(kafka_dispatched_at_val)
                DISPATCH_LATENCY.labels("lightningrod-gateway").observe(dispatch_latency_s)

                if gateway_received_at_val is not None:
                    kafka_ingestion_s_val = float(gateway_received_at_val) - float(kafka_dispatched_at_val)

                if kafka_broker_ts_val is not None:
                    kafka_broker_lag_s_val = float(kafka_broker_ts_val) - float(kafka_dispatched_at_val)

            logger.info(json.dumps({
                "event": "dispatch_delivered",
                "service": "lightningrod-gateway",
                "execution_id": execution_id,
                "device_id": device_id,
                "kafka_dispatched_at": kafka_dispatched_at_val,
                "kafka_broker_timestamp": kafka_broker_ts_val,
                "gateway_received_at": gateway_received_at_val,
                "delivered_at": delivered_at,
                "kafka_broker_lag_s": round(kafka_broker_lag_s_val, 6) if kafka_broker_lag_s_val is not None else None,
                "kafka_ingestion_s": round(kafka_ingestion_s_val, 6) if kafka_ingestion_s_val is not None else None,
                "queue_wait_s": round(queue_wait_s, 6) if queue_wait_s is not None else None,
                "dispatch_latency_s": round(dispatch_latency_s, 6) if dispatch_latency_s is not None else None,
                "attempts": attempt,
            }))

            await _dispatch_delete(execution_id)
            PENDING_DISPATCH_GAUGE.labels("lightningrod-gateway").set(await _dispatch_count())
            if device_id != "unknown":
                PER_DEVICE_PENDING_GAUGE.labels("lightningrod-gateway", device_id).set(
                    await _dispatch_count_for_device(device_id)
                )
            # Full timing breakdown returned to the caller (benchmark board agent).
            # All epoch-float fields enable JSONL reconstruction without log parsing.
            return {
                "execution_id": execution_id,
                "device_id": device_id,
                "status": "delivered",
                "attempts": attempt,
                "kafka_dispatched_at": kafka_dispatched_at_val,
                "kafka_broker_timestamp": kafka_broker_ts_val,
                "gateway_received_at": gateway_received_at_val,
                "delivered_at": delivered_at,
                "kafka_broker_lag_seconds": kafka_broker_lag_s_val,
                "kafka_ingestion_seconds": kafka_ingestion_s_val,
                "queue_wait_seconds": queue_wait_s,
                "dispatch_latency_seconds": dispatch_latency_s,
            }

        error_msg = f"no active session for device {device_id}"
        cached["delivery_last_error"] = error_msg
        await _dispatch_set(execution_id, cached)
        logger.warning(
            "Delivery attempt %d/%d failed for execution %s: %s",
            attempt, MAX_DELIVERY_ATTEMPTS, execution_id, error_msg,
        )

        if attempt < MAX_DELIVERY_ATTEMPTS:
            await asyncio.sleep(DELIVERY_BACKOFF_SECONDS * attempt)

    last_error = cached.get("delivery_last_error", "")
    DELIVERY_FAILURES_TOTAL.labels("lightningrod-gateway", device_id).inc()

    await _publish_event("delivery_failed", execution_id, {
        "execution_id": execution_id,
        "device_id": device_id,
        "attempts": MAX_DELIVERY_ATTEMPTS,
        "last_error": last_error,
    })

    await _dispatch_delete(execution_id)
    PENDING_DISPATCH_GAUGE.labels("lightningrod-gateway").set(await _dispatch_count())
    if device_id != "unknown":
        PER_DEVICE_PENDING_GAUGE.labels("lightningrod-gateway", device_id).set(
            await _dispatch_count_for_device(device_id)
        )

    raise HTTPException(
        status_code=502,
        detail={
            "execution_id": execution_id,
            "device_id": device_id,
            "status": "delivery_failed",
            "attempts": MAX_DELIVERY_ATTEMPTS,
            "last_error": last_error,
        },
    )
