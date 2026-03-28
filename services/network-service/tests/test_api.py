from httpx import ASGITransport, AsyncClient
import pytest

from main import app

transport = ASGITransport(app=app)


@pytest.mark.asyncio
async def test_port_crud() -> None:
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/v2/ports", json={"device_id": "d1", "network_id": "n1"})
        assert create_resp.status_code == 201
        port_id = create_resp.json()["id"]

        list_resp = await client.get("/api/v2/ports")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1

        get_resp = await client.get(f"/api/v2/ports/{port_id}")
        assert get_resp.status_code == 200

        del_resp = await client.delete(f"/api/v2/ports/{port_id}")
        assert del_resp.status_code == 204
