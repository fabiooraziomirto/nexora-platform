from sqlalchemy import Column, String

from fleet_service.core.database import Base


class Fleet(Base):
    __tablename__ = "fleets"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1024), nullable=True)
    owner_id = Column(String(64), nullable=True, index=True)
    tenant_id = Column(String(255), nullable=True, index=True)
