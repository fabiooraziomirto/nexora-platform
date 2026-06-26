"""
REST API client for Nxr.
"""

from typing import Optional, Dict, Any, List
import httpx
from httpx import AsyncClient, Response

from sdk.types import (
    Device,
    DeviceCreate,
    DeviceUpdate,
    Fleet,
    FleetCreate,
    FleetUpdate,
    Network,
    NetworkCreate,
    NetworkUpdate,
    Execution,
    ExecutionCreate,
    PaginatedResponse,
)


class NxrClient:
    """Main client for Nxr API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_version: str = "v2",
        token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.token = token
        self.timeout = timeout
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        self.client = AsyncClient(
            base_url=f"{self.base_url}/api/{api_version}",
            headers=headers,
            timeout=timeout,
        )
        
        # Sub-clients
        self.devices = DeviceClient(self.client)
        self.fleet = FleetClient(self.client)
        self.network = NetworkClient(self.client)
        self.execution = ExecutionClient(self.client)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def health(self) -> Dict[str, Any]:
        """Check API health."""
        response = await self.client.get("/health")
        response.raise_for_status()
        return response.json()

    async def version(self) -> Dict[str, Any]:
        """Get API version."""
        response = await self.client.get("/version")
        response.raise_for_status()
        return response.json()


class DeviceClient:
    """Device management client."""

    def __init__(self, client: AsyncClient):
        self.client = client

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> PaginatedResponse:
        """List devices."""
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        if status:
            params["status"] = status
        if device_type:
            params["device_type"] = device_type
        
        response = await self.client.get("/devices", params=params)
        response.raise_for_status()
        return PaginatedResponse(**response.json())

    async def get(self, device_id: str) -> Device:
        """Get device by ID."""
        response = await self.client.get(f"/devices/{device_id}")
        response.raise_for_status()
        return Device(**response.json())

    async def create(self, device: DeviceCreate) -> Device:
        """Create device."""
        response = await self.client.post("/devices", json=device.model_dump())
        response.raise_for_status()
        return Device(**response.json())

    async def update(self, device_id: str, device: DeviceUpdate) -> Device:
        """Update device."""
        response = await self.client.put(
            f"/devices/{device_id}",
            json=device.model_dump(exclude_unset=True),
        )
        response.raise_for_status()
        return Device(**response.json())

    async def delete(self, device_id: str):
        """Delete device."""
        response = await self.client.delete(f"/devices/{device_id}")
        response.raise_for_status()


class FleetClient:
    """Fleet management client."""

    def __init__(self, client: AsyncClient):
        self.client = client

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse:
        """List fleets."""
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        response = await self.client.get("/fleet", params=params)
        response.raise_for_status()
        return PaginatedResponse(**response.json())

    async def get(self, fleet_id: str) -> Fleet:
        """Get fleet by ID."""
        response = await self.client.get(f"/fleet/{fleet_id}")
        response.raise_for_status()
        return Fleet(**response.json())

    async def create(self, fleet: FleetCreate) -> Fleet:
        """Create fleet."""
        response = await self.client.post("/fleet", json=fleet.model_dump())
        response.raise_for_status()
        return Fleet(**response.json())

    async def update(self, fleet_id: str, fleet: FleetUpdate) -> Fleet:
        """Update fleet."""
        response = await self.client.put(
            f"/fleet/{fleet_id}",
            json=fleet.model_dump(exclude_unset=True),
        )
        response.raise_for_status()
        return Fleet(**response.json())

    async def delete(self, fleet_id: str):
        """Delete fleet."""
        response = await self.client.delete(f"/fleet/{fleet_id}")
        response.raise_for_status()

    async def add_devices(self, fleet_id: str, device_ids: List[str]) -> Fleet:
        """Add devices to fleet."""
        response = await self.client.post(
            f"/fleet/{fleet_id}/devices",
            json={"device_ids": device_ids},
        )
        response.raise_for_status()
        return Fleet(**response.json())

    async def remove_devices(self, fleet_id: str, device_ids: List[str]) -> Fleet:
        """Remove devices from fleet."""
        response = await self.client.delete(
            f"/fleet/{fleet_id}/devices",
            json={"device_ids": device_ids},
        )
        response.raise_for_status()
        return Fleet(**response.json())


class NetworkClient:
    """Network management client."""

    def __init__(self, client: AsyncClient):
        self.client = client

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse:
        """List networks."""
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        response = await self.client.get("/network", params=params)
        response.raise_for_status()
        return PaginatedResponse(**response.json())

    async def get(self, network_id: str) -> Network:
        """Get network by ID."""
        response = await self.client.get(f"/network/{network_id}")
        response.raise_for_status()
        return Network(**response.json())

    async def create(self, network: NetworkCreate) -> Network:
        """Create network."""
        response = await self.client.post("/network", json=network.model_dump())
        response.raise_for_status()
        return Network(**response.json())

    async def update(self, network_id: str, network: NetworkUpdate) -> Network:
        """Update network."""
        response = await self.client.put(
            f"/network/{network_id}",
            json=network.model_dump(exclude_unset=True),
        )
        response.raise_for_status()
        return Network(**response.json())

    async def delete(self, network_id: str):
        """Delete network."""
        response = await self.client.delete(f"/network/{network_id}")
        response.raise_for_status()


class ExecutionClient:
    """Execution management client."""

    def __init__(self, client: AsyncClient):
        self.client = client

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        device_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> PaginatedResponse:
        """List executions."""
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        if device_id:
            params["device_id"] = device_id
        if status:
            params["status"] = status
        
        response = await self.client.get("/execution", params=params)
        response.raise_for_status()
        return PaginatedResponse(**response.json())

    async def get(self, execution_id: str) -> Execution:
        """Get execution by ID."""
        response = await self.client.get(f"/execution/{execution_id}")
        response.raise_for_status()
        return Execution(**response.json())

    async def create(self, execution: ExecutionCreate) -> Execution:
        """Create execution."""
        response = await self.client.post("/execution", json=execution.model_dump())
        response.raise_for_status()
        return Execution(**response.json())

    async def cancel(self, execution_id: str) -> Execution:
        """Cancel execution."""
        response = await self.client.post(f"/execution/{execution_id}/cancel")
        response.raise_for_status()
        return Execution(**response.json())

