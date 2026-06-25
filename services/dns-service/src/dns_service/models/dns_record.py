from sqlalchemy import Column, Integer, String

from dns_service.core.database import Base


class DNSRecord(Base):
    __tablename__ = "dns_records"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    type = Column(String(16), nullable=False, default="A")
    value = Column(String(255), nullable=True)
    ttl = Column(Integer, nullable=True, default=300)
