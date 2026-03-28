from httpx import ASGITransport, AsyncClient
import pytest

from main import app, SessionLocal, Execution, ACTIVE_STATUSES

transport = ASGITransport(app=app)


async def _client():
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_execution_crud() -> None:
    async with await _client() as client:
        create_resp = await client.post("/api/v2/executions", json={"device_id": "d1", "command": "ping"})
        assert create_resp.status_code == 201
        data = create_resp.json()
        execution_id = data["id"]
        assert data["status"] == "queued"
        assert data["correlation_id"] is not None
        assert data["created_at"] is not None

        list_resp = await client.get("/api/v2/executions")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1

        get_resp = await client.get(f"/api/v2/executions/{execution_id}")
        assert get_resp.status_code == 200

        del_resp = await client.delete(f"/api/v2/executions/{execution_id}")
        assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_dispatch_callback_lifecycle() -> None:
    async with await _client() as client:
        create_resp = await client.post("/api/v2/executions", json={"device_id": "d-life", "command": "ls"})
        assert create_resp.status_code == 201
        eid = create_resp.json()["id"]

        dispatch_resp = await client.post(f"/api/v2/executions/{eid}/dispatch")
        assert dispatch_resp.status_code == 200
        assert dispatch_resp.json()["status"] == "dispatched"
        assert dispatch_resp.json()["dispatched_at"] is not None

        cb_running = await client.post(f"/api/v2/executions/{eid}/callback", json={"status": "running"})
        assert cb_running.status_code == 200
        assert cb_running.json()["status"] == "running"

        cb_done = await client.post(
            f"/api/v2/executions/{eid}/callback",
            json={"status": "succeeded", "exit_code": 0, "stdout": "ok", "stderr": ""},
        )
        assert cb_done.status_code == 200
        result = cb_done.json()
        assert result["status"] == "succeeded"
        assert result["exit_code"] == 0
        assert result["result_stdout"] == "ok"

        await client.delete(f"/api/v2/executions/{eid}")


@pytest.mark.asyncio
async def test_idempotency_key() -> None:
    async with await _client() as client:
        payload = {"device_id": "d-idem", "command": "echo hi", "idempotency_key": "idem-unique-1"}
        r1 = await client.post("/api/v2/executions", json=payload)
        assert r1.status_code == 201
        r2 = await client.post("/api/v2/executions", json=payload)
        assert r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"]

        await client.delete(f"/api/v2/executions/{r1.json()['id']}")


@pytest.mark.asyncio
async def test_callback_rejects_unknown_fields() -> None:
    async with await _client() as client:
        r = await client.post("/api/v2/executions", json={"device_id": "d-unk", "command": "x"})
        eid = r.json()["id"]
        await client.post(f"/api/v2/executions/{eid}/dispatch")

        bad = await client.post(
            f"/api/v2/executions/{eid}/callback",
            json={"status": "running", "malicious_field": "pwned"},
        )
        assert bad.status_code == 422
        assert "unknown fields" in bad.json()["detail"]

        await client.delete(f"/api/v2/executions/{eid}")


@pytest.mark.asyncio
async def test_callback_failed_scenario() -> None:
    async with await _client() as client:
        r = await client.post("/api/v2/executions", json={"device_id": "d-fail", "command": "bad"})
        eid = r.json()["id"]
        await client.post(f"/api/v2/executions/{eid}/dispatch")

        cb = await client.post(
            f"/api/v2/executions/{eid}/callback",
            json={"status": "failed", "exit_code": 1, "stderr": "segfault"},
        )
        assert cb.status_code == 200
        assert cb.json()["status"] == "failed"
        assert cb.json()["exit_code"] == 1
        assert cb.json()["result_stderr"] == "segfault"

        await client.delete(f"/api/v2/executions/{eid}")


@pytest.mark.asyncio
async def test_per_device_queue_limit_429(monkeypatch) -> None:
    monkeypatch.setattr("main.MAX_EXECUTIONS_PER_DEVICE", 2)
    async with await _client() as client:
        ids = []
        for i in range(2):
            r = await client.post("/api/v2/executions", json={"device_id": "d-limit", "command": f"cmd{i}"})
            assert r.status_code == 201
            ids.append(r.json()["id"])

        over = await client.post("/api/v2/executions", json={"device_id": "d-limit", "command": "overflow"})
        assert over.status_code == 429
        assert "active executions" in over.json()["detail"]

        for eid in ids:
            await client.delete(f"/api/v2/executions/{eid}")


@pytest.mark.asyncio
async def test_invalid_transition_409() -> None:
    async with await _client() as client:
        r = await client.post("/api/v2/executions", json={"device_id": "d-trans", "command": "x"})
        eid = r.json()["id"]

        bad = await client.post(
            f"/api/v2/executions/{eid}/callback",
            json={"status": "succeeded"},
        )
        assert bad.status_code == 409

        await client.delete(f"/api/v2/executions/{eid}")


@pytest.mark.asyncio
async def test_cancel_execution() -> None:
    async with await _client() as client:
        r = await client.post("/api/v2/executions", json={"device_id": "d-cancel", "command": "x"})
        eid = r.json()["id"]

        cancel = await client.post(f"/api/v2/executions/{eid}/cancel")
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "cancelled"

        cancel_again = await client.post(f"/api/v2/executions/{eid}/cancel")
        assert cancel_again.status_code == 409

        await client.delete(f"/api/v2/executions/{eid}")


@pytest.mark.asyncio
async def test_timeout_candidate_logic() -> None:
    """Verify that the timeout loop picks up dispatched executions with expired timestamps."""
    from datetime import datetime, timezone, timedelta
    from main import _timeout_loop, EXECUTION_DISPATCHED_TIMEOUT_SECONDS

    async with await _client() as client:
        r = await client.post("/api/v2/executions", json={"device_id": "d-to", "command": "sleep"})
        eid = r.json()["id"]
        await client.post(f"/api/v2/executions/{eid}/dispatch")

    with SessionLocal() as db:
        ex = db.get(Execution, eid)
        ex.dispatched_at = datetime.now(timezone.utc) - timedelta(seconds=EXECUTION_DISPATCHED_TIMEOUT_SECONDS + 60)
        db.commit()

    import main
    orig = main.EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS
    main.EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS = 0

    import asyncio

    async def _run_once():
        task = asyncio.create_task(_timeout_loop())
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await _run_once()
    main.EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS = orig

    async with await _client() as client:
        get = await client.get(f"/api/v2/executions/{eid}")
        assert get.json()["status"] == "timeout"
        await client.delete(f"/api/v2/executions/{eid}")
