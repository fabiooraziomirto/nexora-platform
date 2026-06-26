from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text
from sqlalchemy.dialects.mysql import CHAR
from device_service.core.database import Base


class DeviceShadow(Base):
    """Device shadow: desired vs reported state with delta tracking.

    desired  — cloud-set intent; what the operator wants the device to be/do.
    reported — last state self-reported by the edge agent via heartbeat or shadow endpoint.
    delta    — auto-computed JSON of keys where desired != reported (stored for fast reads).
    version  — monotonically incrementing counter; bumped on every desired or reported write.
    """

    __tablename__ = "device_shadows"

    device_id = Column(CHAR(36), primary_key=True, index=True)
    desired = Column(Text, nullable=True)    # JSON
    reported = Column(Text, nullable=True)   # JSON
    delta = Column(Text, nullable=True)      # JSON — keys differing between desired and reported
    version = Column(Integer, nullable=False, default=1)
    desired_at = Column(DateTime, nullable=True)
    reported_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
