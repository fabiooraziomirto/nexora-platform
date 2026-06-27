import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

import aiokafka

from ai_pipeline_service.core.analyzer import analyze_event
from ai_pipeline_service.core.config import settings
from ai_pipeline_service.core.database import SessionLocal
from ai_pipeline_service.core.llm import summarize_with_ollama
from ai_pipeline_service.core.metrics import EVENTS_PROCESSED_TOTAL, INSIGHTS_CREATED_TOTAL
from ai_pipeline_service.models.insight import AIInsight
from ai_pipeline_service.api.insights import create_insight_from_analysis

logger = logging.getLogger("ai-pipeline-service")

consumer_task: asyncio.Task | None = None
kafka_connected = False

EVENT_TYPES = [
    "device.telemetry.ingested",
    "device.slo.violated",
    "execution.succeeded",
    "execution.failed",
    "execution.callback",
    "execution.timeout",
    "delivery_failed",
    "execution.delivery_failed",
]


async def process_event(event_type: str, payload: dict[str, Any]) -> AIInsight | None:
    EVENTS_PROCESSED_TOTAL.labels(event_type).inc()
    with SessionLocal() as db:
        analysis = analyze_event(event_type, payload, db)
        if not analysis:
            return None
        summary, model_used = await summarize_with_ollama(
            analysis["title"],
            analysis["category"],
            analysis["severity"],
            analysis["evidence"],
            analysis["recommendations"],
        )
        insight = create_insight_from_analysis(db, analysis, summary, model_used, insight_id=str(uuid4()))
        INSIGHTS_CREATED_TOTAL.labels(insight.category, insight.severity).inc()
        return insight


async def _consumer_loop() -> None:
    global kafka_connected
    topics = [f"{settings.KAFKA_TOPIC_PREFIX}.{event_type}" for event_type in EVENT_TYPES]
    consumer = aiokafka.AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
        group_id=settings.KAFKA_CONSUMER_GROUP,
        auto_offset_reset="latest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    try:
        await consumer.start()
        kafka_connected = True
        logger.info("AI pipeline Kafka consumer started on %s", topics)
    except Exception:
        kafka_connected = False
        logger.exception("AI pipeline Kafka consumer failed to start")
        if settings.KAFKA_REQUIRED:
            raise
        return

    try:
        async for msg in consumer:
            event_type = msg.topic.replace(f"{settings.KAFKA_TOPIC_PREFIX}.", "", 1)
            try:
                await process_event(event_type, msg.value)
            except Exception:
                logger.exception("Failed to process AI pipeline event %s", event_type)
    finally:
        kafka_connected = False
        await consumer.stop()


def start_consumer() -> None:
    global consumer_task
    if not settings.KAFKA_ENABLED:
        logger.info("AI pipeline Kafka consumer disabled")
        return
    consumer_task = asyncio.create_task(_consumer_loop())


async def stop_consumer() -> None:
    global consumer_task
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        consumer_task = None
