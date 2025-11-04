# Authentication Examples

## Token Authentication

```python
from sdk import Stack4ThingsClient

client = Stack4ThingsClient(
    base_url="http://localhost:8000",
    token="your-jwt-token"
)
```

## Keycloak Authentication

```python
import httpx
from sdk import Stack4ThingsClient

# Get token from Keycloak
async with httpx.AsyncClient() as http_client:
    response = await http_client.post(
        "http://keycloak:8080/realms/stack4things/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "your-client-id",
            "client_secret": "your-client-secret",
        }
    )
    token = response.json()["access_token"]

# Use token with SDK
client = Stack4ThingsClient(
    base_url="http://localhost:8000",
    token=token
)
```

