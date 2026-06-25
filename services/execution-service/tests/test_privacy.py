"""
Tests for execution-service privacy filtering.

Verifies that:
- owner sees full payload (level 4: stdout/stderr visible)
- non-owner in same tenant sees command history only (level 3: stdout/stderr masked)
- non-owner in different tenant gets 404
- list_executions filters by owner_id for non-operators
"""
import os

os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS", "600")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_execution_privacy.db")
os.environ.setdefault("AUTH_ENABLED", "false")

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


from starlette.datastructures import State
from starlette.types import ASGIApp, Receive, Scope, Send


class InjectState:
    """ASGI middleware that pre-injects a fixed identity into request.state.

    Must run BEFORE FastAPI's auth_middleware. When auth_middleware checks
    getattr(request.state, "user_id", None) and finds it set, it skips the
    default dev-user override and passes through directly.
    """

    def __init__(self, app: ASGIApp, user_id: str, tenant_id: str, is_operator: bool = False):
        self.app = app
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.is_operator = is_operator

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            state = State()
            state.user_id = self.user_id
            state.tenant_id = self.tenant_id
            state.is_operator = self.is_operator
            scope["state"] = state
        await self.app(scope, receive, send)


def make_client(user_id: str, tenant_id: str, is_operator: bool = False) -> AsyncClient:
    wrapped = InjectState(app, user_id=user_id, tenant_id=tenant_id, is_operator=is_operator)
    return AsyncClient(transport=ASGITransport(app=wrapped), base_url="http://test")


@pytest.fixture(autouse=True)
def cleanup_db():
    # Truncate between tests regardless of which SQLite file the engine is using.
    from execution_service.core.database import engine
    from execution_service.models.execution import Execution
    from sqlalchemy import delete

    with engine.begin() as conn:
        conn.execute(delete(Execution))
    yield
    with engine.begin() as conn:
        conn.execute(delete(Execution))


@pytest.mark.asyncio
async def test_owner_sees_full_payload():
    """Owner (level 4) receives stdout and stderr."""
    async with make_client("alice", "tenant-a") as owner_client:
        create = await owner_client.post(
            "/api/v2/executions",
            json={"device_id": "dev-1", "command": "ls"},
        )
        assert create.status_code == 201
        exec_id = create.json()["id"]

        # Simulate callback with output
        await owner_client.post(
            f"/api/v2/executions/{exec_id}/dispatch"
        )
        await owner_client.post(
            f"/api/v2/executions/{exec_id}/callback",
            json={"status": "running"},
        )
        await owner_client.post(
            f"/api/v2/executions/{exec_id}/callback",
            json={"status": "succeeded", "exit_code": 0, "stdout": "hello", "stderr": ""},
        )

        # Owner reads back — should see full payload
        get = await owner_client.get(f"/api/v2/executions/{exec_id}")
        assert get.status_code == 200
        data = get.json()
        assert data["result_stdout"] == "hello"
        assert data["exit_code"] == 0


@pytest.mark.asyncio
async def test_same_tenant_non_owner_sees_masked_payload():
    """Non-owner in same tenant sees command history (level 3) — no stdout/stderr."""
    async with make_client("alice", "tenant-a") as owner_client:
        create = await owner_client.post(
            "/api/v2/executions",
            json={"device_id": "dev-1", "command": "whoami"},
        )
        exec_id = create.json()["id"]
        await owner_client.post(f"/api/v2/executions/{exec_id}/dispatch")
        await owner_client.post(
            f"/api/v2/executions/{exec_id}/callback",
            json={"status": "running"},
        )
        await owner_client.post(
            f"/api/v2/executions/{exec_id}/callback",
            json={"status": "succeeded", "stdout": "secret-output"},
        )

    async with make_client("bob", "tenant-a") as viewer_client:
        get = await viewer_client.get(f"/api/v2/executions/{exec_id}")
        assert get.status_code == 200
        data = get.json()
        # Level 3: can see command, status, timestamps — not the payload
        assert data["command"] == "whoami"
        assert data["status"] == "succeeded"
        assert data["result_stdout"] is None
        assert data["exit_code"] is None


@pytest.mark.asyncio
async def test_different_tenant_gets_404():
    """Non-owner from different tenant receives 404."""
    async with make_client("alice", "tenant-a") as owner_client:
        create = await owner_client.post(
            "/api/v2/executions",
            json={"device_id": "dev-1", "command": "secret"},
        )
        exec_id = create.json()["id"]

    async with make_client("charlie", "tenant-b") as outsider_client:
        get = await outsider_client.get(f"/api/v2/executions/{exec_id}")
        assert get.status_code == 404


@pytest.mark.asyncio
async def test_operator_sees_full_payload_all_tenants():
    """Platform operator sees all executions with full payload."""
    async with make_client("alice", "tenant-a") as owner_client:
        create = await owner_client.post(
            "/api/v2/executions",
            json={"device_id": "dev-1", "command": "top-secret"},
        )
        exec_id = create.json()["id"]
        await owner_client.post(f"/api/v2/executions/{exec_id}/dispatch")
        await owner_client.post(
            f"/api/v2/executions/{exec_id}/callback",
            json={"status": "running"},
        )
        await owner_client.post(
            f"/api/v2/executions/{exec_id}/callback",
            json={"status": "succeeded", "stdout": "classified"},
        )

    async with make_client("ops", "ops-tenant", is_operator=True) as ops_client:
        get = await ops_client.get(f"/api/v2/executions/{exec_id}")
        assert get.status_code == 200
        # Operator sees full payload
        assert get.json()["result_stdout"] == "classified"

        # Operator sees all executions in list
        listing = await ops_client.get("/api/v2/executions")
        assert listing.json()["total"] >= 1


@pytest.mark.asyncio
async def test_list_executions_filters_by_owner():
    """Non-operator sees only their own executions in the list."""
    async with make_client("alice", "tenant-a") as alice_client:
        await alice_client.post(
            "/api/v2/executions",
            json={"device_id": "dev-alice", "command": "alice-cmd"},
        )

    async with make_client("bob", "tenant-a") as bob_client:
        await bob_client.post(
            "/api/v2/executions",
            json={"device_id": "dev-bob", "command": "bob-cmd"},
        )
        listing = await bob_client.get("/api/v2/executions")
        items = listing.json()["items"]
        # Bob sees only his own execution
        assert all(i["owner_id"] == "bob" for i in items)
        assert len(items) == 1
