from sqlalchemy import Column, DateTime, String, UniqueConstraint

from fleet_service.core.database import Base


class FleetMember(Base):
    __tablename__ = "fleet_members"

    id = Column(String(36), primary_key=True, index=True)
    fleet_id = Column(String(36), nullable=False, index=True)
    device_id = Column(String(64), nullable=False, index=True)
    joined_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("fleet_id", "device_id", name="uq_fleet_member"),)
