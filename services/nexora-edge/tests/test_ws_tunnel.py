"""
Tests for the WebSocket reverse-tunnel endpoint.

All tests run without Redis (REDIS_ENABLED=false set in conftest.py) so
they exercise the in-memory fallback path. The Redis Pub/Sub cross-replica
routing requires an integration test with a real Redis; those are out of
scope here and should be run via docker-compose.

Coverage:
  - WS connection opens a session / reconnect updates it
  - Pending dispatches are replayed immediately on connect
  - Agent ACK removes the dispatch from cache
  - Un-ACKed dispatches survive a reconnect (at-least-once delivery)
  - Disconnect marks session ws_connected=False
  - Rapid connect/disconnect churn leaves state clean
  - Session heartbeat over WS refreshes last_seen
"""

import asyncio
import time

import pytest
from starlette.testclient import TestClient

import main
from main import app


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    main._local_sessions.clear()
    main._local_dispatches.clear()
    main._ws_connections.clear()
    monkeypatch.setattr(main, "redis_client", None)
    monkeypatch.setattr(main, "REDIS_ENABLED", False)
    monkeypatch.setattr(main, "KAFKA_ENABLED", False)
    yield
    main._local_sessions.clear()
    main._local_dispatches.clear()
    main._ws_connections.clear()


def _seed_session(device_id: str) -> None:
    asyncio.run(main._session_set(device_id, {
        "device_id": device_id,
        "registered_at": time.time(),
        "last_seen": time.time(),
        "ws_connected": False,
        "metadata": {},
    }))


def _seed_dispatch(execution_id: str, device_id: str) -> None:
    asyncio.run(main._dispatch_set(execution_id, {
        "execution_id": execution_id,
        "device_id": device_id,
        "event": {
            "event_type": "execution.dispatched",
            "payload": {"device_id": device_id, "command": "ping"},
            "occurred_at": time.time(),
        },
        "received_at": time.time(),
        "delivery_attempts": 0,
        "delivery_last_error": "",
    }))


def _get_session(device_id: str) -> dict | None:
    return asyncio.run(main._session_get(device_id))


def _get_dispatch(execution_id: str) -> dict | None:
    return asyncio.run(main._dispatch_get(execution_id))


# ---------------------------------------------------------------------------
# Connection / session tests
# ---------------------------------------------------------------------------

def test_ws_connect_creates_session():
    with TestClient(app) as client:
        with client.websocket_connect("/api/v2/agents/ws/device-ws-1") as ws:
            session = _get_session("device-ws-1")
            assert session is not None
            assert session["ws_connected"] is True
            assert session["device_id"] == "device-ws-1"


def test_ws_disconnect_marks_session_not_connected():
    with TestClient(app) as client:
        with client.websocket_connect("/api/v2/agents/ws/device-ws-2"):
            assert _get_session("device-ws-2")["ws_connected"] is True
        # After context exit the WS closes and the handler's finally block runs.
        session = _get_session("device-ws-2")
        assert session is not None
        assert session["ws_connected"] is False


def test_ws_reconnect_updates_session():
    _seed_session("device-ws-r")
    with TestClient(app) as client:
        with client.websocket_connect("/api/v2/agents/ws/device-ws-r") as ws:
            session = _get_session("device-ws-r")
            assert session["ws_connected"] is True


# ---------------------------------------------------------------------------
# Push replay on connect
# ---------------------------------------------------------------------------

def test_ws_pending_dispatch_replayed_on_connect():
    _seed_session("device-ws-3")
    _seed_dispatch("exec-ws-1", "device-ws-3")

    with TestClient(app) as client:
        with client.websocket_connect("/api/v2/agents/ws/device-ws-3") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "control"
            assert msg["execution_id"] == "exec-ws-1"
            assert msg["device_id"] == "device-ws-3"
            assert msg["payload"]["command"] == "ping"


def test_ws_replay_multiple_pending_dispatches():
    _seed_session("device-ws-4")
    _seed_dispatch("exec-ws-m1", "device-ws-4")
    _seed_dispatch("exec-ws-m2", "device-ws-4")

    with TestClient(app) as client:
        with client.websocket_connect("/api/v2/agents/ws/device-ws-4") as ws:
            ids = set()
            for _ in range(2):
                msg = ws.receive_json()
                assert msg["type"] == "control"
                ids.add(msg["execution_id"])
            assert ids == {"exec-ws-m1", "exec-ws-m2"}


def test_ws_replay_only_sends_own_device_dispatches():
    """Dispatch for a different device must not be replayed to this agent."""
    _seed_dispatch("exec-other", "device-other")

    with TestClient(app) as client:
        with client.websocket_connect("/api/v2/agents/ws/device-ws-5") as ws:
            # No dispatch replayed — the only pending one belongs to device-other.
            # Trigger a ping to prove the connection is live and we get a pong.
            ws.send_json({"type": "ping"})
            msg = ws.receive_json()
            assert msg["type"] == "pong"

    # Dispatch for other device is still in cache.
    assert _get_dispatch("exec-other") is not None


# ---------------------------------------------------------------------------
# ACK → dispatch cleared (at-least-once delivery)
# ---------------------------------------------------------------------------

def test_ws_ack_removes_dispatch_from_cache():
    _seed_session("device-ws-6")
    _seed_dispatch("exec-ws-ack", "device-ws-6")

    with TestClient(app) as client:
        with client.websocket_connect("/api/v2/agents/ws/device-ws-6") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "control"
            ws.send_json({"type": "ack", "execution_id": "exec-ws-ack"})
            # Give the handler a moment to process the ack.
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"

    assert _get_dispatch("exec-ws-ack") is None


def test_ws_unacked_dispatch_survives_reconnect():
    """Dispatch that was pushed but not ACKed is replayed after reconnect."""
    _seed_session("device-ws-7")
    _seed_dispatch("exec-ws-noack", "device-ws-7")

    with TestClient(app) as client:
        # First connection: receive push, but do NOT ack.
        with client.websocket_connect("/api/v2/agents/ws/device-ws-7") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "control"
            assert msg["execution_id"] == "exec-ws-noack"
            # No ack sent; dispatch remains in cache.

        assert _get_dispatch("exec-ws-noack") is not None, "un-ACKed dispatch must survive disconnect"

        # Second connection (reconnect): dispatch is replayed again.
        with client.websocket_connect("/api/v2/agents/ws/device-ws-7") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "control"
            assert msg["execution_id"] == "exec-ws-noack"


# ---------------------------------------------------------------------------
# Ping / pong keepalive
# ---------------------------------------------------------------------------

def test_ws_ping_pong():
    with TestClient(app) as client:
        with client.websocket_connect("/api/v2/agents/ws/device-ws-ping") as ws:
            ws.send_json({"type": "ping"})
            msg = ws.receive_json()
            assert msg["type"] == "pong"


# ---------------------------------------------------------------------------
# WS heartbeat
# ---------------------------------------------------------------------------

def test_ws_heartbeat_refreshes_last_seen():
    _seed_session("device-ws-hb")
    before = _get_session("device-ws-hb")["last_seen"]
    time.sleep(0.01)

    with TestClient(app) as client:
        with client.websocket_connect("/api/v2/agents/ws/device-ws-hb") as ws:
            ws.send_json({"type": "heartbeat"})
            ws.send_json({"type": "ping"})
            ws.receive_json()  # pong

    after = _get_session("device-ws-hb")["last_seen"]
    assert after >= before


# ---------------------------------------------------------------------------
# Churn survival
# ---------------------------------------------------------------------------

def test_ws_rapid_connect_disconnect_leaves_clean_state():
    for i in range(5):
        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v2/agents/ws/device-churn-{i}"):
                pass

    # All sessions should be ws_connected=False after disconnect.
    for i in range(5):
        session = _get_session(f"device-churn-{i}")
        assert session is not None
        assert session["ws_connected"] is False

    # _ws_connections dict must be empty.
    assert len(main._ws_connections) == 0


def test_ws_same_device_rapid_reconnect():
    _seed_session("device-ws-churn")
    _seed_dispatch("exec-churn", "device-ws-churn")

    with TestClient(app) as client:
        for _ in range(3):
            with client.websocket_connect("/api/v2/agents/ws/device-ws-churn") as ws:
                msg = ws.receive_json()
                assert msg["type"] == "control"
                # Don't ack — dispatch persists for next reconnect.

    # After all reconnects, dispatch still in cache (never ACKed).
    assert _get_dispatch("exec-churn") is not None
    assert main._ws_connections == {}
