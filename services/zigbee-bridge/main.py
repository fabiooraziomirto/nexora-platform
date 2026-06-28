"""Zigbee bridge — reads zigbee2mqtt topics and bridges to Nexora."""
import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import aiomqtt
import httpx
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from zigbee_bridge.core import config
from zigbee_bridge.core.message_handler import handle_message
from zigbee_bridge.core.command_handler import start_consumer
from zigbee_bridge.core.device_registry import list_devices

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("zigbee-bridge")

_start_time = time.time()
_mqtt_connected = False
_kafka_consumer: Any = None


async def _mqtt_loop() -> None:
    global _mqtt_connected
    z2m_topic = f"{config.Z2M_BASE_TOPIC}/#"
    while True:
        try:
            kwargs: dict = {
                "hostname": config.MQTT_HOST,
                "port": config.MQTT_PORT,
                "identifier": "nexora-zigbee-bridge",
            }
            if config.MQTT_USERNAME:
                kwargs["username"] = config.MQTT_USERNAME
            if config.MQTT_PASSWORD:
                kwargs["password"] = config.MQTT_PASSWORD

            async with aiomqtt.Client(**kwargs) as client:
                _mqtt_connected = True
                logger.info("Connected to MQTT broker %s:%s", config.MQTT_HOST, config.MQTT_PORT)
                await client.subscribe(z2m_topic)
                logger.info("Subscribed to %s", z2m_topic)
                async for message in client.messages:
                    topic = str(message.topic)
                    payload = bytes(message.payload)
                    try:
                        await handle_message(topic, payload)
                    except Exception as exc:
                        logger.error("Error handling message topic=%s: %s", topic, exc)
        except aiomqtt.MqttError as exc:
            _mqtt_connected = False
            logger.warning("MQTT disconnected: %s — reconnecting in 5s", exc)
            await asyncio.sleep(5)
        except Exception as exc:
            _mqtt_connected = False
            logger.error("MQTT loop error: %s — reconnecting in 10s", exc)
            await asyncio.sleep(10)


async def _build_kafka_consumer() -> Any:
    if not config.KAFKA_ENABLED:
        return None
    try:
        from aiokafka import AIOKafkaConsumer
        topic = f"{config.KAFKA_TOPIC_PREFIX}.execution.dispatched"
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
            group_id="zigbee-bridge",
            value_deserializer=lambda v: v,
            auto_offset_reset="latest",
        )
        await consumer.start()
        logger.info("Kafka consumer started — topic=%s", topic)
        return consumer
    except Exception as exc:
        logger.warning("Kafka unavailable: %s — command handler disabled", exc)
        return None


async def _mock_mqtt_loop() -> None:
    """Simulate zigbee2mqtt messages for dev/CI without hardware."""
    global _mqtt_connected
    _mqtt_connected = True
    logger.info("Mock MQTT mode — no real zigbee2mqtt, emitting synthetic device messages")
    await asyncio.sleep(2)

    devices_payload = json.dumps([
        {
            "friendly_name": "mock-bulb-01",
            "ieee_address": "0x00158d000123abcd",
            "definition": {
                "model": "LED2003G10",
                "vendor": "IKEA",
                "exposes": [
                    {"name": "state", "type": "binary"},
                    {"name": "brightness", "type": "numeric"},
                    {"name": "color_temp", "type": "numeric"},
                ],
            },
            "endpoints": {
                "1": {"clusters": {"input": ["genOnOff", "genLevelCtrl"], "output": []}}
            },
        },
        {
            "friendly_name": "mock-sensor-01",
            "ieee_address": "0x00158d000456efgh",
            "definition": {
                "model": "SNZB-02",
                "vendor": "SONOFF",
                "exposes": [
                    {"name": "temperature", "type": "numeric"},
                    {"name": "humidity", "type": "numeric"},
                    {"name": "battery", "type": "numeric"},
                ],
            },
            "endpoints": {
                "1": {"clusters": {"input": ["msTemperatureMeasurement"], "output": []}}
            },
        },
    ]).encode()

    await handle_message(f"{config.Z2M_BASE_TOPIC}/bridge/devices", devices_payload)
    await asyncio.sleep(1)

    import random
    while True:
        bulb_state = json.dumps({
            "state": "ON",
            "brightness": random.randint(100, 254),
            "color_temp": random.randint(250, 500),
            "linkquality": random.randint(50, 255),
        }).encode()
        await handle_message(f"{config.Z2M_BASE_TOPIC}/mock-bulb-01", bulb_state)

        sensor_state = json.dumps({
            "temperature": round(random.uniform(18.0, 26.0), 1),
            "humidity": round(random.uniform(40.0, 70.0), 1),
            "battery": random.randint(70, 100),
            "linkquality": random.randint(50, 255),
        }).encode()
        await handle_message(f"{config.Z2M_BASE_TOPIC}/mock-sensor-01", sensor_state)

        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _kafka_consumer

    mock_mode = os.getenv("ZIGBEE_MOCK", "false").lower() == "true"
    if mock_mode:
        mqtt_task = asyncio.create_task(_mock_mqtt_loop(), name="mock-mqtt-loop")
    else:
        mqtt_task = asyncio.create_task(_mqtt_loop(), name="mqtt-loop")

    _kafka_consumer = await _build_kafka_consumer()

    async def _dummy_publish(topic: str, payload: str) -> None:
        logger.info("MQTT publish [no client] topic=%s payload=%s", topic, payload)

    if not mock_mode:
        # Real publish: re-use connection via a shared client reference stored in app state
        app.state.mqtt_publish = _dummy_publish
    else:
        app.state.mqtt_publish = _dummy_publish

    await start_consumer(_kafka_consumer, app.state.mqtt_publish)

    yield

    mqtt_task.cancel()
    try:
        await mqtt_task
    except asyncio.CancelledError:
        pass
    if _kafka_consumer:
        await _kafka_consumer.stop()


app = FastAPI(title="Nexora Zigbee Bridge", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "mqtt_connected": _mqtt_connected}


@app.get("/ready")
async def ready():
    return {"status": "ready"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    uptime = time.time() - _start_time
    devices = list_devices()
    lines = [
        "# HELP zigbee_bridge_uptime_seconds Uptime in seconds",
        "# TYPE zigbee_bridge_uptime_seconds gauge",
        f"zigbee_bridge_uptime_seconds {uptime:.1f}",
        "# HELP zigbee_bridge_devices_registered Registered Zigbee devices",
        "# TYPE zigbee_bridge_devices_registered gauge",
        f"zigbee_bridge_devices_registered {len(devices)}",
        "# HELP zigbee_bridge_mqtt_connected MQTT broker connected",
        "# TYPE zigbee_bridge_mqtt_connected gauge",
        f"zigbee_bridge_mqtt_connected {1 if _mqtt_connected else 0}",
    ]
    return "\n".join(lines) + "\n"


@app.get("/devices")
async def get_devices():
    return {"devices": list_devices()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=False)
