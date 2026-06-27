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
async def test_guardrails_block_command_prefix_403(monkeypatch) -> None:
    monkeypatch.setattr("main.GUARDRAILS_ENABLED", True)
    monkeypatch.setattr("main.GUARDRAILS_DENY_COMMAND_PREFIXES", ("rm ", "shutdown"))
    async with await _client() as client:
        blocked = await client.post(
            "/api/v2/executions",
            json={"device_id": "d-guard", "command": "rm -rf /tmp/demo"},
        )
        assert blocked.status_code == 403
        assert "blocked by policy" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_guardrails_block_execution_type_403(monkeypatch) -> None:
    monkeypatch.setattr("main.GUARDRAILS_ENABLED", True)
    monkeypatch.setattr("main.GUARDRAILS_BLOCKED_EXECUTION_TYPES", ("function.invoke",))
    async with await _client() as client:
        blocked = await client.post(
            "/api/v2/executions",
            json={
                "device_id": "d-guard-type",
                "execution_type": "function.invoke",
                "plugin_id": "plugin-x",
                "command": "function.invoke:plugin-x",
            },
        )
        assert blocked.status_code == 403
        assert "blocked by policy" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_guardrails_block_dispatch_for_existing_execution(monkeypatch) -> None:
    async with await _client() as client:
        created = await client.post(
            "/api/v2/executions",
            json={"device_id": "d-guard-dispatch", "command": "echo hello"},
        )
        assert created.status_code == 201
        eid = created.json()["id"]

        monkeypatch.setattr("main.GUARDRAILS_ENABLED", True)
        monkeypatch.setattr("main.GUARDRAILS_DENY_COMMAND_PREFIXES", ("echo",))

        blocked_dispatch = await client.post(f"/api/v2/executions/{eid}/dispatch")
        assert blocked_dispatch.status_code == 403
        assert "blocked by policy" in blocked_dispatch.json()["detail"]

        await client.delete(f"/api/v2/executions/{eid}")


@pytest.mark.asyncio
async def test_rollout_execution_to_fleet_canary_rings(monkeypatch) -> None:
    async def _fake_members(_fleet_id: str) -> list[str]:
        return ["d-r1", "d-r2", "d-r3", "d-r4", "d-r5"]

    monkeypatch.setattr("main._get_fleet_members", _fake_members)

    async with await _client() as client:
        resp = await client.post(
            "/api/v2/fleets/fleet-a/executions/rollout",
            json={
                "execution_type": "command",
                "command": "echo canary",
                "ring_size": 2,
                "stop_on_failure": True,
            },
        )

        assert resp.status_code == 202
        data = resp.json()
        assert data["fleet_id"] == "fleet-a"
        assert data["planned_rings"] == 3
        assert data["completed_rings"] == 3
        assert data["dispatched"] == 5
        assert data["failed"] == 0
        assert data["status"] == "rolling_out"
        assert [r["ring_size"] for r in data["rings"]] == [2, 2, 1]

        for ring in data["rings"]:
            for item in ring["results"]:
                assert item["execution_id"] is not None
                await client.delete(f"/api/v2/executions/{item['execution_id']}")


@pytest.mark.asyncio
async def test_rollout_execution_to_fleet_requires_command_for_command_type(monkeypatch) -> None:
    async def _fake_members(_fleet_id: str) -> list[str]:
        return ["d-r1"]

    monkeypatch.setattr("main._get_fleet_members", _fake_members)

    async with await _client() as client:
        resp = await client.post(
            "/api/v2/fleets/fleet-a/executions/rollout",
            json={"execution_type": "command", "ring_size": 1},
        )
        assert resp.status_code == 400
        assert "command is required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_runbook_execute_success() -> None:
    async with await _client() as client:
        resp = await client.post(
            "/api/v2/runbooks/execute",
            json={
                "name": "smoke-runbook",
                "device_id": "d-runbook-1",
                "steps": [
                    {"name": "prep", "execution_type": "command", "command": "echo prep"},
                    {"name": "verify", "execution_type": "command", "command": "echo verify"},
                ],
                "stop_on_failure": True,
            },
        )

        assert resp.status_code == 202
        data = resp.json()
        assert data["device_id"] == "d-runbook-1"
        assert data["total_steps"] == 2
        assert data["completed_steps"] == 2
        assert data["dispatched"] == 2
        assert data["failed"] == 0
        assert data["status"] == "running"

        for item in data["results"]:
            assert item["status"] == "dispatched"
            await client.delete(f"/api/v2/executions/{item['execution_id']}")


@pytest.mark.asyncio
async def test_runbook_execute_requires_non_empty_steps() -> None:
    async with await _client() as client:
        resp = await client.post(
            "/api/v2/runbooks/execute",
            json={"device_id": "d-runbook-2", "steps": []},
        )
        assert resp.status_code == 400
        assert "steps must be a non-empty list" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_drift_analyze_for_fleet(monkeypatch) -> None:
    async def _fake_members(_fleet_id: str) -> list[str]:
        return ["d-drift-1", "d-drift-2"]

    monkeypatch.setattr("main._get_fleet_members", _fake_members)

    async with await _client() as client:
        # d-drift-1 has successful install for plugin-a
        created = await client.post(
            "/api/v2/executions",
            json={
                "device_id": "d-drift-1",
                "execution_type": "function.install",
                "plugin_id": "plugin-a",
                "command": "function.install:plugin-a",
            },
        )
        assert created.status_code == 201
        eid = created.json()["id"]
        await client.post(f"/api/v2/executions/{eid}/dispatch")
        await client.post(
            f"/api/v2/executions/{eid}/callback",
            json={"status": "succeeded", "exit_code": 0, "stdout": "ok", "stderr": ""},
        )

        resp = await client.post(
            "/api/v2/drift/analyze",
            json={"fleet_id": "fleet-drift", "expected_plugins": ["plugin-a"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_devices"] == 2
        assert data["devices_with_drift"] == 1
        assert data["summary"]["missing_installs"] == 1

        d1 = next(x for x in data["devices"] if x["device_id"] == "d-drift-1")
        d2 = next(x for x in data["devices"] if x["device_id"] == "d-drift-2")
        assert d1["has_drift"] is False
        assert d2["has_drift"] is True

        await client.delete(f"/api/v2/executions/{eid}")


@pytest.mark.asyncio
async def test_drift_analyze_requires_target() -> None:
    async with await _client() as client:
        resp = await client.post(
            "/api/v2/drift/analyze",
            json={"expected_plugins": ["plugin-a"]},
        )
        assert resp.status_code == 400
        assert "provide fleet_id or non-empty device_ids" in resp.json()["detail"]


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
