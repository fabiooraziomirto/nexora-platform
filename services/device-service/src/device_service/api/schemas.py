from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


class DeviceBase(BaseModel):
    """Base device schema."""
    name: str = Field(..., min_length=1, max_length=255)
    device_type: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    metadata: Optional[dict] = None
    tags: Optional[list[str]] = None


class DeviceCreate(DeviceBase):
    """Schema for device creation."""
    pass


class DeviceUpdate(BaseModel):
    """Schema for device update."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    device_type: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    metadata: Optional[dict] = None
    tags: Optional[list[str]] = None


class DeviceResponse(DeviceBase):
    """Schema for device response."""
    id: UUID
    status: str
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Ownership fields (present when caller has access)
    owner_id: Optional[str] = None
    tenant_id: Optional[str] = None
    privacy_level: int = 0

    model_config = ConfigDict(from_attributes=True)


class DeviceListResponse(BaseModel):
    """Schema for device list response."""
    items: list[DeviceResponse]
    total: int
    page: int
    page_size: int


class AgentRegisterRequest(BaseModel):
    """Schema for agent registration (IoTronic board registration parity)."""
    device_id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=255)
    device_type: str = Field(..., min_length=1, max_length=100)
    metadata: Optional[dict] = None


class AgentHeartbeatRequest(BaseModel):
    """Schema for agent heartbeat (Lightning-Rod connection lifecycle parity)."""
    status: Optional[str] = Field(default="online", min_length=1, max_length=50)
    telemetry: Optional[dict] = None


class AgentStatusResponse(BaseModel):
    """Response returned after agent register / heartbeat."""
    device_id: UUID
    status: str
    last_seen: datetime

