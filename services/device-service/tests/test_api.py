import pytest
from httpx import AsyncClient
from device_service.main import app
from device_service.core.database import get_db, Base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os


# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "mysql+pymysql://test:test@localhost:3306/test_stack4things"
)


@pytest.fixture
async def db_session():
    """Create test database session."""
    # Create sync engine for testing
    sync_engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(sync_engine)
    
    # Create async engine
    async_engine = create_async_engine(
        TEST_DATABASE_URL.replace("mysql+pymysql://", "mysql+aiomysql://"),
        pool_pre_ping=True,
    )
    
    async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    # Cleanup
    Base.metadata.drop_all(sync_engine)
    sync_engine.dispose()
    await async_engine.dispose()


@pytest.fixture
async def client(db_session):
    """Create test client."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
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

