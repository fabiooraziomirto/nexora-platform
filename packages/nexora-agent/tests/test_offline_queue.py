"""Unit tests for offline queue — uses in-memory SQLite."""
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture(autouse=True)
def tmp_queue(tmp_path):
    """Redirect queue DB to a temp file and reset global state between tests."""
    db_path = tmp_path / "queue.db"
    with patch("nexora_agent.config.QUEUE_DB_PATH", db_path):
        import nexora_agent.offline_queue as oq
        oq._conn = None  # force re-init
        yield oq
        if oq._conn:
            oq._conn.close()
            oq._conn = None


def test_enqueue_and_depth(tmp_queue):
    tmp_queue.enqueue("telemetry", {"samples": [{"metric": "temp", "value": 22.0}]})
    tmp_queue.enqueue("callback", {"execution_id": "eid-1", "status": "succeeded"})
    assert tmp_queue.depth() == 2


def test_peek_returns_items_in_order(tmp_queue):
    for i in range(5):
        tmp_queue.enqueue("telemetry", {"i": i})
    items = tmp_queue.peek(limit=3)
    assert len(items) == 3
    assert [it["payload"]["i"] for it in items] == [0, 1, 2]


def test_ack_removes_item(tmp_queue):
    tmp_queue.enqueue("telemetry", {"x": 1})
    items = tmp_queue.peek()
    tmp_queue.ack(items[0]["id"])
    assert tmp_queue.depth() == 0


def test_nack_increments_attempts(tmp_queue):
    tmp_queue.enqueue("telemetry", {"x": 1})
    item = tmp_queue.peek()[0]
    tmp_queue.nack(item["id"])
    item2 = tmp_queue.peek()[0]
    assert item2["attempts"] == 1


def test_nack_drops_after_max_attempts(tmp_queue):
    tmp_queue.enqueue("telemetry", {"x": 1})
    item = tmp_queue.peek()[0]
    # Simulate MAX_ATTEMPTS nacks
    for _ in range(tmp_queue._MAX_ATTEMPTS):
        tmp_queue.nack(item["id"])
    assert tmp_queue.depth() == 0


@pytest.mark.asyncio
async def test_drain_calls_send_functions(tmp_queue):
    tmp_queue.enqueue("telemetry", {"samples": []})
    tmp_queue.enqueue("callback", {"execution_id": "eid-1", "status": "succeeded"})

    calls = {"telemetry": 0, "callback": 0}

    async def send_telemetry(p):
        calls["telemetry"] += 1
        return True

    async def send_callback(p):
        calls["callback"] += 1
        return True

    await tmp_queue.drain(send_telemetry, send_callback)
    assert calls["telemetry"] == 1
    assert calls["callback"] == 1
    assert tmp_queue.depth() == 0


@pytest.mark.asyncio
async def test_drain_nacks_on_failure(tmp_queue):
    tmp_queue.enqueue("telemetry", {"samples": []})

    async def send_telemetry(p):
        return False

    async def send_callback(p):
        return True

    await tmp_queue.drain(send_telemetry, send_callback)
    items = tmp_queue.peek()
    assert len(items) == 1
    assert items[0]["attempts"] == 1
