from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, Boolean, Text, Index
from sqlalchemy.dialects.mysql import CHAR
from device_service.core.database import Base


class DeviceSLO(Base):
    """Service Level Objective definition for a device metric.

    An SLO asserts that `metric <operator> threshold` must hold for each incoming
    telemetry sample.  When a sample violates the assertion a SLOViolation row is
    written and a Kafka event is published.

    operator values: lt, lte, gt, gte, eq
    """

    __tablename__ = "device_slos"

    id = Column(CHAR(36), primary_key=True)
    device_id = Column(CHAR(36), nullable=False, index=True)
    metric = Column(String(128), nullable=False)
    operator = Column(String(8), nullable=False)   # lt | lte | gt | gte | eq
    threshold = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_slo_device_metric", "device_id", "metric"),
    )


class SLOViolation(Base):
    """Recorded breach of a DeviceSLO."""

    __tablename__ = "slo_violations"

    id = Column(CHAR(36), primary_key=True)
    slo_id = Column(CHAR(36), nullable=False, index=True)
    device_id = Column(CHAR(36), nullable=False, index=True)
    metric = Column(String(128), nullable=False)
    observed_value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    operator = Column(String(8), nullable=False)
    violated_at = Column(DateTime, nullable=False, index=True)
