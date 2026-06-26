from httpx import ASGITransport, AsyncClient
import pytest

from main import app

transport = ASGITransport(app=app)


def _client() -> AsyncClient:
    return AsyncClient(transport=transport, base_url="http://test")


async def _create(client, **over):
    body = {"device_id": "d1", "network_id": "n1"}
    body.update(over)
    return await client.post("/api/v2/ports", json=body)


@pytest.mark.asyncio
async def test_create_and_get():
    async with _client() as c:
        r = await _create(c)
        assert r.status_code == 201
        pid = r.json()["id"]
        g = await c.get(f"/api/v2/ports/{pid}")
        assert g.status_code == 200
        assert g.json()["device_id"] == "d1"
        assert g.json()["status"] == "created"


@pytest.mark.asyncio
async def test_list_returns_total():
    async with _client() as c:
        await _create(c)
        r = await c.get("/api/v2/ports")
        assert r.status_code == 200
        assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_patch_updates_ip_and_network():
    async with _client() as c:
        pid = (await _create(c)).json()["id"]
        p = await c.patch(f"/api/v2/ports/{pid}", json={"ip_address": "10.1.2.3", "network_id": "n2"})
        assert p.status_code == 200
        assert p.json()["ip_address"] == "10.1.2.3"
        assert p.json()["network_id"] == "n2"


@pytest.mark.asyncio
async def test_patch_invalid_status_400():
    async with _client() as c:
        pid = (await _create(c)).json()["id"]
        p = await c.patch(f"/api/v2/ports/{pid}", json={"status": "bogus"})
        assert p.status_code == 400


@pytest.mark.asyncio
async def test_delete_then_404():
    async with _client() as c:
        pid = (await _create(c)).json()["id"]
        assert (await c.delete(f"/api/v2/ports/{pid}")).status_code == 204
        assert (await c.get(f"/api/v2/ports/{pid}")).status_code == 404


@pytest.mark.asyncio
async def test_get_missing_404():
    async with _client() as c:
        assert (await c.get("/api/v2/ports/nope")).status_code == 404


@pytest.mark.asyncio
async def test_patch_missing_404():
    async with _client() as c:
        assert (await c.patch("/api/v2/ports/nope", json={"ip_address": "x"})).status_code == 404


@pytest.mark.asyncio
async def test_delete_missing_404():
    async with _client() as c:
        assert (await c.delete("/api/v2/ports/nope")).status_code == 404
