"""
Common event contracts for core CRUD services.
"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


EventAction = Literal["created", "updated", "deleted"]


class ResourceEvent(BaseModel):
    event_type: str = Field(..., description="Topic suffix, e.g. plugin.created")
    service: str = Field(..., description="Source service name")
    resource: str = Field(..., description="Resource type, e.g. plugin/fleet")
    action: EventAction
    resource_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def make_resource_event(
    service: str,
    resource: str,
    action: EventAction,
    resource_id: str,
    payload: dict[str, Any] | None = None,
) -> ResourceEvent:
    return ResourceEvent(
        event_type=f"{resource}.{action}",
        service=service,
        resource=resource,
        action=action,
        resource_id=resource_id,
        payload=payload or {},
    )
