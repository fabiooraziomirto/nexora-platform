# Stack4Things Python SDK

Python SDK for interacting with Stack4Things v2.0 services via REST API and gRPC.

## Installation

```bash
pip install stack4things-sdk
```

Or with Poetry:

```bash
poetry add stack4things-sdk
```

## Features

- ✅ REST API client
- ✅ gRPC client (when proto files are available)
- ✅ Type definitions
- ✅ Async/await support
- ✅ Type hints
- ✅ Error handling

## Quick Start

### REST API Client

```python
import asyncio
from sdk import Stack4ThingsClient, DeviceCreate

async def main():
    # Initialize client
    async with Stack4ThingsClient(
        base_url="http://localhost:8000",
        token="your-token-here"
    ) as client:
        # List devices
        devices = await client.devices.list(page=1, page_size=10)
        print(f"Found {devices.total} devices")
        
        # Get device
        device = await client.devices.get("device-123")
        print(f"Device: {device.name}")
        
        # Create device
        new_device = await client.devices.create(
            DeviceCreate(
                name="Raspberry Pi 4",
                device_type="raspberry_pi",
                description="Test device"
            )
        )
        print(f"Created device: {new_device.id}")

asyncio.run(main())
```

### gRPC Client

```python
import asyncio
from sdk import Stack4ThingsGRPCClient

async def main():
    async with Stack4ThingsGRPCClient(
        host="localhost",
        port=50051
    ) as client:
        # List devices
        devices = await client.list_devices()
        print(f"Found {len(devices)} devices")

asyncio.run(main())
```

## API Reference

### Stack4ThingsClient

Main client for REST API operations.

```python
client = Stack4ThingsClient(
    base_url="http://localhost:8000",
    api_version="v2",
    token="your-token",
    timeout=30.0
)
```

#### Sub-clients

- `client.devices` - Device management
- `client.fleet` - Fleet management
- `client.network` - Network management
- `client.execution` - Execution management

### DeviceClient

```python
# List devices
devices = await client.devices.list(page=1, page_size=20, status="online")

# Get device
device = await client.devices.get("device-123")

# Create device
device = await client.devices.create(DeviceCreate(...))

# Update device
device = await client.devices.update("device-123", DeviceUpdate(...))

# Delete device
await client.devices.delete("device-123")
```

### FleetClient

```python
# List fleets
fleets = await client.fleet.list(page=1, page_size=20)

# Get fleet
fleet = await client.fleet.get("fleet-123")

# Create fleet
fleet = await client.fleet.create(FleetCreate(...))

# Update fleet
fleet = await client.fleet.update("fleet-123", FleetUpdate(...))

# Add devices to fleet
fleet = await client.fleet.add_devices("fleet-123", ["device-1", "device-2"])

# Remove devices from fleet
fleet = await client.fleet.remove_devices("fleet-123", ["device-1"])
```

### NetworkClient

```python
# List networks
networks = await client.network.list(page=1, page_size=20)

# Get network
network = await client.network.get("network-123")

# Create network
network = await client.network.create(NetworkCreate(...))

# Update network
network = await client.network.update("network-123", NetworkUpdate(...))
```

### ExecutionClient

```python
# List executions
executions = await client.execution.list(page=1, page_size=20, device_id="device-123")

# Get execution
execution = await client.execution.get("execution-123")

# Create execution
execution = await client.execution.create(ExecutionCreate(...))

# Cancel execution
execution = await client.execution.cancel("execution-123")
```

## Type Definitions

All types are defined in `sdk.types`:

- `Device` - Device model
- `DeviceCreate` - Device creation model
- `DeviceUpdate` - Device update model
- `DeviceStatus` - Device status enum
- `Fleet` - Fleet model
- `FleetCreate` - Fleet creation model
- `Network` - Network model
- `Execution` - Execution model
- `ExecutionStatus` - Execution status enum
- `PaginatedResponse` - Paginated response model

## Error Handling

The SDK raises `httpx.HTTPStatusError` for HTTP errors:

```python
from httpx import HTTPStatusError

try:
    device = await client.devices.get("nonexistent")
except HTTPStatusError as e:
    if e.response.status_code == 404:
        print("Device not found")
    else:
        print(f"Error: {e}")
```

## Authentication

The SDK supports Bearer token authentication:

```python
client = Stack4ThingsClient(
    base_url="http://localhost:8000",
    token="your-jwt-token"
)
```

## Development

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Format code
poetry run black .
poetry run ruff check .

# Type check
poetry run mypy sdk
```

## Documentation

Full documentation is available at:
- [API Documentation](./docs/api/)
- [gRPC Documentation](./docs/grpc/)

## License

MIT

