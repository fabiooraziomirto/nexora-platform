# Common Library

Libreria comune condivisa tra tutti i microservizi Stack4Things v2.0.

## Features

- ✅ Database utilities (SQLAlchemy async)
- ✅ Event bus client (Kafka/NATS)
- ✅ Redis client
- ✅ Logging utilities (structured logging)
- ✅ Configuration management (Pydantic Settings)
- ✅ Error handling utilities
- ✅ Health check utilities
- ✅ Metrics utilities (Prometheus)

## Installation

```bash
cd libraries/common
poetry install
```

## Usage

### Configuration

```python
from common import settings

# Access settings
print(settings.DATABASE_URL)
print(settings.REDIS_HOST)
```

### Database

```python
from common import get_db_session, Base, init_db
from sqlalchemy.ext.asyncio import AsyncSession

# Initialize database
await init_db()

# Use in FastAPI dependency
async def get_db():
    async for session in get_db_session():
        yield session
```

### Event Bus

```python
from common import get_event_bus, EventBusType

# Get Kafka event bus
event_bus = get_event_bus(EventBusType.KAFKA)
await event_bus.connect()

# Publish event
await event_bus.publish("device.created", {"device_id": "123"})

# Subscribe to events
async def handle_event(event_type: str, data: dict):
    print(f"Received {event_type}: {data}")

await event_bus.subscribe(["device.created", "device.updated"], handle_event)
```

### Cache (Redis)

```python
from common import get_cache

cache = get_cache()
await cache.connect()

# Set value
await cache.set("key", {"data": "value"}, ttl=3600)

# Get value
value = await cache.get("key")

# Delete key
await cache.delete("key")
```

### Logging

```python
from common import setup_logging, get_logger

# Setup logging (typically in main.py)
setup_logging(log_level="INFO", log_format="json")

# Use logger
logger = get_logger(__name__)
logger.info("Service started", version="1.0.0")
```

### Error Handling

```python
from common import NotFoundError, ValidationError

# Raise errors
if not device:
    raise NotFoundError("device", device_id)

if not valid:
    raise ValidationError("Invalid data", field="name")

# Handle in FastAPI
try:
    # ...
except NotFoundError as e:
    raise e.to_http_exception()
```

### Health Checks

```python
from common import HealthChecker, check_database, check_redis

checker = HealthChecker()
checker.add_check("database", check_database)
checker.add_check("redis", check_redis)

# Run all checks
status = await checker.check_all()
```

### Metrics

```python
from common import get_metrics

metrics = get_metrics()

# Counter
counter = metrics.counter("requests_total", "Total requests")
counter.inc()

# Histogram
histogram = metrics.histogram("request_duration", "Request duration")
histogram.observe(0.5)

# Gauge
gauge = metrics.gauge("active_connections", "Active connections")
gauge.set(10)

# Use in FastAPI
@app.get("/metrics")
async def metrics_endpoint():
    return metrics.get_metrics_response()
```

## Module Structure

```
common/
├── config/          # Configuration management
├── database/         # Database utilities
├── events/           # Event bus client
├── cache/            # Redis client
├── logging/          # Structured logging
├── errors/           # Error handling
├── health/           # Health checks
└── metrics/          # Prometheus metrics
```

## Configuration

The library uses Pydantic Settings for configuration. Set environment variables:

```bash
# Database
DATABASE_URL=mysql+pymysql://user:pass@host:port/db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_PREFIX=stack4things

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Development

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Format code
poetry run black .
poetry run ruff check .
```
