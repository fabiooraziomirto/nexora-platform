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
from device_service.core.metrics import (
    device_operations,
    device_operation_duration,
    active_devices,
    device_provisioning_seconds,
    device_registrations_total,
    device_heartbeats_total,
)

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
        
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(Device.created_at.desc())
        
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
        import time as _time
        t0 = _time.monotonic()
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

        device_operations.labels(operation="create", status="ok").inc()
        device_operation_duration.labels(operation="create").observe(_time.monotonic() - t0)

        logger.info("Device created", device_id=device.id, name=device.name)

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
        
        update_data = device_data.model_dump(exclude_unset=True)
        if "metadata" in update_data:
            update_data["meta"] = update_data.pop("metadata")
        for field, value in update_data.items():
            setattr(device, field, value)
        
        await self.db.commit()
        await self.db.refresh(device)
        
        logger.info("Device updated", device_id=device.id)
        
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
            device_operations.labels(operation="delete", status="not_found").inc()
            return False

        was_online = device.status == "online"
        device_id_str = device.id
        await self.db.delete(device)
        await self.db.commit()

        device_operations.labels(operation="delete", status="ok").inc()
        if was_online:
            active_devices.dec()

        logger.info("Device deleted", device_id=device_id_str)

        await event_bus.publish("device.deleted", {"device_id": device_id_str})

        return True

    # ------------------------------------------------------------------
    # Agent lifecycle (IoTronic-parity)
    # ------------------------------------------------------------------

    async def register_agent(self, data: AgentRegisterRequest) -> AgentStatusResponse:
        """Register or re-register an agent device."""
        import json as _json
        import time as _time

        t0 = _time.monotonic()
        now = datetime.now(timezone.utc)
        is_new = True

        if data.device_id:
            query = select(Device).where(Device.id == str(data.device_id))
            result = await self.db.execute(query)
            device = result.scalar_one_or_none()
        else:
            device = None

        capabilities_json = _json.dumps(data.capabilities) if data.capabilities else None

        if device:
            is_new = False
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

        reg_type = "new" if is_new else "re_register"
        device_registrations_total.labels(registration_type=reg_type).inc()
        device_operations.labels(operation="register", status="ok").inc()
        device_operation_duration.labels(operation="register").observe(_time.monotonic() - t0)
        if is_new:
            active_devices.inc()

        logger.info("Agent registered", device_id=device.id, name=device.name, type=reg_type)

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
        import json as _json

        query = select(Device).where(Device.id == str(device_id))
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()

        if not device:
            device_heartbeats_total.labels(status="not_found").inc()
            return None

        now = datetime.now(timezone.utc)
        is_first_heartbeat = device.last_seen is None

        device.last_seen = now
        device.status = data.status or "online"
        if data.capabilities is not None:
            device.capabilities = _json.dumps(data.capabilities)

        await self.db.commit()
        await self.db.refresh(device)

        device_heartbeats_total.labels(status="ok").inc()
        device_operations.labels(operation="heartbeat", status="ok").inc()

        # Provisioning time: first heartbeat after registration
        if is_first_heartbeat and device.created_at:
            provisioning_s = (now - device.created_at.replace(tzinfo=timezone.utc)).total_seconds()
            if provisioning_s >= 0:
                device_provisioning_seconds.observe(provisioning_s)

        logger.info("Agent heartbeat", device_id=device.id)

        return AgentStatusResponse(
            device_id=UUID(device.id),
            status=device.status,
            last_seen=device.last_seen,
        )
