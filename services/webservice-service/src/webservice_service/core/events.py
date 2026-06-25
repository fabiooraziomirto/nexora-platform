import asyncio
import json
import logging
import time
from typing import Any

import aiokafka

from webservice_service.core.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC_PREFIX,
    KAFKA_RETRY_ATTEMPTS,
    KAFKA_RETRY_DELAY_SECONDS,
)

logger = logging.getLogger("webservice-service")

producer: aiokafka.AIOKafkaProducer | None = None


async def publish_event(action: str, resource_id: str, payload: dict[str, Any]) -> None:
    if not producer:
        logger.warning(
            "Kafka producer not available, skipping event",
            extra={"action": action, "resource_id": resource_id},
        )
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
            logger.exception(
                "Kafka publish failed",
                extra={"attempt": attempt, "topic": topic, "resource_id": resource_id},
            )
            if attempt < KAFKA_RETRY_ATTEMPTS:
                await asyncio.sleep(KAFKA_RETRY_DELAY_SECONDS * attempt)
