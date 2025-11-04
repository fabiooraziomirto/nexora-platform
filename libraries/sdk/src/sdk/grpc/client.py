"""
gRPC client for Stack4Things.
"""

from typing import Optional, List, Dict, Any
import grpc
from grpc import aio

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

    # Device methods (to be implemented with actual proto stubs)
    async def list_devices(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> List[Device]:
        """List devices via gRPC."""
        # TODO: Implement with actual proto stubs
        # stub = self._stubs['device']
        # request = device_pb2.ListDevicesRequest(...)
        # response = await stub.ListDevices(request)
        # return [Device.from_proto(d) for d in response.devices]
        raise NotImplementedError("Proto stubs not yet implemented")

    async def get_device(self, device_id: str) -> Device:
        """Get device via gRPC."""
        # TODO: Implement with actual proto stubs
        raise NotImplementedError("Proto stubs not yet implemented")

    async def create_device(self, device: DeviceCreate) -> Device:
        """Create device via gRPC."""
        # TODO: Implement with actual proto stubs
        raise NotImplementedError("Proto stubs not yet implemented")

    async def update_device(self, device_id: str, device: DeviceUpdate) -> Device:
        """Update device via gRPC."""
        # TODO: Implement with actual proto stubs
        raise NotImplementedError("Proto stubs not yet implemented")

    async def delete_device(self, device_id: str):
        """Delete device via gRPC."""
        # TODO: Implement with actual proto stubs
        raise NotImplementedError("Proto stubs not yet implemented")

    # Fleet methods (to be implemented with actual proto stubs)
    async def list_fleets(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Fleet]:
        """List fleets via gRPC."""
        # TODO: Implement with actual proto stubs
        raise NotImplementedError("Proto stubs not yet implemented")

    async def get_fleet(self, fleet_id: str) -> Fleet:
        """Get fleet via gRPC."""
        # TODO: Implement with actual proto stubs
        raise NotImplementedError("Proto stubs not yet implemented")

    async def create_fleet(self, fleet: FleetCreate) -> Fleet:
        """Create fleet via gRPC."""
        # TODO: Implement with actual proto stubs
        raise NotImplementedError("Proto stubs not yet implemented")

    # Execution methods (to be implemented with actual proto stubs)
    async def create_execution(self, execution: ExecutionCreate) -> Execution:
        """Create execution via gRPC."""
        # TODO: Implement with actual proto stubs
        raise NotImplementedError("Proto stubs not yet implemented")

    async def get_execution(self, execution_id: str) -> Execution:
        """Get execution via gRPC."""
        # TODO: Implement with actual proto stubs
        raise NotImplementedError("Proto stubs not yet implemented")

