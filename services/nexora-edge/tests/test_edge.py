"""
Tests for the nexora-edge gateway using the in-memory store fallback
(REDIS_ENABLED=false, KAFKA_ENABLED=false) — no external infra required.
"""
import time

import pytest
from httpx import ASGITransport, AsyncClient

import main

transport = ASGITransport(app=main.app)


@pytest.fixture(autouse=True)
def _clean_state():
    main._local_sessions.clear()
    main._local_dispatches.clear()
    yield
    main._local_sessions.clear()
    main._local_dispatches.clear()


async def _client():
    return AsyncClient(transport=transport, base_url="http://test")


# ── Health / readiness ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health():
    async with await _client() as c:
        assert (await c.get("/health")).status_code == 200


@pytest.mark.asyncio
async def test_ready():
    async with await _client() as c:
        r = await c.get("/ready")
        assert r.status_code == 200


# ── Session lifecycle ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_requires_device_id():
    async with await _client() as c:
        r = await c.post("/api/v2/agents/sessions/register", json={"foo": "bar"})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_get_heartbeat_flow():
    async with await _client() as c:
        r = await c.post("/api/v2/agents/sessions/register",
                         json={"device_id": "dev-1", "fw": "1.2.3"})
        assert r.status_code == 201
        assert r.json()["device_id"] == "dev-1"

        r = await c.get("/api/v2/agents/sessions/dev-1")
        assert r.status_code == 200
        assert r.json()["metadata"]["fw"] == "1.2.3"

        r = await c.post("/api/v2/agents/sessions/dev-1/heartbeat")
        assert r.status_code == 200
        assert "last_seen" in r.json()


@pytest.mark.asyncio
async def test_get_missing_session():
    async with await _client() as c:
        assert (await c.get("/api/v2/agents/sessions/ghost")).status_code == 404


@pytest.mark.asyncio
async def test_heartbeat_missing_session():
    async with await _client() as c:
        assert (await c.post("/api/v2/agents/sessions/ghost/heartbeat")).status_code == 404


# ── Dispatch delivery ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deliver_unknown_dispatch():
    async with await _client() as c:
        assert (await c.post("/api/v2/deliver/exec-x")).status_code == 404


@pytest.mark.asyncio
async def test_deliver_success_removes_dispatch():
    # Seed an active session and a pending dispatch in the in-memory store.
    now = time.time()
    main._local_sessions["dev-9"] = {
        "device_id": "dev-9", "registered_at": now, "last_seen": now, "metadata": {},
    }
    main._local_dispatches["exec-9"] = {
        "device_id": "dev-9", "received_at": now, "delivery_attempts": 0,
        "event": {"payload": {}, "occurred_at": now},
    }
    async with await _client() as c:
        r = await c.post("/api/v2/deliver/exec-9")
        assert r.status_code == 200
        assert r.json()["status"] == "delivered"
    # Dispatch consumed after successful delivery.
    assert "exec-9" not in main._local_dispatches
