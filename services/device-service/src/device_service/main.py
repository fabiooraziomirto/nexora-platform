from contextlib import asynccontextmanager
import csv
import html
import io
import json
from datetime import datetime, timezone
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
import structlog
from uuid import uuid4
import time

from device_service.api import devices
from device_service.api import discovery
from device_service.api import privacy
from device_service.api import shadow
from device_service.api import slo
from device_service.api import telemetry
# Ensure all ORM models are registered with Base.metadata before init_db()
from device_service.models import device as _m_device  # noqa: F401
from device_service.models import device_shadow as _m_shadow  # noqa: F401
from device_service.models import device_slo as _m_slo  # noqa: F401
from device_service.models import device_telemetry as _m_telemetry  # noqa: F401
from device_service.core.config import settings
from device_service.core.database import engine, init_db
from device_service.core.events import event_bus
from device_service.core.metrics import setup_metrics, get_metrics_response
from device_service.core.rate_limit import limiter
from device_service.core.tracing import setup_tracing
from device_service.core.auth import CurrentUser, get_current_user
from common.audit import read_audit_events

logger = structlog.get_logger()

AUDIT_EXPORT_FIELDS = [
    "timestamp",
    "service",
    "actor_user_id",
    "actor_tenant_id",
    "actor_roles",
    "action",
    "resource_type",
    "resource_id",
    "tenant_id",
    "correlation_id",
    "outcome",
    "reason",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Device Service", version=settings.VERSION)

    if settings.ENVIRONMENT == "production" and not settings.AUTH_ENABLED:
        raise RuntimeError("AUTH_ENABLED=false is not allowed when ENVIRONMENT=production")
    if settings.ENVIRONMENT == "production" and settings.AUTH_DEV_BYPASS_ENABLED:
        raise RuntimeError("AUTH_DEV_BYPASS_ENABLED=true is not allowed when ENVIRONMENT=production")
    if settings.AUTH_DEV_BYPASS_ENABLED:
        logger.warning("AUTH DEV BYPASS ENABLED — NOT FOR PRODUCTION")
    
    # Initialize database
    await init_db()
    
    # Initialize event bus
    await event_bus.connect()
    
    # Setup metrics and tracing
    setup_metrics()
    setup_tracing()
    
    # CORS safety check
    if "*" in settings.CORS_ORIGINS and not settings.DEBUG:
        logger.warning(
            "cors_wildcard_in_production",
            detail="CORS_ORIGINS contains '*' — set explicit origins in production",
        )

    logger.info("Device Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Device Service")
    await event_bus.disconnect()
    await engine.dispose()


app = FastAPI(
    title="Nxr Device Service",
    description="Device Management Service for Nxr v2.0",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiter state and 429 handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers — discovery first so /devices/pending and /devices/announce
# are matched before the /devices/{device_id} path parameter in devices.router
app.include_router(discovery.router, prefix="/api/v2", tags=["discovery"])
app.include_router(privacy.router, prefix="/api/v2", tags=["privacy"])
app.include_router(shadow.router, prefix="/api/v2", tags=["shadow"])
app.include_router(telemetry.router, prefix="/api/v2", tags=["telemetry"])
app.include_router(slo.router, prefix="/api/v2", tags=["slo"])
app.include_router(devices.router, prefix="/api/v2", tags=["devices"])


@app.middleware("http")
async def trace_context_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or uuid4().hex
    correlation_id = request.headers.get("x-correlation-id", trace_id)
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    response.headers["x-trace-id"] = trace_id
    response.headers["x-correlation-id"] = correlation_id
    logger.info(
        "request_completed",
        trace_id=trace_id,
        correlation_id=correlation_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_s=round(elapsed, 6),
    )
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "device-service"}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database not ready: {exc}")

    if settings.KAFKA_REQUIRED and not event_bus.connected:
        raise HTTPException(status_code=503, detail="kafka not ready")

    return {
        "status": "ready",
        "service": "device-service",
        "database": "ok",
        "kafka_connected": event_bus.connected,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return get_metrics_response()


@app.get("/api/v2/audit/events")
async def list_audit_events(
    tenant_id: str | None = Query(default=None),
    actor_user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    current_user: CurrentUser = Depends(get_current_user),
):
    events = _authorized_audit_events(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        from_=from_,
        to=to,
        current_user=current_user,
    )
    start = (page - 1) * page_size
    end = start + page_size
    return {"items": events[start:end], "total": len(events), "page": page, "page_size": page_size}


@app.get("/api/v2/audit/events/export")
async def export_audit_events(
    tenant_id: str | None = Query(default=None),
    actor_user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    format: str = Query(default="json", pattern="^(json|csv|html)$"),
    limit: int = Query(default=1000, ge=1, le=5000),
    current_user: CurrentUser = Depends(get_current_user),
):
    events = _authorized_audit_events(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        from_=from_,
        to=to,
        current_user=current_user,
    )[:limit]
    generated_at = datetime.now(timezone.utc).isoformat()
    filename = f"nexora-audit-evidence-{generated_at[:10]}.{format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    if format == "json":
        payload = {
            "generated_at": generated_at,
            "total": len(events),
            "fields": AUDIT_EXPORT_FIELDS,
            "items": events,
        }
        return Response(
            content=json.dumps(payload, indent=2, default=str),
            media_type="application/json",
            headers=headers,
        )

    if format == "csv":
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=AUDIT_EXPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for event in events:
            row = dict(event)
            row["actor_roles"] = ",".join(row.get("actor_roles") or [])
            writer.writerow(row)
        return Response(content=out.getvalue(), media_type="text/csv", headers=headers)

    rows = "\n".join(
        "<tr>"
        + "".join(f"<td>{html.escape(_audit_cell(event.get(field)))}</td>" for field in AUDIT_EXPORT_FIELDS)
        + "</tr>"
        for event in events
    )
    headings = "".join(f"<th>{html.escape(field)}</th>" for field in AUDIT_EXPORT_FIELDS)
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Nexora Audit Evidence Export</title>
  <style>
    body {{ font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #0f172a; margin: 32px; }}
    h1 {{ font-size: 20px; margin: 0 0 4px; }}
    p {{ margin: 0 0 18px; color: #475569; font-size: 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f5f9; color: #334155; }}
    td {{ word-break: break-word; }}
  </style>
</head>
<body>
  <h1>Nexora Audit Evidence Export</h1>
  <p>Generated at {html.escape(generated_at)} UTC. Events included: {len(events)}.</p>
  <table>
    <thead><tr>{headings}</tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""
    return Response(content=document, media_type="text/html", headers=headers)


def _authorized_audit_events(
    *,
    tenant_id: str | None,
    actor_user_id: str | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    from_: str | None,
    to: str | None,
    current_user: CurrentUser,
):
    if not settings.AUTH_ENABLED:
        events = read_audit_events(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            from_ts=from_,
            to_ts=to,
        )
        return list(reversed(events))

    roles = set(current_user.roles)
    is_platform_admin = (
        settings.AUTH_PLATFORM_ADMIN_ROLE in roles
        or settings.AUTH_OPERATOR_ROLE in roles
        or current_user.is_operator
    )
    is_tenant_admin = settings.AUTH_TENANT_ADMIN_ROLE in roles or is_platform_admin
    if not is_tenant_admin:
        raise HTTPException(status_code=403, detail="tenant-admin role required")
    effective_tenant = tenant_id if is_platform_admin else current_user.tenant_id
    events = read_audit_events(
        tenant_id=effective_tenant,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        from_ts=from_,
        to_ts=to,
    )
    return list(reversed(events))


def _audit_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)
