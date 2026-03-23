from httpx import AsyncClient
import pytest

from main import app


@pytest.mark.asyncio
async def test_dns_record_crud() -> None:
    async with AsyncClient(app=app, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v2/dns/records", json={"name": "test.example.org", "type": "A", "value": "10.0.0.2"}
        )
        assert create_resp.status_code == 201
        record_id = create_resp.json()["id"]

        list_resp = await client.get("/api/v2/dns/records")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1

        get_resp = await client.get(f"/api/v2/dns/records/{record_id}")
        assert get_resp.status_code == 200

        del_resp = await client.delete(f"/api/v2/dns/records/{record_id}")
        assert del_resp.status_code == 204
