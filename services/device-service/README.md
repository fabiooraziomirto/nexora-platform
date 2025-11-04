# Device Service

Servizio per la gestione dei dispositivi IoT in Stack4Things v2.0.

## Setup

```bash
poetry install
poetry run alembic upgrade head
poetry run uvicorn device_service.main:app --reload
```

## API Documentation

Una volta avviato il servizio, la documentazione OpenAPI è disponibile su:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

```bash
poetry run pytest
```

## Environment Variables

- `DATABASE_URL`: MySQL connection string (mysql+pymysql://user:pass@host/db)
- `REDIS_URL`: Redis connection string
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers
- `LOG_LEVEL`: Log level (default: INFO)

