import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

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
from prometheus_client import generate_latest

from nexora_edge.core.config import (
    ENVIRONMENT,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC_PREFIX,
    KAFKA_ENABLED,
    KAFKA_REQUIRED,
    MAX_DELIVERY_ATTEMPTS,
    DELIVERY_BACKOFF_SECONDS,
    REDIS_URL,
    REDIS_ENABLED,
    REDIS_REQUIRED,
    SESSION_TTL_SECONDS,
    DISPATCH_TTL_SECONDS,
)
from nexora_edge.core.tracing import setup_tracing, extract_trace_context, tracer as _tracer
try:
    from opentelemetry import trace as _otel_trace
except ImportError:
    from nexora_edge.core.tracing import _NoopTrace

    _otel_trace = _NoopTrace()
from nexora_edge.core.metrics import (
    DISPATCH_EVENTS_TOTAL,
    DELIVERY_ATTEMPTS_TOTAL,
    DELIVERY_FAILURES_TOTAL,
    AGENT_SESSIONS_GAUGE,
    PENDING_DISPATCH_GAUGE,
    PER_DEVICE_PENDING_GAUGE,
    REQUEST_DURATION,
    DISPATCH_LATENCY,
    BROKER_COMMIT_LAG,
    KAFKA_INGESTION_LATENCY,
    QUEUE_WAIT,
    KAFKA_CONSUMER_LAG,
)

app = FastAPI(title="Lightningrod Gateway", version="0.1.0")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("nexora-edge")

producer: aiokafka.AIOKafkaProducer | None = None
consumer: aiokafka.AIOKafkaConsumer | None = None
_consumer_task: asyncio.Task | None = None
_lag_poller_task: asyncio.Task | None = None
redis_client: aioredis.Redis | None = None

# Local in-memory fallback — used only when Redis is disabled or unreachable.
# With fallback active the gateway is NOT horizontally scalable (single-instance only).
_local_sessions: dict[str, dict[str, Any]] = {}
_local_dispatches: dict[str, dict[str, Any]] = {}


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
# Kafka consumer lag poller
# ---------------------------------------------------------------------------

async def _poll_consumer_lag(interval_seconds: float = 15.0) -> None:
    """Periodically observe the consumer lag for each assigned partition."""
    while True:
        await asyncio.sleep(interval_seconds)
        if consumer is None:
            continue
        try:
            partitions = consumer.assignment()
            if not partitions:
                continue
            end_offsets = await consumer.end_offsets(list(partitions))
            for tp, end_offset in end_offsets.items():
                try:
                    position = await consumer.position(tp)
                    lag = max(0, end_offset - position)
                    KAFKA_CONSUMER_LAG.labels(
                        service="nexora-edge",
                        topic=tp.topic,
                        partition=str(tp.partition),
                    ).set(lag)
                except Exception:
                    pass
        except Exception:
            logger.debug("lag poller: skipped (consumer not ready)")


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
        group_id="nexora-edge",
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
                KAFKA_INGESTION_LATENCY.labels("nexora-edge").observe(kafka_ingestion_s)

                if kafka_broker_ts is not None:
                    broker_commit_lag_s = kafka_broker_ts - float(kafka_dispatched_at)
                    BROKER_COMMIT_LAG.labels("nexora-edge").observe(broker_commit_lag_s)

                logger.info(json.dumps({
                    "event": "dispatch_kafka_ingested",
                    "service": "nexora-edge",
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

            DISPATCH_EVENTS_TOTAL.labels("nexora-edge").inc()
            PENDING_DISPATCH_GAUGE.labels("nexora-edge").set(await _dispatch_count())
            if device_id:
                PER_DEVICE_PENDING_GAUGE.labels("nexora-edge", device_id).set(
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
        "service": "nexora-edge",
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
    setup_tracing()

    if ENVIRONMENT == "production" and (not REDIS_ENABLED or not REDIS_REQUIRED):
        raise RuntimeError(
            "nexora-edge requires REDIS_ENABLED=true and REDIS_REQUIRED=true "
            "when ENVIRONMENT=production"
        )

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
    _lag_poller_task = asyncio.create_task(_poll_consumer_lag())


@app.on_event("shutdown")
async def shutdown() -> None:
    global producer, _consumer_task, _lag_poller_task, redis_client
    for task in (_consumer_task, _lag_poller_task):
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    _consumer_task = None
    _lag_poller_task = None
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
    REQUEST_DURATION.labels("nexora-edge", request.method, request.url.path).observe(elapsed)
    logger.info(
        json.dumps(
            {
                "service": "nexora-edge",
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
    return {"status": "healthy", "service": "nexora-edge"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    kafka_ok = producer is not None or not KAFKA_ENABLED
    if not kafka_ok:
        raise HTTPException(status_code=503, detail="Kafka producer not available")
    sessions = await _session_count()
    redis_status = "ok" if redis_client is not None else ("disabled" if not REDIS_ENABLED else "degraded")
    return {
        "status": "ready",
        "service": "nexora-edge",
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
    AGENT_SESSIONS_GAUGE.labels("nexora-edge").set(await _session_count())
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

    # Extract distributed trace context propagated from execution-service via Kafka envelope.
    # The "event" sub-dict holds the original Kafka message (which includes traceparent if set).
    _parent_ctx = extract_trace_context(cached.get("event", {}))

    for attempt in range(attempts + 1, MAX_DELIVERY_ATTEMPTS + 1):
        cached["delivery_attempts"] = attempt
        await _dispatch_set(execution_id, cached)
        DELIVERY_ATTEMPTS_TOTAL.labels("nexora-edge", device_id).inc()

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
                QUEUE_WAIT.labels("nexora-edge").observe(queue_wait_s)

            if kafka_dispatched_at_val is not None:
                dispatch_latency_s = delivered_at - float(kafka_dispatched_at_val)
                DISPATCH_LATENCY.labels("nexora-edge").observe(dispatch_latency_s)

                if gateway_received_at_val is not None:
                    kafka_ingestion_s_val = float(gateway_received_at_val) - float(kafka_dispatched_at_val)

                if kafka_broker_ts_val is not None:
                    kafka_broker_lag_s_val = float(kafka_broker_ts_val) - float(kafka_dispatched_at_val)

            _trace_id = ""
            with _tracer.start_as_current_span(
                "gateway.deliver",
                context=_parent_ctx,
                attributes={
                    "execution_id": execution_id,
                    "device_id": device_id,
                    "attempt": attempt,
                    "queue_wait_seconds": queue_wait_s or 0.0,
                    "dispatch_latency_seconds": dispatch_latency_s or 0.0,
                },
            ):
                _trace_id = format(
                    _otel_trace.get_current_span().get_span_context().trace_id, "032x"
                )

            logger.info(json.dumps({
                "event": "dispatch_delivered",
                "service": "nexora-edge",
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
                "trace_id": _trace_id,
            }))

            await _dispatch_delete(execution_id)
            PENDING_DISPATCH_GAUGE.labels("nexora-edge").set(await _dispatch_count())
            if device_id != "unknown":
                PER_DEVICE_PENDING_GAUGE.labels("nexora-edge", device_id).set(
                    await _dispatch_count_for_device(device_id)
                )
            # Full timing breakdown + original Kafka event returned to the caller.
            # Agents use "payload" to get plugin details for function.install/invoke.
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
                "payload": cached.get("event", {}).get("payload", {}),
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
    DELIVERY_FAILURES_TOTAL.labels("nexora-edge", device_id).inc()

    await _publish_event("delivery_failed", execution_id, {
        "execution_id": execution_id,
        "device_id": device_id,
        "attempts": MAX_DELIVERY_ATTEMPTS,
        "last_error": last_error,
    })

    await _dispatch_delete(execution_id)
    PENDING_DISPATCH_GAUGE.labels("nexora-edge").set(await _dispatch_count())
    if device_id != "unknown":
        PER_DEVICE_PENDING_GAUGE.labels("nexora-edge", device_id).set(
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
