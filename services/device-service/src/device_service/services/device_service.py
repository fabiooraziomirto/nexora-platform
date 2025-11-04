from uuid import UUID, uuid4
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
import structlog

from device_service.models.device import Device
from device_service.api.schemas import DeviceCreate, DeviceUpdate, DeviceResponse, DeviceListResponse
from device_service.core.events import event_bus

logger = structlog.get_logger()


class DeviceService:
    """Service for device management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def list_devices(
        self,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        device_type: Optional[str] = None,
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
            items=[DeviceResponse.model_validate(d) for d in devices],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def get_device(self, device_id: UUID) -> Optional[DeviceResponse]:
        """Get device by ID."""
        query = select(Device).where(Device.id == str(device_id))
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()
        if device:
            return DeviceResponse.model_validate(device)
        return None
    
    async def create_device(self, device_data: DeviceCreate) -> DeviceResponse:
        """Create a new device."""
        device = Device(
            id=str(uuid4()),
            name=device_data.name,
            device_type=device_data.device_type,
            description=device_data.description,
            metadata=device_data.metadata,
            tags=device_data.tags,
            status="offline",
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
        
        return DeviceResponse.model_validate(device)
    
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
        
        return DeviceResponse.model_validate(device)
    
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

