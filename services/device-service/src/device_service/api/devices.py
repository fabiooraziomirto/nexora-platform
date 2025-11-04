from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from device_service.core.database import get_db
from device_service.api.schemas import (
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    DeviceListResponse,
)
from device_service.models.device import Device
from device_service.services.device_service import DeviceService

logger = structlog.get_logger()
router = APIRouter()


@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: str | None = None,
    device_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List devices with pagination and filtering."""
    service = DeviceService(db)
    return await service.list_devices(
        page=page,
        page_size=page_size,
        status=status,
        device_type=device_type,
    )


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get device by ID."""
    service = DeviceService(db)
    device = await service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/devices", response_model=DeviceResponse, status_code=201)
async def create_device(
    device_data: DeviceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new device."""
    service = DeviceService(db)
    return await service.create_device(device_data)


@router.patch("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    device_data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update device."""
    service = DeviceService(db)
    device = await service.update_device(device_id, device_data)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete device."""
    service = DeviceService(db)
    success = await service.delete_device(device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")

