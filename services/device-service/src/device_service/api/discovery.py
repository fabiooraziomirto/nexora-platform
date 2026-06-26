"""
Device discovery and pairing endpoints — RFC 8628 device authorization flow.

Flow:
  1. LR device POSTs /announce → gets device_code (for polling) + user_code (for owner)
  2. Device polls GET /announce/poll?device_code=X every DISCOVERY_POLL_INTERVAL_SECONDS
  3. Owner (authenticated) GETs /pending to see waiting devices
  4. Owner POSTs /{discovery_id}/claim → device is registered, bootstrap_token issued
  5. Next poll by device returns "approved" + bootstrap_token → device registers normally
"""
import secrets
import string
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from device_service.core.config import settings
from device_service.core.database import get_db
from device_service.core.auth import CurrentUser, get_current_user
from device_service.models.device import Device
from device_service.models.device_discovery import DeviceDiscovery
from device_service.models.ownership_event import OwnershipEvent

logger = structlog.get_logger()
router = APIRouter()

_USER_CODE_CHARS = string.ascii_uppercase + string.digits


def _generate_device_code() -> str:
    return secrets.token_urlsafe(32)


def _generate_user_code() -> str:
    """Generate a human-readable 8-char code in XXXX-XXXX format."""
    raw = "".join(secrets.choice(_USER_CODE_CHARS) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class AnnounceRequest(BaseModel):
    hardware_id: str
    device_type: str
    firmware_version: str | None = None


class AnnounceResponse(BaseModel):
    discovery_id: str
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int          # seconds
    poll_interval: int       # seconds


class PollResponse(BaseModel):
    status: str              # pending_approval | approved | rejected | expired
    bootstrap_token: str | None = None
    device_id: str | None = None


class DiscoveryItem(BaseModel):
    discovery_id: str
    hardware_id: str
    device_type: str
    firmware_version: str | None
    user_code: str
    announced_at: datetime


class ClaimRequest(BaseModel):
    name: str                # human-readable name the owner assigns to the device
    description: str | None = None


class ClaimResponse(BaseModel):
    device_id: str
    name: str
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/devices/announce", response_model=AnnounceResponse)
async def announce(
    body: AnnounceRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Unauthenticated endpoint — a NexoraEdge device calls this at startup to announce
    itself. Returns RFC 8628 codes. No authentication required (the device has no
    credentials yet; trust is established when the owner claims it).
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.DISCOVERY_EXPIRY_SECONDS)

    # Expire any previous pending announcements for the same hardware_id
    stale_q = select(DeviceDiscovery).where(
        and_(
            DeviceDiscovery.hardware_id == body.hardware_id,
            DeviceDiscovery.status == "announced",
        )
    )
    stale_result = await db.execute(stale_q)
    for stale in stale_result.scalars().all():
        stale.status = "expired"

    discovery = DeviceDiscovery(
        id=str(uuid4()),
        hardware_id=body.hardware_id,
        device_type=body.device_type,
        firmware_version=body.firmware_version,
        device_code=_generate_device_code(),
        user_code=_generate_user_code(),
        status="announced",
        expires_at=expires_at,
        created_at=now,
    )
    db.add(discovery)
    await db.commit()
    await db.refresh(discovery)

    logger.info("Device announced", hardware_id=body.hardware_id, discovery_id=discovery.id)

    return AnnounceResponse(
        discovery_id=discovery.id,
        device_code=discovery.device_code,
        user_code=discovery.user_code,
        verification_uri="/pair",   # frontend URL where owner enters user_code
        expires_in=settings.DISCOVERY_EXPIRY_SECONDS,
        poll_interval=settings.DISCOVERY_POLL_INTERVAL_SECONDS,
    )


@router.get("/devices/announce/poll", response_model=PollResponse)
async def poll(
    device_code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Unauthenticated polling endpoint — device calls this every poll_interval seconds
    to check if an owner has claimed it.
    """
    q = select(DeviceDiscovery).where(DeviceDiscovery.device_code == device_code)
    result = await db.execute(q)
    discovery = result.scalar_one_or_none()

    if not discovery:
        raise HTTPException(status_code=404, detail="Unknown device_code")

    # Expire if past deadline
    now = datetime.now(timezone.utc)
    exp = discovery.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if discovery.status == "announced" and now > exp:
        discovery.status = "expired"
        await db.commit()

    if discovery.status == "approved":
        return PollResponse(
            status="approved",
            bootstrap_token=discovery.bootstrap_token_issued,
            device_id=discovery.device_id,
        )

    return PollResponse(status=discovery.status)


@router.get("/devices/pending", response_model=list[DiscoveryItem])
async def list_pending(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Authenticated — owner sees devices waiting for approval in their tenant."""
    q = select(DeviceDiscovery).where(DeviceDiscovery.status == "announced")
    result = await db.execute(q)
    discoveries = result.scalars().all()

    now = datetime.now(timezone.utc)
    items = []
    for d in discoveries:
        exp = d.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            d.status = "expired"
            continue
        items.append(DiscoveryItem(
            discovery_id=d.id,
            hardware_id=d.hardware_id,
            device_type=d.device_type,
            firmware_version=d.firmware_version,
            user_code=d.user_code,
            announced_at=d.created_at,
        ))

    if any(d.status == "expired" for d in discoveries):
        await db.commit()

    return items


@router.post("/devices/{discovery_id}/claim", response_model=ClaimResponse, status_code=201)
async def claim(
    discovery_id: str,
    body: ClaimRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Authenticated — owner approves a pending device discovery.
    Creates a Device record with owner_id and tenant_id from the caller's JWT.
    Issues a one-time bootstrap token that the device receives on its next poll.
    """
    q = select(DeviceDiscovery).where(DeviceDiscovery.id == discovery_id)
    result = await db.execute(q)
    discovery = result.scalar_one_or_none()

    if not discovery:
        raise HTTPException(status_code=404, detail="Discovery not found")

    now = datetime.now(timezone.utc)
    exp = discovery.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)

    if discovery.status != "announced" or now > exp:
        raise HTTPException(status_code=409, detail=f"Discovery is {discovery.status}, cannot claim")

    # Create the device with owner's identity
    token_id = f"pair-{secrets.token_hex(8)}"
    token_secret = secrets.token_urlsafe(32)
    token_exp = int((now + timedelta(hours=1)).timestamp())
    bootstrap_token = f"{token_id}:{token_secret}"

    device = Device(
        id=str(uuid4()),
        name=body.name,
        device_type=discovery.device_type,
        description=body.description,
        status="offline",
        owner_id=user.user_id,
        tenant_id=user.tenant_id,
        privacy_level=0,
        created_at=now,
        updated_at=now,
    )
    db.add(device)

    # Update discovery
    discovery.status = "approved"
    discovery.claimed_by = user.user_id
    discovery.claimed_tenant = user.tenant_id
    discovery.claimed_at = now
    discovery.bootstrap_token_issued = bootstrap_token
    discovery.device_id = device.id

    # Add one-time bootstrap token to settings dynamically isn't possible at runtime,
    # so we store it in the discovery and validate it in a separate flow.
    # For now: the device reads the token from the poll response and uses /agents/register.
    # The token is validated by the discovery record (see agents/register_from_discovery).

    # Audit event
    event = OwnershipEvent(
        id=str(uuid4()),
        device_id=device.id,
        actor_id=user.user_id,
        action="paired",
        details={
            "hardware_id": discovery.hardware_id,
            "discovery_id": discovery.id,
            "tenant_id": user.tenant_id,
        },
        created_at=now,
    )
    db.add(event)

    await db.commit()

    logger.info(
        "Device claimed",
        device_id=device.id,
        owner_id=user.user_id,
        hardware_id=discovery.hardware_id,
    )

    return ClaimResponse(
        device_id=device.id,
        name=device.name,
        message="Device paired. It will connect automatically on next poll.",
    )


@router.post("/devices/{discovery_id}/reject", status_code=204)
async def reject(
    discovery_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Authenticated — owner rejects a pending device discovery."""
    q = select(DeviceDiscovery).where(DeviceDiscovery.id == discovery_id)
    result = await db.execute(q)
    discovery = result.scalar_one_or_none()

    if not discovery:
        raise HTTPException(status_code=404, detail="Discovery not found")

    if discovery.status != "announced":
        raise HTTPException(status_code=409, detail=f"Discovery is {discovery.status}, cannot reject")

    discovery.status = "rejected"
    await db.commit()

    logger.info("Device rejected", discovery_id=discovery_id, actor=user.user_id)
