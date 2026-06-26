from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, Text, Index
from sqlalchemy.dialects.mysql import CHAR
from device_service.core.database import Base


class DeviceTelemetry(Base):
    """Time-series telemetry readings from edge devices.

    Each row is one metric sample: (device_id, metric, value, ts).
    Tags are an optional JSON dict for dimensions like unit, sensor_id, etc.
    Designed for append-only ingest; rows are never updated.
    """

    __tablename__ = "device_telemetry"

    id = Column(CHAR(36), primary_key=True)
    device_id = Column(CHAR(36), nullable=False, index=True)
    metric = Column(String(128), nullable=False)
    value = Column(Float, nullable=False)
    ts = Column(DateTime, nullable=False, index=True)
    tags = Column(Text, nullable=True)  # JSON dict

    __table_args__ = (
        Index("ix_telemetry_device_metric_ts", "device_id", "metric", "ts"),
    )
