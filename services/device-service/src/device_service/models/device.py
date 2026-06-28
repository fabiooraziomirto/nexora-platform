from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, JSON, Index, Integer
from sqlalchemy.dialects.mysql import CHAR
from device_service.core.database import Base

# Valid values for connection_protocol
PROTOCOL_NEXORA_AGENT = "nexora-agent"  # WebSocket via nexora-edge (default)
PROTOCOL_MATTER = "matter"
PROTOCOL_MQTT = "mqtt"
PROTOCOL_ZIGBEE = "zigbee"
PROTOCOL_HTTP_POLL = "http-poll"


class Device(Base):
    """Device model."""

    __tablename__ = "devices"

    # Primary key (UUID as CHAR(36) for MySQL compatibility)
    id = Column(CHAR(36), primary_key=True, index=True)

    # Device identification
    name = Column(String(255), nullable=False, index=True)
    device_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Ownership — physical owner (Keycloak sub) and tenant (Keycloak group)
    owner_id = Column(CHAR(36), nullable=True, index=True)
    tenant_id = Column(String(255), nullable=True, index=True)

    # Privacy level configured by owner (0=operational only, 1-4=opt-in tiers)
    privacy_level = Column(Integer, nullable=False, default=0)

    # Status
    status = Column(String(50), nullable=False, default="offline", index=True)
    last_seen = Column(DateTime, nullable=True, index=True)

    # FaaS capabilities reported by edge agent at register/heartbeat
    # JSON: {"wasm_wasi": true, "arch": "arm64", "agent_version": "1.0", "available_memory_mb": 256, "supported_runtimes": ["wasm-wasi"]}
    capabilities = Column(Text, nullable=True)

    # Runtime env vars for FaaS secrets; pre-configured by operator, NOT included in dispatch payloads.
    # JSON: {"VAR_NAME": "value"} — applied by edge agent to nexora-function-runtime at bootstrap.
    runtime_env = Column(Text, nullable=True)

    # Protocol of the physical connection to this device.
    # "nexora-agent" (default): device runs nexora-edge agent over WebSocket.
    # "matter": device is commissioned into the Nexora Matter fabric via matter-bridge.
    # "mqtt", "zigbee", "http-poll": reserved for future bridge services.
    connection_protocol = Column(String(50), nullable=False, default=PROTOCOL_NEXORA_AGENT, index=True)

    # Protocol-specific metadata (JSON). For Matter: fabric_id, node_id, endpoints, clusters.
    # For MQTT: broker_url, topic_prefix. Populated by bridge services, not by the device itself.
    protocol_meta = Column(JSON, nullable=True)

    # Metadata
    meta = Column("metadata", JSON, nullable=True)
    tags = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_device_status_updated", "status", "updated_at"),
        Index("idx_device_name_type", "name", "device_type"),
        Index("idx_device_owner_tenant", "owner_id", "tenant_id"),
        Index("idx_device_protocol", "connection_protocol"),
    )

    
    def __repr__(self):
        return f"<Device(id={self.id}, name={self.name}, status={self.status})>"

