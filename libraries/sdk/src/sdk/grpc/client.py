"""
gRPC client for Stack4Things.
"""

from typing import Optional, List, Dict, Any
import grpc
from grpc import aio
import httpx

from sdk.types import (
    Device,
    DeviceCreate,
    DeviceUpdate,
    Fleet,
    FleetCreate,
    Execution,
    ExecutionCreate,
)


class Stack4ThingsGRPCClient:
    """gRPC client for Stack4Things services."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 50051,
        credentials: Optional[grpc.ChannelCredentials] = None,
    ):
        self.host = host
        self.port = port
        self.credentials = credentials
        
        # Build channel address
        self.address = f"{host}:{port}"
        
        # Channel will be created on first use
        self._channel: Optional[aio.Channel] = None
        self._stubs: Dict[str, Any] = {}
        self._http_base = f"http://{host.replace('50051', '8000')}" if port == 50051 else f"http://{host}:{port}"

    async def connect(self):
        """Connect to gRPC server."""
        if self._channel is None:
            if self.credentials:
                self._channel = aio.secure_channel(self.address, self.credentials)
            else:
                self._channel = aio.insecure_channel(self.address)
        
        # Initialize stubs here when proto files are available
        # Example:
        # from sdk.grpc import device_pb2_grpc
        # self._stubs['device'] = device_pb2_grpc.DeviceServiceStub(self._channel)

    async def disconnect(self):
        """Disconnect from gRPC server."""
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stubs.clear()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    # Device methods (HTTP fallback until proto stubs are wired)
    async def list_devices(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> List[Device]:
        """List devices via gRPC."""
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self._http_base}/api/v2/devices", params=params)
            r.raise_for_status()
            items = r.json().get("items", [])
            return [Device(**item) for item in items]

    async def get_device(self, device_id: str) -> Device:
        """Get device via gRPC."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self._http_base}/api/v2/devices/{device_id}")
            r.raise_for_status()
            return Device(**r.json())

    async def create_device(self, device: DeviceCreate) -> Device:
        """Create device via gRPC."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{self._http_base}/api/v2/devices", json=device.model_dump())
            r.raise_for_status()
            return Device(**r.json())

    async def update_device(self, device_id: str, device: DeviceUpdate) -> Device:
        """Update device via gRPC."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.patch(f"{self._http_base}/api/v2/devices/{device_id}", json=device.model_dump(exclude_none=True))
            r.raise_for_status()
            return Device(**r.json())

    async def delete_device(self, device_id: str):
        """Delete device via gRPC."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.delete(f"{self._http_base}/api/v2/devices/{device_id}")
            r.raise_for_status()

    # Fleet methods (HTTP fallback until proto stubs are wired)
    async def list_fleets(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Fleet]:
        """List fleets via gRPC."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self._http_base}/api/v2/fleets", params={"page": page, "page_size": page_size})
            r.raise_for_status()
            return [Fleet(**item) for item in r.json().get("items", [])]

    async def get_fleet(self, fleet_id: str) -> Fleet:
        """Get fleet via gRPC."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self._http_base}/api/v2/fleets/{fleet_id}")
            r.raise_for_status()
            return Fleet(**r.json())

    async def create_fleet(self, fleet: FleetCreate) -> Fleet:
        """Create fleet via gRPC."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{self._http_base}/api/v2/fleets", json=fleet.model_dump())
            r.raise_for_status()
            return Fleet(**r.json())

    # Execution methods (HTTP fallback until proto stubs are wired)
    async def create_execution(self, execution: ExecutionCreate) -> Execution:
        """Create execution via gRPC."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{self._http_base}/api/v2/executions", json=execution.model_dump())
            r.raise_for_status()
            return Execution(**r.json())

    async def get_execution(self, execution_id: str) -> Execution:
        """Get execution via gRPC."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self._http_base}/api/v2/executions/{execution_id}")
            r.raise_for_status()
            return Execution(**r.json())

