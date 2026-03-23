from httpx import AsyncClient
import pytest

from main import app


@pytest.mark.asyncio
async def test_execution_crud() -> None:
    async with AsyncClient(app=app, base_url="http://test") as client:
        create_resp = await client.post("/api/v2/executions", json={"device_id": "d1", "command": "ping"})
        assert create_resp.status_code == 201
        execution_id = create_resp.json()["id"]

        list_resp = await client.get("/api/v2/executions")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1

        get_resp = await client.get(f"/api/v2/executions/{execution_id}")
        assert get_resp.status_code == 200

        del_resp = await client.delete(f"/api/v2/executions/{execution_id}")
        assert del_resp.status_code == 204
