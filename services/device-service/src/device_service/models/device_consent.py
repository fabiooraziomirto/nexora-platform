from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Index
from sqlalchemy.dialects.mysql import CHAR
from device_service.core.database import Base


class DeviceConsent(Base):
    """
    Records an owner's explicit consent to share device data at a given privacy level
    with a specific actor. Revocable at any time with immediate effect.

    Privacy levels:
      1 — Fleet visibility (name, type, zone, aggregate status)
      2 — Health metrics (uptime, command success rate, delivery failures)
      3 — Command history (action, status, timestamp — no payload)
      4 — Full payload (command content and responses; not delegatable)
    """

    __tablename__ = "device_consents"

    id = Column(CHAR(36), primary_key=True, index=True)

    device_id = Column(CHAR(36), nullable=False, index=True)

    granted_by = Column(CHAR(36), nullable=False)          # owner_id
    granted_to = Column(String(255), nullable=False)        # user_id, role name, or tenant_id
    granted_to_type = Column(String(20), nullable=False)    # "user" | "role" | "tenant"

    level = Column(Integer, nullable=False)                 # 1–3 (level 4 is owner-only, not delegatable)

    granted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    __table_args__ = (
        Index("idx_consent_device_active", "device_id", "is_active"),
        Index("idx_consent_granted_to", "granted_to", "granted_to_type", "is_active"),
    )

    def __repr__(self):
        return (
            f"<DeviceConsent(device={self.device_id}, level={self.level}, "
            f"to={self.granted_to_type}:{self.granted_to}, active={self.is_active})>"
        )
