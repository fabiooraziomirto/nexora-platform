from httpx import AsyncClient
import pytest

from plugin_service.main import app


@pytest.mark.asyncio
async def test_health() -> None:
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "plugin-service"


@pytest.mark.asyncio
async def test_plugin_crud_minimal() -> None:
    async with AsyncClient(app=app, base_url="http://test") as client:
        create_resp = await client.post("/api/v2/plugins", json={"name": "demo-plugin"})
        assert create_resp.status_code == 201
        plugin_id = create_resp.json()["id"]

        list_resp = await client.get("/api/v2/plugins")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1

        get_resp = await client.get(f"/api/v2/plugins/{plugin_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "demo-plugin"

        del_resp = await client.delete(f"/api/v2/plugins/{plugin_id}")
        assert del_resp.status_code == 204
