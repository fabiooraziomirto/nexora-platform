import time
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from device_service.core.config import settings
from device_service.core.database import get_db
from device_service.core.auth import CurrentUser, get_current_user
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
    return {tid.strip() for tid in raw.split(",") if tid.strip()}


def _validate_bootstrap_token(header_value: str) -> None:
    """Validate an ``id:secret`` bootstrap token or raise HTTPException."""
    if ":" not in header_value:
        raise HTTPException(status_code=401, detail="Invalid bootstrap token format")

    tid, secret = header_value.split(":", 1)
    revoked = _get_revoked_token_ids()
    if tid in revoked:
        raise HTTPException(status_code=403, detail="Bootstrap token revoked")

    known = _parse_bootstrap_tokens(settings.AGENT_BOOTSTRAP_TOKENS)
    if tid not in known or known[tid][0] != secret:
        raise HTTPException(status_code=401, detail="Invalid bootstrap token")

    if known[tid][1] < int(time.time()):
        raise HTTPException(status_code=401, detail="Bootstrap token expired")


@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: str | None = None,
    device_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """List devices. Operators see all devices; owners see only their tenant's devices."""
    service = DeviceService(db)
    # Operators get an unfiltered view (topology only — no sensitive payload)
    tenant_filter = None if user.is_operator else user.tenant_id
    return await service.list_devices(
        page=page,
        page_size=page_size,
        status=status,
        device_type=device_type,
        tenant_id=tenant_filter,
    )


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get device by ID. Access depends on caller's privacy level with the device."""
    service = DeviceService(db)
    device = await service.get_device_raw(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Tenant isolation: non-operators can only see devices in their tenant
    if not user.is_operator and device.tenant_id and device.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Device not found")

    return service._to_response(device)


@router.post("/devices", response_model=DeviceResponse, status_code=201)
async def create_device(
    device_data: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Create a new device. Sets owner_id and tenant_id from the caller's identity."""
    service = DeviceService(db)
    return await service.create_device(
        device_data,
        owner_id=user.user_id,
        tenant_id=user.tenant_id,
    )


@router.patch("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    device_data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Update device. Requires ownership or operator role."""
    service = DeviceService(db)
    device = await service.get_device_raw(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if not user.is_operator and device.owner_id and device.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not the device owner")

    updated = await service.update_device(device_id, device_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Device not found")
    return updated


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Delete device. Requires ownership or operator role."""
    service = DeviceService(db)
    device = await service.get_device_raw(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if not user.is_operator and device.owner_id and device.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not the device owner")

    success = await service.delete_device(device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")


# ---------------------------------------------------------------------------
# Agent endpoints (IoTronic-parity: board registration & Lightning-Rod lifecycle)
# ---------------------------------------------------------------------------


@router.post("/agents/register", response_model=AgentStatusResponse, status_code=201)
async def agent_register(
    body: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
    x_bootstrap_token: str = Header(...),
):
    """Register an agent (or re-register an existing device)."""
    _validate_bootstrap_token(x_bootstrap_token)
    service = DeviceService(db)
    return await service.register_agent(body)


@router.post(
    "/agents/{device_id}/heartbeat",
    response_model=AgentStatusResponse,
)
async def agent_heartbeat(
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
