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

app = FastAPI(title="DNS Service", version="0.1.0")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dns_service.db")
Base = declarative_base()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
AUTH_DEV_TOKEN = os.getenv("AUTH_DEV_TOKEN", "dev-token")
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "")
AUTH_WRITE_ROLE = os.getenv("AUTH_WRITE_ROLE", "writer")


class DNSRecord(Base):
    __tablename__ = "dns_records"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    type = Column(String(16), nullable=False, default="A")
    value = Column(String(255), nullable=True)


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
    return {"status": "healthy", "service": "dns-service"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(select(func.count()).select_from(DNSRecord))
    return {"status": "ready", "service": "dns-service", "database": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")


@app.get("/api/v2/dns/records")
async def list_records() -> dict[str, Any]:
    with SessionLocal() as db:
        items = db.execute(select(DNSRecord)).scalars().all()
        payload = [{"id": r.id, "name": r.name, "type": r.type, "value": r.value} for r in items]
    return {"items": payload, "total": len(payload)}


@app.post("/api/v2/dns/records", status_code=201)
async def create_record(payload: dict[str, Any]) -> dict[str, Any]:
    record_id = str(uuid4())
    record = DNSRecord(
        id=record_id,
        name=payload.get("name"),
        type=payload.get("type", "A"),
        value=payload.get("value"),
    )
    with SessionLocal() as db:
        db.add(record)
        db.commit()
    return {"id": record.id, "name": record.name, "type": record.type, "value": record.value}


@app.get("/api/v2/dns/records/{record_id}")
async def get_record(record_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        record = db.get(DNSRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="record not found")
    return {"id": record.id, "name": record.name, "type": record.type, "value": record.value}


@app.delete("/api/v2/dns/records/{record_id}", status_code=204)
async def delete_record(record_id: str) -> None:
    with SessionLocal() as db:
        record = db.get(DNSRecord, record_id)
        if not record:
            raise HTTPException(status_code=404, detail="record not found")
        db.delete(record)
        db.commit()
