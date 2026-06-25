from datetime import datetime
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.mysql import CHAR
from device_service.core.database import Base


class DeviceDiscovery(Base):
    """
    Represents a device that has announced itself but not yet been claimed by an owner.
    Implements RFC 8628 device authorization flow: device polls device_code until an
    authenticated owner claims it via user_code on the dashboard.
    """

    __tablename__ = "device_discoveries"

    id = Column(CHAR(36), primary_key=True, index=True)

    # Physical device identity (stable across reboots)
    hardware_id = Column(String(255), nullable=False, index=True)
    device_type = Column(String(100), nullable=False)
    firmware_version = Column(String(50), nullable=True)

    # RFC 8628 codes
    device_code = Column(String(64), nullable=False, unique=True, index=True)  # device polls with this
    user_code = Column(String(16), nullable=False, unique=True, index=True)    # owner enters in browser

    # State machine: announced → pending_approval → approved | rejected | expired
    status = Column(String(30), nullable=False, default="announced", index=True)

    expires_at = Column(DateTime, nullable=False)

    # Filled when owner claims
    claimed_by = Column(CHAR(36), nullable=True)       # owner_id (Keycloak sub)
    claimed_tenant = Column(String(255), nullable=True) # owner's tenant_id
    claimed_at = Column(DateTime, nullable=True)

    # Bootstrap token handed to device after approval (one-time use)
    bootstrap_token_issued = Column(String(255), nullable=True)

    # device_id created after successful claim
    device_id = Column(CHAR(36), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_discovery_status_expires", "status", "expires_at"),
    )

    def __repr__(self):
        return f"<DeviceDiscovery(id={self.id}, hardware_id={self.hardware_id}, status={self.status})>"
