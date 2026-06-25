from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Index
from sqlalchemy.dialects.mysql import CHAR
from device_service.core.database import Base


class OwnershipEvent(Base):
    """
    Immutable audit log for all ownership and consent lifecycle events.
    Queryable by the device owner (GDPR accountability, Art. 7 / Art. 15).
    Actions: paired | unpaired | consent_granted | consent_revoked | level_changed | ownership_transferred
    """

    __tablename__ = "ownership_events"

    id = Column(CHAR(36), primary_key=True, index=True)
    device_id = Column(CHAR(36), nullable=False, index=True)
    actor_id = Column(CHAR(36), nullable=False)     # who performed the action
    action = Column(String(50), nullable=False)
    details = Column(JSON, nullable=True)            # action-specific payload
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_ownership_event_device_ts", "device_id", "created_at"),
    )

    def __repr__(self):
        return f"<OwnershipEvent(device={self.device_id}, action={self.action}, actor={self.actor_id})>"
