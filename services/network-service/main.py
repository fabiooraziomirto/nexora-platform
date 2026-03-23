import os
from typing import Any
import base64
import json
import time
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest
from sqlalchemy import Column, String, create_engine, func, select
from sqlalchemy.orm import declarative_base, sessionmaker

app = FastAPI(title="Network Service", version="0.1.0")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./network_service.db")
Base = declarative_base()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
AUTH_DEV_TOKEN = os.getenv("AUTH_DEV_TOKEN", "dev-token")
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "")
AUTH_WRITE_ROLE = os.getenv("AUTH_WRITE_ROLE", "writer")


class Port(Base):
    __tablename__ = "ports"

    id = Column(String(36), primary_key=True, index=True)
    device_id = Column(String(64), nullable=True, index=True)
    network_id = Column(String(64), nullable=True, index=True)
    status = Column(String(64), nullable=False, default="created")


@app.on_event("startup")
def startup() -> None:
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
    if token == AUTH_DEV_TOKEN:
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "network-service"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(select(func.count()).select_from(Port))
    return {"status": "ready", "service": "network-service", "database": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")


@app.get("/api/v2/ports")
async def list_ports() -> dict[str, Any]:
    with SessionLocal() as db:
        items = db.execute(select(Port)).scalars().all()
        payload = [{"id": p.id, "device_id": p.device_id, "network_id": p.network_id, "status": p.status} for p in items]
    return {"items": payload, "total": len(payload)}


@app.post("/api/v2/ports", status_code=201)
async def create_port(payload: dict[str, Any]) -> dict[str, Any]:
    port_id = str(uuid4())
    port = Port(
        id=port_id,
        device_id=payload.get("device_id"),
        network_id=payload.get("network_id"),
        status="created",
    )
    with SessionLocal() as db:
        db.add(port)
        db.commit()
    return {"id": port.id, "device_id": port.device_id, "network_id": port.network_id, "status": port.status}


@app.get("/api/v2/ports/{port_id}")
async def get_port(port_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        port = db.get(Port, port_id)
    if not port:
        raise HTTPException(status_code=404, detail="port not found")
    return {"id": port.id, "device_id": port.device_id, "network_id": port.network_id, "status": port.status}


@app.delete("/api/v2/ports/{port_id}", status_code=204)
async def delete_port(port_id: str) -> None:
    with SessionLocal() as db:
        port = db.get(Port, port_id)
        if not port:
            raise HTTPException(status_code=404, detail="port not found")
        db.delete(port)
        db.commit()
