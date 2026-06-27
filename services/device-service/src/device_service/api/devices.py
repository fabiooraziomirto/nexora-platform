import hmac
import time
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from common.audit import emit_audit_event

from device_service.core.config import settings
from device_service.core.database import get_db
from device_service.core.auth import CurrentUser, get_current_user
from device_service.core.rate_limit import limiter, key_by_device_id
from device_service.api.schemas import (
    AgentHeartbeatRequest,
    AgentRegisterRequest,
    AgentStatusResponse,
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    DeviceListResponse,
)
from device_service.services.device_service import DeviceService

logger = structlog.get_logger()
router = APIRouter()


def _parse_bootstrap_tokens(raw: str) -> dict[str, tuple[str, int]]:
    """Return {token_id: (secret, expiry_epoch)} parsed from config string."""
    tokens: dict[str, tuple[str, int]] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) != 3:
            continue
        tid, secret, exp = parts
        try:
            tokens[tid] = (secret, int(exp))
        except ValueError:
            continue
    return tokens


def _get_revoked_token_ids() -> set[str]:
    raw = settings.AGENT_BOOTSTRAP_REVOKED_TOKEN_IDS
    return {t.strip() for t in raw.split(",") if t.strip()}


def _validate_bootstrap_token(header_value: str) -> None:
    import time as _time
    parts = header_value.split(":")
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid bootstrap token format")
    token_id, secret = parts
    revoked = _get_revoked_token_ids()
    if token_id in revoked:
        raise HTTPException(status_code=401, detail="Bootstrap token has been revoked")
    tokens = _parse_bootstrap_tokens(settings.AGENT_BOOTSTRAP_TOKENS)
    entry = tokens.get(token_id)
    if not entry:
        raise HTTPException(status_code=401, detail="Unknown bootstrap token")
    expected_secret, expiry = entry
    if not hmac.compare_digest(secret, expected_secret):
        raise HTTPException(status_code=401, detail="Invalid bootstrap token")
    if _time.time() > expiry:
        raise HTTPException(status_code=401, detail="Bootstrap token has expired")


@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    device_type: str | None = None,
    tenant_id: str | None = None,
    owner_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all devices with pagination and filtering."""
    if current_user and not current_user.is_operator:
        if tenant_id and tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=403, detail="tenant filter requires platform role")
        tenant_id = current_user.tenant_id
        owner_id = owner_id or None
    service = DeviceService(db)
    return await service.list_devices(
        page=page,
        page_size=page_size,
        status=status,
        device_type=device_type,
        tenant_id=tenant_id,
        owner_id=owner_id,
    )


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get device by ID."""
    service = DeviceService(db)
    device = await service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/devices", response_model=DeviceResponse, status_code=201)
async def create_device(
    device_data: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a new device."""
    service = DeviceService(db)
    created = await service.create_device(
        device_data,
        owner_id=current_user.user_id if current_user else None,
        tenant_id=current_user.tenant_id if current_user else None,
    )
    emit_audit_event(
        service="device-service",
        action="device.created",
        resource_type="device",
        resource_id=str(created.id),
        tenant_id=created.tenant_id,
        actor_user_id=current_user.user_id if current_user else None,
        actor_tenant_id=current_user.tenant_id if current_user else None,
        actor_roles=current_user.roles if current_user else [],
    )
    return created


@router.patch("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    device_data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update device."""
    service = DeviceService(db)
    device_raw = await service.get_device_raw(device_id)
    if not device_raw:
        raise HTTPException(status_code=404, detail="Device not found")
    if current_user and device_raw.owner_id and device_raw.owner_id != current_user.user_id:
        if not current_user.has_role(settings.AUTH_OPERATOR_ROLE):
            raise HTTPException(status_code=403, detail="Not authorized to update this device")
    updated = await service.update_device(device_id, device_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Device not found")
    emit_audit_event(
        service="device-service",
        action="device.updated",
        resource_type="device",
        resource_id=str(device_id),
        tenant_id=updated.tenant_id,
        actor_user_id=current_user.user_id if current_user else None,
        actor_tenant_id=current_user.tenant_id if current_user else None,
        actor_roles=current_user.roles if current_user else [],
    )
    return updated


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete device."""
    service = DeviceService(db)
    device_raw = await service.get_device_raw(device_id)
    if not device_raw:
        raise HTTPException(status_code=404, detail="Device not found")
    if current_user and device_raw.owner_id and device_raw.owner_id != current_user.user_id:
        if not current_user.has_role(settings.AUTH_OPERATOR_ROLE):
            raise HTTPException(status_code=403, detail="Not authorized to delete this device")
    success = await service.delete_device(device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    emit_audit_event(
        service="device-service",
        action="device.deleted",
        resource_type="device",
        resource_id=str(device_id),
        tenant_id=device_raw.tenant_id,
        actor_user_id=current_user.user_id if current_user else None,
        actor_tenant_id=current_user.tenant_id if current_user else None,
        actor_roles=current_user.roles if current_user else [],
    )


# ---------------------------------------------------------------------------
# Agent endpoints (IoTronic-parity: board registration & Lightning-Rod lifecycle)
# ---------------------------------------------------------------------------


@router.post("/agents/register", response_model=AgentStatusResponse, status_code=201)
@limiter.limit("10/minute")
async def agent_register(
    request: Request,
    body: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
    x_bootstrap_token: str = Header(...),
):
    """Register an agent (or re-register an existing device)."""
    _validate_bootstrap_token(x_bootstrap_token)
    service = DeviceService(db)
    result = await service.register_agent(body)
    emit_audit_event(
        service="device-service",
        action="agent.registered",
        resource_type="device",
        resource_id=str(result.device_id),
        tenant_id=getattr(result, "tenant_id", None),
        actor_user_id="agent-bootstrap",
        actor_tenant_id=getattr(result, "tenant_id", None),
        actor_roles=["agent"],
        correlation_id=request.headers.get("x-correlation-id"),
    )
    return result


@router.post(
    "/agents/{device_id}/heartbeat",
    response_model=AgentStatusResponse,
)
@limiter.limit("30/minute", key_func=key_by_device_id)
async def agent_heartbeat(
    request: Request,
    device_id: UUID,
    body: AgentHeartbeatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Accept a heartbeat from an agent."""
    service = DeviceService(db)
    result = await service.heartbeat_agent(device_id, body)
    if not result:
        raise HTTPException(status_code=404, detail="Device not found")
    return result


@router.post("/devices/{device_id}/runtime-config", status_code=200)
async def set_device_runtime_config(
    device_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Set runtime env vars for the FaaS nexora-function-runtime on this device.

    Values are stored server-side only — never included in dispatch payloads.
    The edge agent reads this config at bootstrap and applies it to the runtime process.
    """
    service = DeviceService(db)
    device = await service.get_device_raw(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    import json as _json
    device.meta = device.meta or {}
    if isinstance(device.meta, str):
        try:
            device.meta = _json.loads(device.meta)
        except Exception:
            device.meta = {}
    device.meta["runtime_config"] = payload
    from device_service.core.database import get_db as _get_db
    await db.commit()
    await db.refresh(device)
    return {"device_id": str(device_id), "runtime_config": payload}
