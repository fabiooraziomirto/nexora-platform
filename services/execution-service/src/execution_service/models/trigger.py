from sqlalchemy import Boolean, Column, DateTime, String, Text

from execution_service.core.database import Base


class FunctionTrigger(Base):
    __tablename__ = "function_triggers"

    id = Column(String(36), primary_key=True, index=True)
    # Kafka event type that fires this trigger
    # e.g. "device.registered", "execution.failed", "execution.succeeded"
    event_type = Column(String(100), nullable=False, index=True)
    # plugin_id in plugin-service (the function to invoke)
    function_id = Column(String(36), nullable=False, index=True)
    # "same_device" → use device_id from the event payload
    # "device" → use target_id
    # "fleet" → expand to all members of target_id fleet
    target_type = Column(String(20), nullable=False, default="same_device")
    target_id = Column(String(36), nullable=True)
    # Optional JSON dict: {"exit_code": 1} — trigger fires only when payload matches
    filter_expr = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    tenant_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, nullable=True)
