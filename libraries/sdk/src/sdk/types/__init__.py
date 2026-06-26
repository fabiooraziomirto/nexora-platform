"""
Type definitions for Nxr SDK.
"""

from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class DeviceStatus(str, Enum):
    """Device status."""
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class ExecutionStatus(str, Enum):
    """Execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Device(BaseModel):
    """Device model."""
    id: str = Field(..., description="Device ID")
    name: str = Field(..., description="Device name")
    device_type: str = Field(..., description="Device type")
    description: Optional[str] = Field(None, description="Device description")
    status: DeviceStatus = Field(DeviceStatus.OFFLINE, description="Device status")
    last_seen: Optional[datetime] = Field(None, description="Last seen timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Device metadata")
    tags: Optional[List[str]] = Field(None, description="Device tags")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "device-123",
                "name": "Raspberry Pi 4",
                "device_type": "raspberry_pi",
                "status": "online",
                "last_seen": "2024-01-01T00:00:00Z",
            }
        }
    }


class DeviceCreate(BaseModel):
    """Device creation model."""
    name: str = Field(..., description="Device name")
    device_type: str = Field(..., description="Device type")
    description: Optional[str] = Field(None, description="Device description")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Device metadata")
    tags: Optional[List[str]] = Field(None, description="Device tags")


class DeviceUpdate(BaseModel):
    """Device update model."""
    name: Optional[str] = Field(None, description="Device name")
    description: Optional[str] = Field(None, description="Device description")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Device metadata")
    tags: Optional[List[str]] = Field(None, description="Device tags")


class Fleet(BaseModel):
    """Fleet model."""
    id: str = Field(..., description="Fleet ID")
    name: str = Field(..., description="Fleet name")
    description: Optional[str] = Field(None, description="Fleet description")
    device_ids: List[str] = Field(..., description="Device IDs in fleet")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Fleet metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")


class FleetCreate(BaseModel):
    """Fleet creation model."""
    name: str = Field(..., description="Fleet name")
    description: Optional[str] = Field(None, description="Fleet description")
    device_ids: Optional[List[str]] = Field(None, description="Device IDs")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Fleet metadata")


class FleetUpdate(BaseModel):
    """Fleet update model."""
    name: Optional[str] = Field(None, description="Fleet name")
    description: Optional[str] = Field(None, description="Fleet description")
    device_ids: Optional[List[str]] = Field(None, description="Device IDs")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Fleet metadata")


class Network(BaseModel):
    """Network model."""
    id: str = Field(..., description="Network ID")
    name: str = Field(..., description="Network name")
    cidr: str = Field(..., description="Network CIDR")
    gateway: Optional[str] = Field(None, description="Gateway IP")
    dns_servers: Optional[List[str]] = Field(None, description="DNS servers")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Network metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")


class NetworkCreate(BaseModel):
    """Network creation model."""
    name: str = Field(..., description="Network name")
    cidr: str = Field(..., description="Network CIDR")
    gateway: Optional[str] = Field(None, description="Gateway IP")
    dns_servers: Optional[List[str]] = Field(None, description="DNS servers")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Network metadata")


class NetworkUpdate(BaseModel):
    """Network update model."""
    name: Optional[str] = Field(None, description="Network name")
    gateway: Optional[str] = Field(None, description="Gateway IP")
    dns_servers: Optional[List[str]] = Field(None, description="DNS servers")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Network metadata")


class Execution(BaseModel):
    """Execution model."""
    id: str = Field(..., description="Execution ID")
    device_id: str = Field(..., description="Device ID")
    plugin_id: str = Field(..., description="Plugin ID")
    status: ExecutionStatus = Field(ExecutionStatus.PENDING, description="Execution status")
    input: Optional[Dict[str, Any]] = Field(None, description="Execution input")
    output: Optional[Dict[str, Any]] = Field(None, description="Execution output")
    error: Optional[str] = Field(None, description="Error message")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")


class ExecutionCreate(BaseModel):
    """Execution creation model."""
    device_id: str = Field(..., description="Device ID")
    plugin_id: str = Field(..., description="Plugin ID")
    input: Optional[Dict[str, Any]] = Field(None, description="Execution input")


class PaginatedResponse(BaseModel):
    """Paginated response model."""
    items: List[Any] = Field(..., description="Items")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Page number")
    page_size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total pages")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: Dict[str, Any] = Field(..., description="Error details")

