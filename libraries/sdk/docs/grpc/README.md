# Stack4Things SDK - gRPC Documentation

## Overview

The gRPC client provides high-performance, streaming-capable access to Stack4Things services.

## Setup

```python
from sdk import Stack4ThingsGRPCClient

async with Stack4ThingsGRPCClient(
    host="localhost",
    port=50051
) as client:
    # Use client
    pass
```

## Methods

### Device Methods

```python
# List devices
devices = await client.list_devices(page=1, page_size=20)

# Get device
device = await client.get_device("device-123")

# Create device
device = await client.create_device(DeviceCreate(...))

# Update device
device = await client.update_device("device-123", DeviceUpdate(...))

# Delete device
await client.delete_device("device-123")
```

### Fleet Methods

```python
# List fleets
fleets = await client.list_fleets()

# Get fleet
fleet = await client.get_fleet("fleet-123")

# Create fleet
fleet = await client.create_fleet(FleetCreate(...))
```

### Execution Methods

```python
# Create execution
execution = await client.create_execution(ExecutionCreate(...))

# Get execution
execution = await client.get_execution("execution-123")
```

## Streaming

gRPC supports streaming for real-time updates:

```python
# Stream device updates (when implemented)
async for update in client.stream_device_updates("device-123"):
    print(f"Device update: {update}")
```

## Error Handling

```python
import grpc

try:
    device = await client.get_device("device-123")
except grpc.RpcError as e:
    if e.code() == grpc.StatusCode.NOT_FOUND:
        print("Device not found")
    else:
        print(f"gRPC error: {e}")
```

## TLS/SSL

For secure connections:

```python
import grpc

credentials = grpc.ssl_channel_credentials()

client = Stack4ThingsGRPCClient(
    host="localhost",
    port=50051,
    credentials=credentials
)
```

## Note

gRPC methods are currently placeholders. They will be fully implemented once proto files are generated.

