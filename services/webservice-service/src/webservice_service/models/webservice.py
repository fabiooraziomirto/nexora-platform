from sqlalchemy import Column, Integer, String

from webservice_service.core.database import Base


class Webservice(Base):
    __tablename__ = "webservices"

    id = Column(String(36), primary_key=True, index=True)
    device_id = Column(String(64), nullable=True, index=True)
    port = Column(Integer, nullable=False, default=443)
    status = Column(String(64), nullable=False, default="enabled")
