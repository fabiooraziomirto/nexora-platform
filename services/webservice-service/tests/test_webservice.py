from httpx import ASGITransport, AsyncClient
import pytest

from main import app

transport = ASGITransport(app=app)


def _client() -> AsyncClient:
    return AsyncClient(transport=transport, base_url="http://test")


async def _create(client, **over):
    body = {"device_id": "d1", "port": 8443}
    body.update(over)
    return await client.post("/api/v2/webservices", json=body)


@pytest.mark.asyncio
async def test_create_and_get():
    async with _client() as c:
        r = await _create(c)
        assert r.status_code == 201
        wid = r.json()["id"]
        g = await c.get(f"/api/v2/webservices/{wid}")
        assert g.status_code == 200
        assert g.json()["port"] == 8443
        assert g.json()["status"] == "enabled"


@pytest.mark.asyncio
async def test_create_invalid_status_400():
    async with _client() as c:
        r = await _create(c, status="bogus")
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_returns_total():
    async with _client() as c:
        await _create(c)
        r = await c.get("/api/v2/webservices")
        assert r.status_code == 200
        assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_patch_updates_port_and_status():
    async with _client() as c:
        wid = (await _create(c)).json()["id"]
        p = await c.patch(f"/api/v2/webservices/{wid}", json={"port": 9443, "status": "disabled"})
        assert p.status_code == 200
        assert p.json()["port"] == 9443
        assert p.json()["status"] == "disabled"


@pytest.mark.asyncio
async def test_patch_invalid_status_400():
    async with _client() as c:
        wid = (await _create(c)).json()["id"]
        p = await c.patch(f"/api/v2/webservices/{wid}", json={"status": "bogus"})
        assert p.status_code == 400


@pytest.mark.asyncio
async def test_delete_then_404():
    async with _client() as c:
        wid = (await _create(c)).json()["id"]
        assert (await c.delete(f"/api/v2/webservices/{wid}")).status_code == 204
        assert (await c.get(f"/api/v2/webservices/{wid}")).status_code == 404


@pytest.mark.asyncio
async def test_get_missing_404():
    async with _client() as c:
        assert (await c.get("/api/v2/webservices/nope")).status_code == 404


@pytest.mark.asyncio
async def test_delete_missing_404():
    async with _client() as c:
        assert (await c.delete("/api/v2/webservices/nope")).status_code == 404
