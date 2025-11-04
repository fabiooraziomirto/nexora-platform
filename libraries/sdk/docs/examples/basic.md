# Stack4Things SDK Examples

## Basic Usage

```python
import asyncio
from sdk import Stack4ThingsClient, DeviceCreate

async def main():
    async with Stack4ThingsClient(
        base_url="http://localhost:8000",
        token="your-token"
    ) as client:
        # List devices
        devices = await client.devices.list(page=1, page_size=10)
        print(f"Found {devices.total} devices")
        
        # Create device
        new_device = await client.devices.create(
            DeviceCreate(
                name="Raspberry Pi 4",
                device_type="raspberry_pi"
            )
        )
        print(f"Created device: {new_device.id}")

asyncio.run(main())
```

## Authentication

```python
from sdk import Stack4ThingsClient

# With token
client = Stack4ThingsClient(
    base_url="http://localhost:8000",
    token="your-jwt-token"
)

# Health check
health = await client.health()
print(health)
```

