import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from ai_pipeline_service.api.functions import router as functions_router
from ai_pipeline_service.api.insights import router as insights_router
from ai_pipeline_service.api.query import router as query_router
from ai_pipeline_service.api.risk import router as risk_router
from ai_pipeline_service.core import events
from ai_pipeline_service.core.config import settings
from ai_pipeline_service.core.database import engine, ensure_ai_columns, init_db
from ai_pipeline_service.core.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    metrics_response,
)
from ai_pipeline_service.models import insight as _insight_model  # noqa: F401

logging.basicConfig(level=settings.LOG_LEVEL, format="%(message)s")
logger = logging.getLogger("ai-pipeline-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Pipeline Service")
    init_db()
    ensure_ai_columns()
    events.start_consumer()
    yield
    await events.stop_consumer()
    engine.dispose()


app = FastAPI(
    title="Nexora AI Pipeline Service",
    description="AIOps insights and recommendations for Nexora",
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or uuid4().hex
    correlation_id = request.headers.get("x-correlation-id", trace_id)
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    response.headers["x-trace-id"] = trace_id
    response.headers["x-correlation-id"] = correlation_id
    HTTP_REQUESTS_TOTAL.labels(request.method, request.url.path, str(response.status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(request.method, request.url.path).observe(elapsed)
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "ai-pipeline-service"}


@app.get("/ready")
async def ready() -> dict[str, str | bool]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database not ready: {exc}")
    if settings.KAFKA_REQUIRED and not events.kafka_connected:
        raise HTTPException(status_code=503, detail="kafka not ready")
    return {
        "status": "ready",
        "service": "ai-pipeline-service",
        "database": "ok",
        "kafka_connected": events.kafka_connected,
        "llm_enabled": settings.AI_LLM_ENABLED,
    }


@app.get("/metrics")
async def metrics():
    return metrics_response()


app.include_router(insights_router)
app.include_router(risk_router)
app.include_router(query_router)
app.include_router(functions_router)
