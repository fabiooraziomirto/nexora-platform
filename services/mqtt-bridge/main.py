"""mqtt-bridge — Nexora MQTT protocol gateway.

Bridges MQTT devices into the Nexora platform:
  - Subscribes to {prefix}/devices/+/{telemetry,state,register}
  - Auto-registers unknown devices on first publish
  - Routes telemetry → device-service ingest
  - Routes state → device shadow reported
  - Consumes nxr.execution.dispatched → publishes commands to device MQTT topic

Topic convention (Nexora-native):
  nexora/devices/{device_id}/register    — device self-registration at boot
  nexora/devices/{device_id}/telemetry   — time-series metrics
  nexora/devices/{device_id}/state       — shadow reported state
  nexora/devices/{device_id}/commands    — commands pushed by the bridge (QoS 1)
"""
import asyncio
import logging
import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import secrets
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, Counter, Gauge

from mqtt_bridge.core import config
from mqtt_bridge.core.message_handler import handle_message
from mqtt_bridge.core.command_publisher import start_consumer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("mqtt-bridge")

MQTT_MESSAGES_TOTAL = Counter(
    "mqtt_bridge_messages_total", "Total MQTT messages received", ["action"]
)
MQTT_CONNECTED = Gauge("mqtt_bridge_connected", "1 if connected to broker, 0 otherwise")

_mqtt_client: Any = None
_kafka_producer: Any = None
_kafka_consumer: Any = None
_mqtt_task: asyncio.Task | None = None


async def _mqtt_publish(topic: str, payload: str) -> None:
    if _mqtt_client is None:
        logger.warning("MQTT not connected — cannot publish to %s", topic)
        return
    await _mqtt_client.publish(topic, payload, qos=1)


async def _run_mqtt_loop() -> None:
    """Connect to the MQTT broker and subscribe to device topics."""
    global _mqtt_client
    prefix = config.MQTT_TOPIC_PREFIX
    wildcard = f"{prefix}/devices/+/+"

    try:
        import aiomqtt

        tls_params = None
        if config.MQTT_TLS:
            import ssl
            tls_params = aiomqtt.TLSParameters(
                ca_certs=config.MQTT_CA_CERT,
                tls_version=ssl.PROTOCOL_TLS,
            )

        logger.info("Connecting to MQTT broker %s:%s", config.MQTT_HOST, config.MQTT_PORT)
        async with aiomqtt.Client(
            hostname=config.MQTT_HOST,
            port=config.MQTT_PORT,
            username=config.MQTT_USERNAME,
            password=config.MQTT_PASSWORD,
            tls_params=tls_params,
        ) as client:
            _mqtt_client = client
            MQTT_CONNECTED.set(1)
            await client.subscribe(wildcard, qos=1)
            logger.info("MQTT subscribed to %s", wildcard)

            async for message in client.messages:
                topic = str(message.topic)
                action = topic.split("/")[-1] if "/" in topic else "unknown"
                MQTT_MESSAGES_TOTAL.labels(action=action).inc()
                asyncio.create_task(
                    handle_message(topic, message.payload),
                    name=f"mqtt-msg-{topic}",
                )

    except ImportError:
        logger.warning(
            "aiomqtt not installed — MQTT loop disabled. "
            "Install 'aiomqtt' for real MQTT support."
        )
        MQTT_CONNECTED.set(0)
        return
    except Exception as exc:
        logger.error("MQTT connection error: %s", exc)
        MQTT_CONNECTED.set(0)
    finally:
        _mqtt_client = None
        MQTT_CONNECTED.set(0)


async def _connect_kafka():
    if not config.KAFKA_ENABLED:
        return None, None
    try:
        import aiokafka

        producer = aiokafka.AIOKafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        )
        await producer.start()

        topic = f"{config.KAFKA_TOPIC_PREFIX}.execution.dispatched"
        consumer = aiokafka.AIOKafkaConsumer(
            topic,
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
            group_id="mqtt-bridge",
            auto_offset_reset="latest",
        )
        await consumer.start()
        logger.info("Kafka connected topic=%s", topic)
        return producer, consumer
    except Exception as exc:
        logger.warning("Kafka unavailable: %s", exc)
        return None, None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _kafka_producer, _kafka_consumer, _mqtt_task

    _kafka_producer, _kafka_consumer = await _connect_kafka()
    await start_consumer(_kafka_consumer, _mqtt_publish)

    _mqtt_task = asyncio.create_task(_run_mqtt_loop(), name="mqtt-loop")

    logger.info(
        "mqtt-bridge ready broker=%s:%s kafka=%s",
        config.MQTT_HOST, config.MQTT_PORT,
        "enabled" if _kafka_producer else "disabled",
    )

    yield

    if _mqtt_task:
        _mqtt_task.cancel()
        try:
            await _mqtt_task
        except asyncio.CancelledError:
            pass
    if _kafka_consumer:
        await _kafka_consumer.stop()
    if _kafka_producer:
        await _kafka_producer.stop()


app = FastAPI(title="Nexora MQTT Bridge", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mqtt_connected": _mqtt_client is not None,
        "broker": f"{config.MQTT_HOST}:{config.MQTT_PORT}",
        "kafka": "enabled" if _kafka_producer else "disabled",
    }


@app.get("/ready")
async def ready():
    return {"status": "ok"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return generate_latest()


@app.get("/devices")
async def list_known_devices(request: Request):
    """List device_ids known to this bridge instance (in-memory, resets on restart)."""
    key = config.INTERNAL_SERVICE_KEY
    if key:
        header = request.headers.get("x-internal-key", "")
        if not header or not secrets.compare_digest(header, key):
            raise HTTPException(status_code=403, detail="Missing or invalid internal authentication")
    from mqtt_bridge.core.device_registry import _known
    return {"known_devices": sorted(_known)}
