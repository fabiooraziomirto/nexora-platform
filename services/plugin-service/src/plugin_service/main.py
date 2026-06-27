import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest
from common.auth.context import RequestAuthenticator, auth_settings_from_env

from plugin_service.core.config import (
    AUTH_DEV_BYPASS_ENABLED,
    AUTH_ENABLED,
    ENVIRONMENT,
)
from plugin_service.core.database import Base, engine, SessionLocal, ensure_plugin_columns
from plugin_service.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL
from plugin_service.api.plugins import router as plugins_router

logger = logging.getLogger("plugin-service")
authenticator = RequestAuthenticator(auth_settings_from_env())

app = FastAPI(
    title="Nxr Plugin Service",
    description="Plugin management microservice",
    version="0.1.0",
)


@app.on_event("startup")
def startup() -> None:
    if ENVIRONMENT == "production" and not AUTH_ENABLED:
        raise RuntimeError("AUTH_ENABLED=false is not allowed when ENVIRONMENT=production")
    if AUTH_DEV_BYPASS_ENABLED:
        if ENVIRONMENT == "production":
            raise RuntimeError("AUTH_DEV_BYPASS_ENABLED=true is not allowed when ENVIRONMENT=production")
        logger.warning("AUTH DEV BYPASS ENABLED — NOT FOR PRODUCTION")
    Base.metadata.create_all(bind=engine)
    ensure_plugin_columns()


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    return await authenticator.middleware(request, call_next)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or uuid4().hex
    correlation_id = request.headers.get("x-correlation-id", trace_id)
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    response.headers["x-trace-id"] = trace_id
    response.headers["x-correlation-id"] = correlation_id
    HTTP_REQUESTS_TOTAL.labels(
        "plugin-service", request.method, request.url.path, str(response.status_code)
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        "plugin-service", request.method, request.url.path
    ).observe(elapsed)
    logger.info(json.dumps({
        "service": "plugin-service",
        "trace_id": trace_id,
        "correlation_id": correlation_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_s": round(elapsed, 6),
    }))
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "plugin-service"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")


app.include_router(plugins_router)
