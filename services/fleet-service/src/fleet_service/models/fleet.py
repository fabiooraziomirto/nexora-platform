from sqlalchemy import Column, String

from fleet_service.core.database import Base


class Fleet(Base):
    __tablename__ = "fleets"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1024), nullable=True)
