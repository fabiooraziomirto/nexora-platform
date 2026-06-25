import os
from typing import Any
import base64
import json
import time
import logging
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest
from sqlalchemy import Column, String, create_engine, func, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker

app = FastAPI(
    title="Stack4Things Plugin Service",
    description="Plugin management microservice",
    version="0.1.0",
)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./plugin_service.db")
DB_CONNECT_TIMEOUT_SECONDS = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5"))
Base = declarative_base()
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": DB_CONNECT_TIMEOUT_SECONDS} if "mysql" in DATABASE_URL else {"timeout": DB_CONNECT_TIMEOUT_SECONDS},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
AUTH_DEV_TOKEN = os.getenv("AUTH_DEV_TOKEN", "dev-token")
AUTH_DEV_BYPASS_ENABLED = os.getenv("AUTH_DEV_BYPASS_ENABLED", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "")
AUTH_WRITE_ROLE = os.getenv("AUTH_WRITE_ROLE", "writer")
logger = logging.getLogger("plugin-service")
HTTP_REQUESTS_TOTAL = Counter("s4t_http_requests_total", "Total HTTP requests", ["service", "method", "path", "status"])
HTTP_REQUEST_DURATION_SECONDS = Histogram("s4t_http_request_duration_seconds", "HTTP request duration", ["service", "method", "path"])


class Plugin(Base):
    __tablename__ = "plugins"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(64), nullable=False, default="0.1.0")


@app.on_event("startup")
def startup() -> None:
    if AUTH_DEV_BYPASS_ENABLED:
        if ENVIRONMENT == "production":
            raise RuntimeError("AUTH_DEV_BYPASS_ENABLED=true is not allowed when ENVIRONMENT=production")
        logger.warning("AUTH DEV BYPASS ENABLED — NOT FOR PRODUCTION")
    Base.metadata.create_all(bind=engine)


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        data = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
        return json.loads(data)
    except Exception:
        return None


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not AUTH_ENABLED:
        return await call_next(request)

    if request.url.path in {"/health", "/ready", "/metrics"}:
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "missing bearer token"})

    token = auth.split(" ", 1)[1]
    if AUTH_DEV_BYPASS_ENABLED and token == AUTH_DEV_TOKEN:
        return await call_next(request)

    payload = _decode_jwt_payload(token)
    if not payload:
        return JSONResponse(status_code=401, content={"detail": "invalid token"})

    exp = payload.get("exp")
    if exp and float(exp) < time.time():
        return JSONResponse(status_code=401, content={"detail": "token expired"})

    if KEYCLOAK_ISSUER and payload.get("iss") != KEYCLOAK_ISSUER:
        return JSONResponse(status_code=401, content={"detail": "invalid issuer"})

    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        realm_access = payload.get("realm_access", {})
        roles = set(realm_access.get("roles", []))
        if AUTH_WRITE_ROLE and AUTH_WRITE_ROLE not in roles:
            return JSONResponse(status_code=403, content={"detail": "forbidden"})

    return await call_next(request)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or uuid4().hex
    correlation_id = request.headers.get("x-correlation-id", trace_id)
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    response.headers["x-trace-id"] = trace_id
    response.headers["x-correlation-id"] = correlation_id
    HTTP_REQUESTS_TOTAL.labels("plugin-service", request.method, request.url.path, str(response.status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels("plugin-service", request.method, request.url.path).observe(elapsed)
    logger.info(json.dumps({"service": "plugin-service", "trace_id": trace_id, "correlation_id": correlation_id, "method": request.method, "path": request.url.path, "status": response.status_code, "duration_s": round(elapsed, 6)}))
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "plugin-service"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(select(func.count()).select_from(Plugin))
    return {"status": "ready", "service": "plugin-service", "database": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")


@app.get("/api/v2/plugins")
async def list_plugins() -> dict[str, Any]:
    with SessionLocal() as db:
        items = db.execute(select(Plugin)).scalars().all()
        payload = [{"id": p.id, "name": p.name, "version": p.version} for p in items]
    return {"items": payload, "total": len(payload)}


@app.post("/api/v2/plugins", status_code=201)
async def create_plugin(payload: dict[str, Any]) -> dict[str, Any]:
    if "name" not in payload or not payload["name"]:
        raise HTTPException(status_code=400, detail="name is required")
    plugin_id = str(uuid4())
    data = Plugin(id=plugin_id, name=payload["name"], version=payload.get("version", "0.1.0"))
    with SessionLocal() as db:
        db.add(data)
        db.commit()
    return {"id": data.id, "name": data.name, "version": data.version}


@app.get("/api/v2/plugins/{plugin_id}")
async def get_plugin(plugin_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="plugin not found")
    return {"id": plugin.id, "name": plugin.name, "version": plugin.version}


@app.patch("/api/v2/plugins/{plugin_id}")
async def update_plugin(plugin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        if "name" in payload and payload["name"]:
            plugin.name = payload["name"]
        if "version" in payload and payload["version"]:
            plugin.version = payload["version"]
        db.commit()
        db.refresh(plugin)
    return {"id": plugin.id, "name": plugin.name, "version": plugin.version}


@app.delete("/api/v2/plugins/{plugin_id}", status_code=204)
async def delete_plugin(plugin_id: str) -> None:
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        db.delete(plugin)
        db.commit()
