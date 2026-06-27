import pytest
from httpx import ASGITransport, AsyncClient

import main
from main import app


transport = ASGITransport(app=app)


@pytest.fixture(autouse=True)
def reset_gateway_state(monkeypatch):
    main._local_sessions.clear()
    main._local_dispatches.clear()
    main._ws_connections.clear()
    monkeypatch.setattr(main, "producer", None)
    monkeypatch.setattr(main, "redis_client", None)
    monkeypatch.setattr(main, "KAFKA_ENABLED", False)
    monkeypatch.setattr(main, "REDIS_ENABLED", False)
    monkeypatch.setattr(main, "MAX_DELIVERY_ATTEMPTS", 2)
    monkeypatch.setattr(main, "DELIVERY_BACKOFF_SECONDS", 0)
    yield
    main._local_sessions.clear()
    main._local_dispatches.clear()
    main._ws_connections.clear()


async def _client() -> AsyncClient:
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_and_ready_without_kafka_or_redis() -> None:
    async with await _client() as client:
        health = await client.get("/health")
        ready = await client.get("/ready")

    assert health.status_code == 200
    assert health.json()["service"] == "nexora-edge"
    assert ready.status_code == 200
    assert ready.json()["kafka"] == "disabled"
    assert ready.json()["redis"] == "disabled"


@pytest.mark.asyncio
async def test_agent_session_register_heartbeat_and_get() -> None:
    async with await _client() as client:
        register = await client.post(
            "/api/v2/agents/sessions/register",
            json={"device_id": "device-1", "agent_version": "test"},
        )
        heartbeat = await client.post("/api/v2/agents/sessions/device-1/heartbeat")
        get_session = await client.get("/api/v2/agents/sessions/device-1")

    assert register.status_code == 201
    assert register.json()["device_id"] == "device-1"
    assert register.json()["metadata"]["agent_version"] == "test"
    assert heartbeat.status_code == 200
    assert heartbeat.json()["device_id"] == "device-1"
    assert get_session.status_code == 200
    assert get_session.json()["device_id"] == "device-1"


@pytest.mark.asyncio
async def test_deliver_returns_404_when_dispatch_is_missing() -> None:
    async with await _client() as client:
        response = await client.post("/api/v2/deliver/missing-execution")

    assert response.status_code == 404
    assert response.json()["detail"] == "dispatch not found in cache"


@pytest.mark.asyncio
async def test_deliver_succeeds_when_dispatch_and_session_exist() -> None:
    execution_id = "exec-1"
    device_id = "device-1"
    await main._session_set(device_id, {"device_id": device_id, "last_seen": 1.0})
    await main._dispatch_set(
        execution_id,
        {
            "execution_id": execution_id,
            "device_id": device_id,
            "event": {
                "event_type": "execution.dispatched",
                "payload": {"device_id": device_id, "command": "ping"},
                "occurred_at": 1.0,
            },
            "received_at": 1.0,
            "delivery_attempts": 0,
            "delivery_last_error": "",
        },
    )

    async with await _client() as client:
        response = await client.post(f"/api/v2/deliver/{execution_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "delivered"
    assert payload["execution_id"] == execution_id
    assert payload["device_id"] == device_id
    assert payload["payload"]["command"] == "ping"
    assert await main._dispatch_get(execution_id) is None


@pytest.mark.asyncio
async def test_deliver_fails_after_retries_when_session_is_missing() -> None:
    execution_id = "exec-no-session"
    device_id = "missing-device"
    await main._dispatch_set(
        execution_id,
        {
            "execution_id": execution_id,
            "device_id": device_id,
            "event": {
                "event_type": "execution.dispatched",
                "payload": {"device_id": device_id},
                "occurred_at": 1.0,
            },
            "received_at": 1.0,
            "delivery_attempts": 0,
            "delivery_last_error": "",
        },
    )

    async with await _client() as client:
        response = await client.post(f"/api/v2/deliver/{execution_id}")

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["status"] == "delivery_failed"
    assert detail["attempts"] == 2
    assert detail["device_id"] == device_id
    assert await main._dispatch_get(execution_id) is None
