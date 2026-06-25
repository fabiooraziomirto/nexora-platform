"""
Privacy consent management endpoints for device-service.

An owner can grant access to their device data at specific privacy levels (1-3)
to other users, roles, or tenants. Consent is revocable at any time with
immediate effect (GDPR Art. 7 withdrawal of consent).

Level 4 (full payload) is intentionally not delegatable through this API —
it is accessible only by the device owner directly.
"""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from device_service.core.database import get_db
from device_service.core.auth import CurrentUser, get_current_user
from device_service.models.device import Device
from device_service.models.device_consent import DeviceConsent
from device_service.models.ownership_event import OwnershipEvent

logger = structlog.get_logger()
router = APIRouter()

DELEGATABLE_LEVELS = {1, 2, 3}
LEVEL_DESCRIPTIONS = {
    0: "Operational (always active — device online/offline, last heartbeat)",
    1: "Fleet visibility (name, type, zone, aggregate status)",
    2: "Health metrics (uptime, command success rate, delivery failures)",
    3: "Command history (action, status, timestamp — no payload)",
    4: "Full payload (command content and responses — owner only, not delegatable)",
}


class ConsentGrantRequest(BaseModel):
    granted_to: str = Field(..., description="user_id, role name, or tenant_id")
    granted_to_type: str = Field(..., pattern="^(user|role|tenant)$")
    level: int = Field(..., ge=1, le=3, description="Privacy level to grant (1-3; level 4 is owner-only)")


class ConsentResponse(BaseModel):
    consent_id: str
    device_id: str
    granted_to: str
    granted_to_type: str
    level: int
    level_description: str
    granted_at: datetime
    is_active: bool


class PrivacySummary(BaseModel):
    device_id: str
    owner_id: str | None
    privacy_level: int
    active_consents: list[ConsentResponse]


class OwnershipEventResponse(BaseModel):
    event_id: str
    action: str
    actor_id: str
    details: dict | None
    created_at: datetime


async def _require_owner(device_id: str, user: CurrentUser, db: AsyncSession) -> Device:
    """Load device and verify caller is the owner (or raise 403)."""
    q = select(Device).where(Device.id == device_id)
    result = await db.execute(q)
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if not user.is_operator and device.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Only the device owner can manage privacy settings")
    return device


@router.get("/devices/{device_id}/privacy", response_model=PrivacySummary)
async def get_privacy(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get current privacy configuration for a device."""
    device = await _require_owner(device_id, user, db)

    q = select(DeviceConsent).where(
        and_(DeviceConsent.device_id == device_id, DeviceConsent.is_active == True)
    )
    result = await db.execute(q)
    consents = result.scalars().all()

    return PrivacySummary(
        device_id=device_id,
        owner_id=device.owner_id,
        privacy_level=device.privacy_level,
        active_consents=[
            ConsentResponse(
                consent_id=c.id,
                device_id=c.device_id,
                granted_to=c.granted_to,
                granted_to_type=c.granted_to_type,
                level=c.level,
                level_description=LEVEL_DESCRIPTIONS.get(c.level, ""),
                granted_at=c.granted_at,
                is_active=c.is_active,
            )
            for c in consents
        ],
    )


@router.post("/devices/{device_id}/privacy/consent", response_model=ConsentResponse, status_code=201)
async def grant_consent(
    device_id: str,
    body: ConsentGrantRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Grant access to device data at a specific privacy level.
    Only levels 1-3 are delegatable; level 4 is always owner-only.
    """
    device = await _require_owner(device_id, user, db)

    if body.level not in DELEGATABLE_LEVELS:
        raise HTTPException(status_code=400, detail="Level 4 is owner-only and cannot be delegated")

    # Prevent duplicate active consent for same target+level
    dup_q = select(DeviceConsent).where(
        and_(
            DeviceConsent.device_id == device_id,
            DeviceConsent.granted_to == body.granted_to,
            DeviceConsent.granted_to_type == body.granted_to_type,
            DeviceConsent.level == body.level,
            DeviceConsent.is_active == True,
        )
    )
    existing = await db.execute(dup_q)
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Active consent already exists for this target and level")

    now = datetime.now(timezone.utc)
    consent = DeviceConsent(
        id=str(uuid4()),
        device_id=device_id,
        granted_by=user.user_id,
        granted_to=body.granted_to,
        granted_to_type=body.granted_to_type,
        level=body.level,
        granted_at=now,
        is_active=True,
    )
    db.add(consent)

    event = OwnershipEvent(
        id=str(uuid4()),
        device_id=device_id,
        actor_id=user.user_id,
        action="consent_granted",
        details={
            "granted_to": body.granted_to,
            "granted_to_type": body.granted_to_type,
            "level": body.level,
        },
        created_at=now,
    )
    db.add(event)
    await db.commit()

    logger.info(
        "Consent granted",
        device_id=device_id,
        granted_to=body.granted_to,
        level=body.level,
    )

    return ConsentResponse(
        consent_id=consent.id,
        device_id=device_id,
        granted_to=consent.granted_to,
        granted_to_type=consent.granted_to_type,
        level=consent.level,
        level_description=LEVEL_DESCRIPTIONS.get(consent.level, ""),
        granted_at=consent.granted_at,
        is_active=True,
    )


@router.delete("/devices/{device_id}/privacy/consent/{consent_id}", status_code=204)
async def revoke_consent(
    device_id: str,
    consent_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Revoke a previously granted consent. Effect is immediate — the access layer
    reads is_active at query time; no TTL, no grace period (GDPR Art. 7).
    """
    await _require_owner(device_id, user, db)

    q = select(DeviceConsent).where(
        and_(DeviceConsent.id == consent_id, DeviceConsent.device_id == device_id)
    )
    result = await db.execute(q)
    consent = result.scalar_one_or_none()

    if not consent:
        raise HTTPException(status_code=404, detail="Consent not found")
    if not consent.is_active:
        raise HTTPException(status_code=409, detail="Consent already revoked")

    now = datetime.now(timezone.utc)
    consent.is_active = False
    consent.revoked_at = now

    event = OwnershipEvent(
        id=str(uuid4()),
        device_id=device_id,
        actor_id=user.user_id,
        action="consent_revoked",
        details={"consent_id": consent_id, "level": consent.level, "granted_to": consent.granted_to},
        created_at=now,
    )
    db.add(event)
    await db.commit()

    logger.info("Consent revoked", consent_id=consent_id, device_id=device_id)


@router.get("/devices/{device_id}/privacy/events", response_model=list[OwnershipEventResponse])
async def get_ownership_events(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Return the full audit trail for a device's ownership and consent events.
    GDPR Art. 15 (right of access) — owner can see all actions taken on their device.
    """
    await _require_owner(device_id, user, db)

    q = select(OwnershipEvent).where(
        OwnershipEvent.device_id == device_id
    ).order_by(OwnershipEvent.created_at.desc())
    result = await db.execute(q)
    events = result.scalars().all()

    return [
        OwnershipEventResponse(
            event_id=e.id,
            action=e.action,
            actor_id=e.actor_id,
            details=e.details,
            created_at=e.created_at,
        )
        for e in events
    ]
