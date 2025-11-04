# Stack4Things SDK Documentation

Welcome to the Stack4Things Python SDK documentation.

## Quick Start

```python
from sdk import Stack4ThingsClient

async with Stack4ThingsClient(
    base_url="http://localhost:8000",
    token="your-token"
) as client:
    devices = await client.devices.list()
```

## Documentation

- [API Reference](./api/README.md)
- [gRPC Documentation](./grpc/README.md)

