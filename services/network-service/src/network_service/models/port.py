from sqlalchemy import Column, String

from network_service.core.database import Base


class Port(Base):
    __tablename__ = "ports"

    id = Column(String(36), primary_key=True, index=True)
    device_id = Column(String(64), nullable=True, index=True)
    network_id = Column(String(64), nullable=True, index=True)
    status = Column(String(64), nullable=False, default="created")
