import pytest
from httpx import ASGITransport, AsyncClient
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test env before importing app/settings.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_device_service.db")
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("KAFKA_REQUIRED", "false")
os.environ.setdefault(
    "AGENT_BOOTSTRAP_TOKENS", "test-bootstrap:test-secret:4102444800,expired:expired-secret:1"
)

from device_service.core.database import Base, get_db
from device_service.main import app

TEST_DATABASE_URL_SYNC = "sqlite:///./test_device_service.db"
TEST_DATABASE_URL_ASYNC = "sqlite+aiosqlite:///./test_device_service.db"


@pytest.fixture
async def db_session():
    """Create test database session."""
    sync_engine = create_engine(TEST_DATABASE_URL_SYNC)
    Base.metadata.create_all(sync_engine)

    async_engine = create_async_engine(TEST_DATABASE_URL_ASYNC, pool_pre_ping=True)
    async_session = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    # Cleanup
    Base.metadata.drop_all(sync_engine)
    sync_engine.dispose()
    await async_engine.dispose()
    if os.path.exists("./test_device_service.db"):
        os.remove("./test_device_service.db")


@pytest.fixture
async def client(db_session):
    """Create test client."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_device(client):
    """Test device creation."""
    response = await client.post(
        "/api/v2/devices",
        json={
            "name": "test-device",
            "device_type": "raspberry-pi",
            "description": "Test device",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-device"
    assert data["device_type"] == "raspberry-pi"
    assert data["status"] == "offline"


@pytest.mark.asyncio
async def test_list_devices(client):
    """Test device listing."""
    # Create a device first
    await client.post(
        "/api/v2/devices",
        json={
            "name": "test-device",
            "device_type": "raspberry-pi",
        },
    )
    
    # List devices
    response = await client.get("/api/v2/devices")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_get_device(client):
    """Test getting a device."""
    # Create a device first
    create_response = await client.post(
        "/api/v2/devices",
        json={
            "name": "test-device",
            "device_type": "raspberry-pi",
        },
    )
    device_id = create_response.json()["id"]
    
    # Get device
    response = await client.get(f"/api/v2/devices/{device_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == device_id
    assert data["name"] == "test-device"


@pytest.mark.asyncio
async def test_update_device(client):
    """Test device update."""
    # Create a device first
    create_response = await client.post(
        "/api/v2/devices",
        json={
            "name": "test-device",
            "device_type": "raspberry-pi",
        },
    )
    device_id = create_response.json()["id"]
    
    # Update device
    response = await client.patch(
        f"/api/v2/devices/{device_id}",
        json={
            "name": "updated-device",
            "description": "Updated description",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "updated-device"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_delete_device(client):
    """Test device deletion."""
    # Create a device first
    create_response = await client.post(
        "/api/v2/devices",
        json={
            "name": "test-device",
            "device_type": "raspberry-pi",
        },
    )
    device_id = create_response.json()["id"]
    
    # Delete device
    response = await client.delete(f"/api/v2/devices/{device_id}")
    assert response.status_code == 204
    
    # Verify deletion
    get_response = await client.get(f"/api/v2/devices/{device_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_not_found_returns_404(client):
    """Test missing device returns 404."""
    response = await client.get("/api/v2/devices/3b2bf08b-ec5e-4618-bf72-3b6e5f588888")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_devices_filter_and_pagination(client):
    """Test filtering and pagination on list endpoint."""
    await client.post(
        "/api/v2/devices",
        json={"name": "sensor-a", "device_type": "sensor", "description": "A"},
    )
    await client.post(
        "/api/v2/devices",
        json={"name": "camera-a", "device_type": "camera", "description": "B"},
    )
    await client.post(
        "/api/v2/devices",
        json={"name": "sensor-b", "device_type": "sensor", "description": "C"},
    )

    response = await client.get("/api/v2/devices?device_type=sensor&page=1&page_size=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert payload["total"] >= 2
    assert len(payload["items"]) == 1
    assert payload["items"][0]["device_type"] == "sensor"


# ---------------------------------------------------------------------------
# Agent endpoint tests
# ---------------------------------------------------------------------------

BOOTSTRAP_HEADER = {"X-Bootstrap-Token": "test-bootstrap:test-secret"}


@pytest.mark.asyncio
async def test_agent_register_creates_online_device(client):
    """Register should create a new device with status=online."""
    response = await client.post(
        "/api/v2/agents/register",
        json={"name": "agent-1", "device_type": "raspberry-pi"},
        headers=BOOTSTRAP_HEADER,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "online"
    assert "device_id" in data
    assert "last_seen" in data


@pytest.mark.asyncio
async def test_agent_register_updates_existing(client):
    """Register with an existing device_id should update, not duplicate."""
    resp1 = await client.post(
        "/api/v2/agents/register",
        json={"name": "agent-2", "device_type": "sensor"},
        headers=BOOTSTRAP_HEADER,
    )
    device_id = resp1.json()["device_id"]

    resp2 = await client.post(
        "/api/v2/agents/register",
        json={"device_id": device_id, "name": "agent-2-updated", "device_type": "sensor"},
        headers=BOOTSTRAP_HEADER,
    )
    assert resp2.status_code == 201
    assert resp2.json()["device_id"] == device_id

    get_resp = await client.get(f"/api/v2/devices/{device_id}")
    assert get_resp.json()["name"] == "agent-2-updated"


@pytest.mark.asyncio
async def test_agent_heartbeat_updates_last_seen(client):
    """Heartbeat should update last_seen and return status."""
    reg = await client.post(
        "/api/v2/agents/register",
        json={"name": "hb-agent", "device_type": "camera"},
        headers=BOOTSTRAP_HEADER,
    )
    device_id = reg.json()["device_id"]

    hb = await client.post(
        f"/api/v2/agents/{device_id}/heartbeat",
        json={"status": "online"},
    )
    assert hb.status_code == 200
    data = hb.json()
    assert data["device_id"] == device_id
    assert data["status"] == "online"
    assert data["last_seen"] >= reg.json()["last_seen"]


@pytest.mark.asyncio
async def test_agent_heartbeat_missing_device_404(client):
    """Heartbeat for non-existent device should return 404."""
    response = await client.post(
        "/api/v2/agents/00000000-0000-0000-0000-000000000000/heartbeat",
        json={"status": "online"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_agent_register_without_token_401(client):
    """Register without X-Bootstrap-Token should return 422 (missing header)."""
    response = await client.post(
        "/api/v2/agents/register",
        json={"name": "no-token", "device_type": "sensor"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_agent_register_invalid_token_401(client):
    """Register with a wrong secret should return 401."""
    response = await client.post(
        "/api/v2/agents/register",
        json={"name": "bad-token", "device_type": "sensor"},
        headers={"X-Bootstrap-Token": "test-bootstrap:wrong-secret"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_agent_register_expired_token_401(client):
    """Register with an expired token should return 401."""
    response = await client.post(
        "/api/v2/agents/register",
        json={"name": "expired", "device_type": "sensor"},
        headers={"X-Bootstrap-Token": "expired:expired-secret"},
    )
    assert response.status_code == 401

