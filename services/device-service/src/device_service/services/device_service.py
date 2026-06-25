from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import structlog

from device_service.models.device import Device
from device_service.api.schemas import (
    AgentHeartbeatRequest,
    AgentRegisterRequest,
    AgentStatusResponse,
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    DeviceListResponse,
)
from device_service.core.events import event_bus

logger = structlog.get_logger()


class DeviceService:
    """Service for device management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _to_response(device: Device) -> DeviceResponse:
        import json as _json
        caps = None
        if device.capabilities:
            try:
                caps = _json.loads(device.capabilities)
            except (ValueError, TypeError):
                caps = None
        return DeviceResponse(
            id=device.id,
            name=device.name,
            device_type=device.device_type,
            description=device.description,
            metadata=device.meta,
            tags=device.tags,
            status=device.status,
            last_seen=device.last_seen,
            created_at=device.created_at,
            updated_at=device.updated_at,
            owner_id=device.owner_id,
            tenant_id=device.tenant_id,
            privacy_level=device.privacy_level,
            capabilities=caps,
        )

    async def list_devices(
        self,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        device_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> DeviceListResponse:
        """List devices with pagination and filtering."""
        query = select(Device)
        count_query = select(func.count()).select_from(Device)

        # Apply filters
        conditions = []
        if status:
            conditions.append(Device.status == status)
        if device_type:
            conditions.append(Device.device_type == device_type)
        if tenant_id:
            conditions.append(Device.tenant_id == tenant_id)
        if owner_id:
            conditions.append(Device.owner_id == owner_id)
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(Device.created_at.desc())
        
        # Execute query
        result = await self.db.execute(query)
        devices = result.scalars().all()
        
        return DeviceListResponse(
            items=[self._to_response(d) for d in devices],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def get_device_raw(self, device_id: UUID) -> Optional[Device]:
        """Return the raw Device ORM object (for ownership checks in route handlers)."""
        query = select(Device).where(Device.id == str(device_id))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_device(self, device_id: UUID) -> Optional[DeviceResponse]:
        """Get device by ID."""
        device = await self.get_device_raw(device_id)
        if device:
            return self._to_response(device)
        return None
    
    async def create_device(
        self,
        device_data: DeviceCreate,
        owner_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> DeviceResponse:
        """Create a new device."""
        device = Device(
            id=str(uuid4()),
            name=device_data.name,
            device_type=device_data.device_type,
            description=device_data.description,
            meta=device_data.metadata,
            tags=device_data.tags,
            status="offline",
            owner_id=owner_id,
            tenant_id=tenant_id,
        )
        
        self.db.add(device)
        await self.db.commit()
        await self.db.refresh(device)
        
        logger.info("Device created", device_id=device.id, name=device.name)
        
        # Publish event
        await event_bus.publish(
            "device.created",
            {
                "device_id": device.id,
                "name": device.name,
                "device_type": device.device_type,
            }
        )
        
        return self._to_response(device)
    
    async def update_device(
        self,
        device_id: UUID,
        device_data: DeviceUpdate,
    ) -> Optional[DeviceResponse]:
        """Update device."""
        query = select(Device).where(Device.id == str(device_id))
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()
        
        if not device:
            return None
        
        # Update fields
        update_data = device_data.model_dump(exclude_unset=True)
        if "metadata" in update_data:
            update_data["meta"] = update_data.pop("metadata")
        for field, value in update_data.items():
            setattr(device, field, value)
        
        await self.db.commit()
        await self.db.refresh(device)
        
        logger.info("Device updated", device_id=device.id)
        
        # Publish event
        await event_bus.publish(
            "device.updated",
            {
                "device_id": device.id,
                "changes": update_data,
            }
        )
        
        return self._to_response(device)
    
    async def delete_device(self, device_id: UUID) -> bool:
        """Delete device."""
        query = select(Device).where(Device.id == str(device_id))
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()
        
        if not device:
            return False
        
        device_id_str = device.id
        await self.db.delete(device)
        await self.db.commit()
        
        logger.info("Device deleted", device_id=device_id_str)
        
        # Publish event
        await event_bus.publish(
            "device.deleted",
            {
                "device_id": device_id_str,
            }
        )
        
        return True

    # ------------------------------------------------------------------
    # Agent lifecycle (IoTronic-parity)
    # ------------------------------------------------------------------

    async def register_agent(self, data: AgentRegisterRequest) -> AgentStatusResponse:
        """Register or re-register an agent device."""
        now = datetime.now(timezone.utc)

        if data.device_id:
            query = select(Device).where(Device.id == str(data.device_id))
            result = await self.db.execute(query)
            device = result.scalar_one_or_none()
        else:
            device = None

        import json as _json
        capabilities_json = _json.dumps(data.capabilities) if data.capabilities else None

        if device:
            device.name = data.name
            device.device_type = data.device_type
            if data.metadata is not None:
                device.meta = data.metadata
            if data.capabilities is not None:
                device.capabilities = capabilities_json
            device.status = "online"
            device.last_seen = now
        else:
            device = Device(
                id=str(data.device_id) if data.device_id else str(uuid4()),
                name=data.name,
                device_type=data.device_type,
                meta=data.metadata,
                capabilities=capabilities_json,
                status="online",
                last_seen=now,
            )
            self.db.add(device)

        await self.db.commit()
        await self.db.refresh(device)

        logger.info("Agent registered", device_id=device.id, name=device.name)

        await event_bus.publish(
            "agent.registered",
            {"device_id": device.id, "name": device.name},
        )

        return AgentStatusResponse(
            device_id=UUID(device.id),
            status=device.status,
            last_seen=device.last_seen,
        )

    async def heartbeat_agent(
        self, device_id: UUID, data: AgentHeartbeatRequest
    ) -> Optional[AgentStatusResponse]:
        """Process an agent heartbeat."""
        query = select(Device).where(Device.id == str(device_id))
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()

        if not device:
            return None

        import json as _json
        now = datetime.now(timezone.utc)
        device.last_seen = now
        device.status = data.status or "online"
        if data.capabilities is not None:
            device.capabilities = _json.dumps(data.capabilities)

        await self.db.commit()
        await self.db.refresh(device)

        logger.info("Agent heartbeat", device_id=device.id)

        return AgentStatusResponse(
            device_id=UUID(device.id),
            status=device.status,
            last_seen=device.last_seen,
        )

