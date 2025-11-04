from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, JSON, Index
from sqlalchemy.dialects.mysql import CHAR, INTEGER
from device_service.core.database import Base


class Device(Base):
    """Device model."""
    
    __tablename__ = "devices"
    
    # Primary key (UUID as CHAR(36) for MySQL compatibility)
    id = Column(CHAR(36), primary_key=True, index=True)
    
    # Device identification
    name = Column(String(255), nullable=False, index=True)
    device_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Status
    status = Column(String(50), nullable=False, default="offline", index=True)
    last_seen = Column(DateTime, nullable=True, index=True)
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for common queries
    __table_args__ = (
        Index("idx_device_status_updated", "status", "updated_at"),
        Index("idx_device_name_type", "name", "device_type"),
    )
    
    def __repr__(self):
        return f"<Device(id={self.id}, name={self.name}, status={self.status})>"

