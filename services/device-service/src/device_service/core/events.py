from typing import Optional
import json
import aiokafka
from device_service.core.config import settings
import structlog

logger = structlog.get_logger()


class EventBus:
    """Event bus for publishing events to Kafka."""
    
    def __init__(self):
        self.producer: Optional[aiokafka.AIOKafkaProducer] = None
        self.bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS.split(",")
        self.topic_prefix = settings.KAFKA_TOPIC_PREFIX
        self.connected = False
    
    async def connect(self):
        """Connect to Kafka."""
        if not settings.KAFKA_ENABLED:
            logger.info("Event bus disabled by configuration")
            self.connected = False
            return
        try:
            self.producer = aiokafka.AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self.producer.start()
            self.connected = True
            logger.info("Event bus connected", servers=self.bootstrap_servers)
        except Exception as e:
            logger.error("Failed to connect event bus", error=str(e))
            self.connected = False
            if settings.KAFKA_REQUIRED:
                raise
    
    async def disconnect(self):
        """Disconnect from Kafka."""
        if self.producer:
            await self.producer.stop()
            logger.info("Event bus disconnected")
        self.connected = False
    
    async def publish(self, event_type: str, data: dict):
        """Publish event to Kafka."""
        if not self.producer or not self.connected:
            logger.warning("Event bus not connected, skipping event", event_type=event_type)
            return
        
        topic = f"{self.topic_prefix}.{event_type}"
        try:
            await self.producer.send_and_wait(topic, data)
            logger.debug("Event published", event_type=event_type, topic=topic)
        except Exception as e:
            logger.error("Failed to publish event", event_type=event_type, error=str(e))


event_bus = EventBus()

