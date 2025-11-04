# Stack4Things SDK Documentation

## API Documentation

### REST API Client

The REST API client provides a Pythonic interface to Stack4Things REST APIs.

#### Authentication

```python
from sdk import Stack4ThingsClient

client = Stack4ThingsClient(
    base_url="http://localhost:8000",
    token="your-jwt-token"
)
```

#### Devices

```python
# List devices
devices = await client.devices.list(page=1, page_size=20)

# Get device
device = await client.devices.get("device-123")

# Create device
from sdk import DeviceCreate
device = await client.devices.create(
    DeviceCreate(
        name="Raspberry Pi 4",
        device_type="raspberry_pi"
    )
)
```

#### Fleets

```python
# List fleets
fleets = await client.fleet.list()

# Create fleet
from sdk import FleetCreate
fleet = await client.fleet.create(
    FleetCreate(name="Production Fleet")
)
```

### gRPC Client

The gRPC client provides high-performance access to Stack4Things services.

```python
from sdk import Stack4ThingsGRPCClient

async with Stack4ThingsGRPCClient(
    host="localhost",
    port=50051
) as client:
    devices = await client.list_devices()
```

## Type Definitions

All types are defined using Pydantic for validation and serialization.

### Device

```python
from sdk import Device, DeviceStatus

device = Device(
    id="device-123",
    name="Raspberry Pi",
    device_type="raspberry_pi",
    status=DeviceStatus.ONLINE
)
```

### Fleet

```python
from sdk import Fleet

fleet = Fleet(
    id="fleet-123",
    name="Production Fleet",
    device_ids=["device-1", "device-2"]
)
```

### Execution

```python
from sdk import Execution, ExecutionStatus

execution = Execution(
    id="exec-123",
    device_id="device-123",
    plugin_id="plugin-123",
    status=ExecutionStatus.RUNNING
)
```

## Error Handling

The SDK uses standard Python exceptions:

- `httpx.HTTPStatusError` for HTTP errors
- `grpc.RpcError` for gRPC errors

```python
from httpx import HTTPStatusError

try:
    device = await client.devices.get("nonexistent")
except HTTPStatusError as e:
    if e.response.status_code == 404:
        print("Device not found")
```

## Examples

See `examples/` directory for complete examples.

