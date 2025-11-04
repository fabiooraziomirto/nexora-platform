"""
Event bus client for Kafka and NATS.
"""

from typing import Optional, Dict, Any, List
import json
import asyncio
from enum import Enum

from common.config import settings
from common.logging import get_logger

logger = get_logger(__name__)


class EventBusType(str, Enum):
    """Event bus type."""
    KAFKA = "kafka"
    NATS = "nats"


class EventBus:
    """Event bus client for publishing and consuming events."""

    def __init__(
        self,
        bus_type: EventBusType = EventBusType.KAFKA,
        bootstrap_servers: Optional[str] = None,
        topic_prefix: Optional[str] = None,
    ):
        self.bus_type = bus_type
        self.bootstrap_servers = bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS
        self.topic_prefix = topic_prefix or settings.KAFKA_TOPIC_PREFIX
        self._producer = None
        self._consumer = None
        self._connected = False

    async def connect(self):
        """Connect to event bus."""
        if self.bus_type == EventBusType.KAFKA:
            await self._connect_kafka()
        elif self.bus_type == EventBusType.NATS:
            await self._connect_nats()
        else:
            raise ValueError(f"Unsupported event bus type: {self.bus_type}")

    async def disconnect(self):
        """Disconnect from event bus."""
        if self.bus_type == EventBusType.KAFKA:
            await self._disconnect_kafka()
        elif self.bus_type == EventBusType.NATS:
            await self._disconnect_nats()
        
        self._connected = False

    async def _connect_kafka(self):
        """Connect to Kafka."""
        try:
            import aiokafka
            
            servers = self.bootstrap_servers.split(",")
            
            self._producer = aiokafka.AIOKafkaProducer(
                bootstrap_servers=servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            
            await self._producer.start()
            self._connected = True
            
            logger.info(
                "Kafka producer connected",
                servers=servers,
                topic_prefix=self.topic_prefix,
            )
        except ImportError:
            logger.error("aiokafka not installed. Install with: pip install aiokafka")
            raise
        except Exception as e:
            logger.error("Failed to connect to Kafka", error=str(e))
            raise

    async def _disconnect_kafka(self):
        """Disconnect from Kafka."""
        if self._producer:
            try:
                await self._producer.stop()
                logger.info("Kafka producer disconnected")
            except Exception as e:
                logger.error("Error disconnecting Kafka producer", error=str(e))
            finally:
                self._producer = None

    async def _connect_nats(self):
        """Connect to NATS."""
        try:
            import nats.aio.client as nats
            
            if not settings.NATS_URL:
                raise ValueError("NATS_URL not configured")
            
            self._client = await nats.connect(
                servers=[settings.NATS_URL],
                name=settings.NATS_CLIENT_ID or "stack4things-service",
            )
            self._connected = True
            
            logger.info(
                "NATS client connected",
                url=settings.NATS_URL,
                client_id=settings.NATS_CLIENT_ID,
            )
        except ImportError:
            logger.error("nats-py not installed. Install with: pip install nats-py")
            raise
        except Exception as e:
            logger.error("Failed to connect to NATS", error=str(e))
            raise

    async def _disconnect_nats(self):
        """Disconnect from NATS."""
        if hasattr(self, "_client") and self._client:
            try:
                await self._client.close()
                logger.info("NATS client disconnected")
            except Exception as e:
                logger.error("Error disconnecting NATS client", error=str(e))
            finally:
                self._client = None

    async def publish(
        self,
        event_type: str,
        data: Dict[str, Any],
        key: Optional[str] = None,
    ):
        """Publish event to event bus."""
        if not self._connected:
            logger.warning("Event bus not connected, skipping event", event_type=event_type)
            return

        topic = f"{self.topic_prefix}.{event_type}"

        try:
            if self.bus_type == EventBusType.KAFKA:
                await self._publish_kafka(topic, data, key)
            elif self.bus_type == EventBusType.NATS:
                await self._publish_nats(topic, data)
            
            logger.debug("Event published", event_type=event_type, topic=topic)
        except Exception as e:
            logger.error("Failed to publish event", event_type=event_type, error=str(e))
            raise

    async def _publish_kafka(self, topic: str, data: Dict[str, Any], key: Optional[str] = None):
        """Publish event to Kafka."""
        if not self._producer:
            raise RuntimeError("Kafka producer not initialized")
        
        await self._producer.send_and_wait(topic, data, key=key.encode() if key else None)

    async def _publish_nats(self, topic: str, data: Dict[str, Any]):
        """Publish event to NATS."""
        if not hasattr(self, "_client") or not self._client:
            raise RuntimeError("NATS client not initialized")
        
        payload = json.dumps(data).encode()
        await self._client.publish(topic, payload)

    async def subscribe(
        self,
        event_types: List[str],
        handler: callable,
        consumer_group: Optional[str] = None,
    ):
        """Subscribe to events."""
        if not self._connected:
            raise RuntimeError("Event bus not connected")
        
        if self.bus_type == EventBusType.KAFKA:
            await self._subscribe_kafka(event_types, handler, consumer_group)
        elif self.bus_type == EventBusType.NATS:
            await self._subscribe_nats(event_types, handler)

    async def _subscribe_kafka(
        self,
        event_types: List[str],
        handler: callable,
        consumer_group: Optional[str] = None,
    ):
        """Subscribe to Kafka topics."""
        try:
            import aiokafka
            
            group_id = consumer_group or settings.KAFKA_CONSUMER_GROUP
            topics = [f"{self.topic_prefix}.{et}" for et in event_types]
            
            self._consumer = aiokafka.AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.bootstrap_servers.split(","),
                group_id=group_id,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_commit=settings.KAFKA_AUTO_COMMIT,
            )
            
            await self._consumer.start()
            
            logger.info("Kafka consumer started", topics=topics, group_id=group_id)
            
            async for msg in self._consumer:
                try:
                    event_type = msg.topic.replace(f"{self.topic_prefix}.", "")
                    await handler(event_type, msg.value)
                except Exception as e:
                    logger.error("Error handling event", error=str(e), event_type=event_type)
        except ImportError:
            logger.error("aiokafka not installed")
            raise

    async def _subscribe_nats(self, event_types: List[str], handler: callable):
        """Subscribe to NATS subjects."""
        if not hasattr(self, "_client") or not self._client:
            raise RuntimeError("NATS client not initialized")
        
        async def message_handler(msg):
            try:
                event_type = msg.subject.replace(f"{self.topic_prefix}.", "")
                data = json.loads(msg.data.decode())
                await handler(event_type, data)
            except Exception as e:
                logger.error("Error handling NATS message", error=str(e))
        
        for event_type in event_types:
            subject = f"{self.topic_prefix}.{event_type}"
            await self._client.subscribe(subject, cb=message_handler)
            logger.info("Subscribed to NATS subject", subject=subject)


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus(
    bus_type: Optional[EventBusType] = None,
    bootstrap_servers: Optional[str] = None,
    topic_prefix: Optional[str] = None,
) -> EventBus:
    """Get or create global event bus instance."""
    global _event_bus
    
    if _event_bus is None:
        bus_type = bus_type or EventBusType.KAFKA
        _event_bus = EventBus(
            bus_type=bus_type,
            bootstrap_servers=bootstrap_servers,
            topic_prefix=topic_prefix,
        )
    
    return _event_bus

