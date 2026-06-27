"""Tests for telemetry ingestion, SLO CRUD, and automatic violation detection."""
import os
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_telemetry_slo.db")
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("KAFKA_REQUIRED", "false")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("AGENT_BOOTSTRAP_TOKENS", "test-bootstrap:test-secret:4102444800")

from device_service.core.database import Base, get_db
from device_service.main import app

_DB_SYNC = "sqlite:///./test_telemetry_slo.db"
_DB_ASYNC = "sqlite+aiosqlite:///./test_telemetry_slo.db"


@pytest.fixture
async def db_session():
    sync_engine = create_engine(_DB_SYNC)
    Base.metadata.create_all(sync_engine)
    async_engine = create_async_engine(_DB_ASYNC, pool_pre_ping=True)
    session_factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    Base.metadata.drop_all(sync_engine)
    sync_engine.dispose()
    await async_engine.dispose()
    if os.path.exists("./test_telemetry_slo.db"):
        os.remove("./test_telemetry_slo.db")


@pytest.fixture
async def client(db_session):
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def device_id(client):
    resp = await client.post(
        "/api/v2/devices",
        json={"name": "telemetry-test-device", "device_type": "sensor"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Telemetry ingest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_single_sample(client, device_id):
    resp = await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": [{"metric": "temperature", "value": 22.5}]},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["ingested"] == 1
    assert data["metrics"]["temperature"] == 1
    assert data["violations"] == 0


@pytest.mark.asyncio
async def test_ingest_batch(client, device_id):
    samples = [{"metric": "cpu", "value": float(i)} for i in range(10)]
    resp = await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": samples},
    )
    assert resp.status_code == 202
    assert resp.json()["ingested"] == 10
    assert resp.json()["metrics"]["cpu"] == 10


@pytest.mark.asyncio
async def test_ingest_multiple_metrics(client, device_id):
    resp = await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": [
            {"metric": "temperature", "value": 25.0},
            {"metric": "humidity", "value": 60.0},
            {"metric": "pressure", "value": 1013.25},
        ]},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["ingested"] == 3
    assert set(data["metrics"].keys()) == {"temperature", "humidity", "pressure"}


@pytest.mark.asyncio
async def test_ingest_with_tags(client, device_id):
    resp = await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": [{"metric": "temperature", "value": 20.0, "tags": {"unit": "celsius", "sensor": "ds18b20"}}]},
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_ingest_nonexistent_device_404(client):
    resp = await client.post(
        "/api/v2/devices/00000000-0000-0000-0000-000000000000/telemetry",
        json={"samples": [{"metric": "temperature", "value": 22.5}]},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ingest_empty_samples_rejected(client, device_id):
    resp = await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": []},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Telemetry query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_telemetry_returns_ingested(client, device_id):
    await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": [{"metric": "temperature", "value": 19.0}]},
    )
    resp = await client.get(f"/api/v2/devices/{device_id}/telemetry?metric=temperature")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert all(s["metric"] == "temperature" for s in data["samples"])


@pytest.mark.asyncio
async def test_query_latest_returns_one_per_metric(client, device_id):
    await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": [
            {"metric": "temperature", "value": 10.0},
            {"metric": "temperature", "value": 20.0},
            {"metric": "humidity", "value": 55.0},
        ]},
    )
    resp = await client.get(f"/api/v2/devices/{device_id}/telemetry/latest")
    assert resp.status_code == 200
    readings = resp.json()["readings"]
    assert "temperature" in readings
    assert "humidity" in readings
    assert readings["temperature"]["value"] == 20.0  # latest value wins (same commit, higher value stored last)


# ---------------------------------------------------------------------------
# SLO CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_slo(client, device_id):
    resp = await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "temperature", "operator": "lt", "threshold": 30.0, "description": "temp under 30°C"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["metric"] == "temperature"
    assert data["operator"] == "lt"
    assert data["threshold"] == 30.0
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_list_slos(client, device_id):
    await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "cpu", "operator": "lt", "threshold": 90.0},
    )
    await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "memory", "operator": "lt", "threshold": 80.0},
    )
    resp = await client.get(f"/api/v2/devices/{device_id}/slos")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_update_slo(client, device_id):
    create = await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "temperature", "operator": "lt", "threshold": 30.0},
    )
    slo_id = create.json()["id"]
    resp = await client.patch(
        f"/api/v2/devices/{device_id}/slos/{slo_id}",
        json={"threshold": 40.0, "enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["threshold"] == 40.0
    assert resp.json()["enabled"] is False


@pytest.mark.asyncio
async def test_delete_slo(client, device_id):
    create = await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "temperature", "operator": "lt", "threshold": 30.0},
    )
    slo_id = create.json()["id"]
    resp = await client.delete(f"/api/v2/devices/{device_id}/slos/{slo_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_slo_invalid_operator_rejected(client, device_id):
    resp = await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "temperature", "operator": "bad", "threshold": 30.0},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# SLO violation detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_violation_detected_on_ingest(client, device_id):
    """Ingesting a value that violates an SLO should return violations > 0."""
    await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "temperature", "operator": "lt", "threshold": 30.0},
    )
    # value 35 is NOT < 30, so it violates the SLO
    resp = await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": [{"metric": "temperature", "value": 35.0}]},
    )
    assert resp.status_code == 202
    assert resp.json()["violations"] == 1


@pytest.mark.asyncio
async def test_no_violation_when_slo_satisfied(client, device_id):
    await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "temperature", "operator": "lt", "threshold": 30.0},
    )
    resp = await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": [{"metric": "temperature", "value": 25.0}]},
    )
    assert resp.status_code == 202
    assert resp.json()["violations"] == 0


@pytest.mark.asyncio
async def test_disabled_slo_not_evaluated(client, device_id):
    create = await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "temperature", "operator": "lt", "threshold": 30.0},
    )
    slo_id = create.json()["id"]
    await client.patch(
        f"/api/v2/devices/{device_id}/slos/{slo_id}",
        json={"enabled": False},
    )
    resp = await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": [{"metric": "temperature", "value": 99.0}]},
    )
    assert resp.status_code == 202
    assert resp.json()["violations"] == 0


@pytest.mark.asyncio
async def test_multiple_violations_in_batch(client, device_id):
    """A batch with multiple violating samples should report all violations."""
    await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "cpu", "operator": "lt", "threshold": 80.0},
    )
    samples = [{"metric": "cpu", "value": float(v)} for v in [90, 95, 85, 70, 88]]
    resp = await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": samples},
    )
    assert resp.status_code == 202
    assert resp.json()["violations"] == 4  # 90, 95, 85, 88 violate; 70 does not


@pytest.mark.asyncio
async def test_violation_history_queryable(client, device_id):
    await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "temperature", "operator": "lt", "threshold": 30.0},
    )
    await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": [{"metric": "temperature", "value": 35.0}]},
    )
    resp = await client.get(f"/api/v2/devices/{device_id}/slos/violations")
    assert resp.status_code == 200
    violations = resp.json()
    assert len(violations) >= 1
    assert violations[0]["metric"] == "temperature"
    assert violations[0]["observed_value"] == 35.0


@pytest.mark.asyncio
async def test_all_slo_operators(client, device_id):
    """Smoke-test all five operators produce the expected violation decisions."""
    cases = [
        ("lt",  30.0, 35.0, True),   # 35 < 30 → False → violation
        ("lte", 30.0, 30.0, False),  # 30 <= 30 → True → no violation
        ("gt",  20.0, 15.0, True),   # 15 > 20 → False → violation
        ("gte", 20.0, 20.0, False),  # 20 >= 20 → True → no violation
        ("eq",  25.0, 25.1, True),   # 25.1 == 25 → False → violation
    ]
    for operator, threshold, value, expect_violation in cases:
        metric = f"m_{operator}"
        await client.post(
            f"/api/v2/devices/{device_id}/slos",
            json={"metric": metric, "operator": operator, "threshold": threshold},
        )
        resp = await client.post(
            f"/api/v2/devices/{device_id}/telemetry",
            json={"samples": [{"metric": metric, "value": value}]},
        )
        got = resp.json()["violations"] > 0
        assert got == expect_violation, f"operator={operator} value={value} threshold={threshold}: expected violation={expect_violation}"


@pytest.mark.asyncio
async def test_slo_assistant_returns_recommendations(client, device_id):
    await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "temperature", "operator": "lt", "threshold": 30.0},
    )
    await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": [
            {"metric": "temperature", "value": 35.0},
            {"metric": "temperature", "value": 36.0},
        ]},
    )

    resp = await client.get(f"/api/v2/devices/{device_id}/slos/assistant?hours=24")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "attention_required"
    assert data["total_violations"] >= 1
    assert len(data["top_metrics"]) >= 1
    assert data["top_metrics"][0]["metric"] == "temperature"
    assert len(data["recommendations"]) >= 1
    assert len(data["suggested_runbook_steps"]) >= 1


@pytest.mark.asyncio
async def test_slo_assistant_healthy_without_violations(client, device_id):
    await client.post(
        f"/api/v2/devices/{device_id}/slos",
        json={"metric": "temperature", "operator": "lt", "threshold": 30.0},
    )
    await client.post(
        f"/api/v2/devices/{device_id}/telemetry",
        json={"samples": [{"metric": "temperature", "value": 25.0}]},
    )

    resp = await client.get(f"/api/v2/devices/{device_id}/slos/assistant?hours=24")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["total_violations"] == 0
    assert data["top_metrics"] == []
