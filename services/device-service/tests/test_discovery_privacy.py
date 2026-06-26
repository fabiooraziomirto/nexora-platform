"""
Tests for device discovery (RFC 8628 pairing) and privacy consent endpoints.
AUTH_ENABLED=false so get_current_user returns dev-user / dev tenant.
"""
import pytest
from httpx import ASGITransport, AsyncClient
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_discovery.db")
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("KAFKA_REQUIRED", "false")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault(
    "AGENT_BOOTSTRAP_TOKENS", "test-bootstrap:test-secret:4102444800"
)

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from device_service.core.database import Base, get_db
from device_service.main import app

TEST_DB_SYNC = "sqlite:///./test_discovery.db"
TEST_DB_ASYNC = "sqlite+aiosqlite:///./test_discovery.db"


@pytest.fixture
async def db_session():
    sync_engine = create_engine(TEST_DB_SYNC)
    Base.metadata.create_all(sync_engine)
    async_engine = create_async_engine(TEST_DB_ASYNC, pool_pre_ping=True)
    async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    Base.metadata.drop_all(sync_engine)
    sync_engine.dispose()
    await async_engine.dispose()
    if os.path.exists("./test_discovery.db"):
        os.remove("./test_discovery.db")


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Discovery tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_announce_returns_codes(client):
    """Announce should return device_code, user_code, and expires_in."""
    resp = await client.post(
        "/api/v2/devices/announce",
        json={"hardware_id": "hw-001", "device_type": "nexoraedge", "firmware_version": "2.1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "device_code" in data
    assert "user_code" in data
    assert "-" in data["user_code"]    # XXXX-XXXX format
    assert data["expires_in"] > 0
    assert data["poll_interval"] > 0


@pytest.mark.asyncio
async def test_poll_pending_before_claim(client):
    """Poll before claim should return status=announced."""
    ann = await client.post(
        "/api/v2/devices/announce",
        json={"hardware_id": "hw-002", "device_type": "nexoraedge"},
    )
    device_code = ann.json()["device_code"]

    poll = await client.get(f"/api/v2/devices/announce/poll?device_code={device_code}")
    assert poll.status_code == 200
    assert poll.json()["status"] == "announced"
    assert poll.json()["bootstrap_token"] is None


@pytest.mark.asyncio
async def test_list_pending_shows_announced(client):
    """Pending list should include newly announced devices."""
    await client.post(
        "/api/v2/devices/announce",
        json={"hardware_id": "hw-003", "device_type": "sensor"},
    )
    resp = await client.get("/api/v2/devices/pending")
    assert resp.status_code == 200
    items = resp.json()
    assert any(d["hardware_id"] == "hw-003" for d in items)


@pytest.mark.asyncio
async def test_claim_creates_device_and_approves(client):
    """Claiming a discovery should create a device and mark discovery approved."""
    ann = await client.post(
        "/api/v2/devices/announce",
        json={"hardware_id": "hw-004", "device_type": "nexoraedge"},
    )
    discovery_id = ann.json()["discovery_id"]
    device_code = ann.json()["device_code"]

    claim = await client.post(
        f"/api/v2/devices/{discovery_id}/claim",
        json={"name": "My Sensor", "description": "HVAC floor 3"},
    )
    assert claim.status_code == 201
    data = claim.json()
    assert "device_id" in data
    assert data["name"] == "My Sensor"

    # Poll should now return approved + bootstrap_token
    poll = await client.get(f"/api/v2/devices/announce/poll?device_code={device_code}")
    assert poll.status_code == 200
    assert poll.json()["status"] == "approved"
    assert poll.json()["bootstrap_token"] is not None
    assert poll.json()["device_id"] == data["device_id"]


@pytest.mark.asyncio
async def test_claim_twice_fails(client):
    """Claiming an already-approved discovery should return 409."""
    ann = await client.post(
        "/api/v2/devices/announce",
        json={"hardware_id": "hw-005", "device_type": "nexoraedge"},
    )
    discovery_id = ann.json()["discovery_id"]
    await client.post(f"/api/v2/devices/{discovery_id}/claim", json={"name": "First Claim"})
    resp = await client.post(f"/api/v2/devices/{discovery_id}/claim", json={"name": "Second Claim"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_reject_discovery(client):
    """Rejecting a discovery should mark it rejected and stop polling."""
    ann = await client.post(
        "/api/v2/devices/announce",
        json={"hardware_id": "hw-006", "device_type": "nexoraedge"},
    )
    discovery_id = ann.json()["discovery_id"]
    device_code = ann.json()["device_code"]

    rej = await client.post(f"/api/v2/devices/{discovery_id}/reject")
    assert rej.status_code == 204

    poll = await client.get(f"/api/v2/devices/announce/poll?device_code={device_code}")
    assert poll.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_poll_unknown_device_code_404(client):
    poll = await client.get("/api/v2/devices/announce/poll?device_code=nonexistent")
    assert poll.status_code == 404


# ---------------------------------------------------------------------------
# Privacy consent tests
# ---------------------------------------------------------------------------

async def _create_device(client) -> str:
    resp = await client.post(
        "/api/v2/devices",
        json={"name": "privacy-test-device", "device_type": "sensor"},
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_get_privacy_empty(client):
    """Fresh device should have no active consents and level 0."""
    device_id = await _create_device(client)
    resp = await client.get(f"/api/v2/devices/{device_id}/privacy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["privacy_level"] == 0
    assert data["active_consents"] == []


@pytest.mark.asyncio
async def test_grant_consent_level1(client):
    """Owner can grant level 1 access to a building manager tenant."""
    device_id = await _create_device(client)
    resp = await client.post(
        f"/api/v2/devices/{device_id}/privacy/consent",
        json={"granted_to": "building-mgmt", "granted_to_type": "tenant", "level": 1},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["level"] == 1
    assert data["granted_to"] == "building-mgmt"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_grant_consent_level4_rejected(client):
    """Level 4 cannot be delegated — must return 400."""
    device_id = await _create_device(client)
    resp = await client.post(
        f"/api/v2/devices/{device_id}/privacy/consent",
        json={"granted_to": "someone", "granted_to_type": "user", "level": 4},
    )
    assert resp.status_code == 422   # Pydantic rejects level>3 before handler


@pytest.mark.asyncio
async def test_grant_duplicate_consent_409(client):
    """Duplicate active consent for same target+level returns 409."""
    device_id = await _create_device(client)
    payload = {"granted_to": "user-abc", "granted_to_type": "user", "level": 2}
    await client.post(f"/api/v2/devices/{device_id}/privacy/consent", json=payload)
    resp = await client.post(f"/api/v2/devices/{device_id}/privacy/consent", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_revoke_consent(client):
    """Revoking consent should deactivate it immediately."""
    device_id = await _create_device(client)
    grant = await client.post(
        f"/api/v2/devices/{device_id}/privacy/consent",
        json={"granted_to": "facility-co", "granted_to_type": "tenant", "level": 2},
    )
    consent_id = grant.json()["consent_id"]

    revoke = await client.delete(f"/api/v2/devices/{device_id}/privacy/consent/{consent_id}")
    assert revoke.status_code == 204

    # Consent should no longer appear in active list
    summary = await client.get(f"/api/v2/devices/{device_id}/privacy")
    assert all(c["consent_id"] != consent_id for c in summary.json()["active_consents"])


@pytest.mark.asyncio
async def test_revoke_twice_returns_409(client):
    device_id = await _create_device(client)
    grant = await client.post(
        f"/api/v2/devices/{device_id}/privacy/consent",
        json={"granted_to": "u", "granted_to_type": "user", "level": 1},
    )
    consent_id = grant.json()["consent_id"]
    await client.delete(f"/api/v2/devices/{device_id}/privacy/consent/{consent_id}")
    resp = await client.delete(f"/api/v2/devices/{device_id}/privacy/consent/{consent_id}")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_ownership_events_logged(client):
    """Grant and revoke should appear in the ownership event audit log."""
    device_id = await _create_device(client)
    grant = await client.post(
        f"/api/v2/devices/{device_id}/privacy/consent",
        json={"granted_to": "auditor", "granted_to_type": "user", "level": 3},
    )
    consent_id = grant.json()["consent_id"]
    await client.delete(f"/api/v2/devices/{device_id}/privacy/consent/{consent_id}")

    events = await client.get(f"/api/v2/devices/{device_id}/privacy/events")
    assert events.status_code == 200
    actions = [e["action"] for e in events.json()]
    assert "consent_granted" in actions
    assert "consent_revoked" in actions
