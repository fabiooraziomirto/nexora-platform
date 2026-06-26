from httpx import ASGITransport, AsyncClient
import pytest

from main import app

transport = ASGITransport(app=app)


def _client() -> AsyncClient:
    return AsyncClient(transport=transport, base_url="http://test")


async def _create(client, **over):
    body = {"name": "test.example.org", "type": "A", "value": "10.0.0.2"}
    body.update(over)
    return await client.post("/api/v2/dns/records", json=body)


@pytest.mark.asyncio
async def test_create_and_get():
    async with _client() as c:
        r = await _create(c)
        assert r.status_code == 201
        rid = r.json()["id"]
        g = await c.get(f"/api/v2/dns/records/{rid}")
        assert g.status_code == 200
        assert g.json()["name"] == "test.example.org"


@pytest.mark.asyncio
async def test_default_ttl():
    async with _client() as c:
        # ttl omitted → defaults to 300
        r = await c.post("/api/v2/dns/records",
                         json={"name": "defaults.example.org", "type": "A", "value": "10.0.0.3"})
        assert r.status_code == 201
        assert r.json()["ttl"] == 300


@pytest.mark.asyncio
async def test_list_returns_total():
    async with _client() as c:
        await _create(c)
        r = await c.get("/api/v2/dns/records")
        assert r.status_code == 200
        assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_patch_updates_value():
    async with _client() as c:
        rid = (await _create(c)).json()["id"]
        p = await c.patch(f"/api/v2/dns/records/{rid}", json={"value": "10.0.0.9", "ttl": 60})
        assert p.status_code == 200
        assert p.json()["value"] == "10.0.0.9"
        assert p.json()["ttl"] == 60


@pytest.mark.asyncio
async def test_delete_then_404():
    async with _client() as c:
        rid = (await _create(c)).json()["id"]
        assert (await c.delete(f"/api/v2/dns/records/{rid}")).status_code == 204
        assert (await c.get(f"/api/v2/dns/records/{rid}")).status_code == 404


@pytest.mark.asyncio
async def test_get_missing_404():
    async with _client() as c:
        assert (await c.get("/api/v2/dns/records/nope")).status_code == 404


@pytest.mark.asyncio
async def test_patch_missing_404():
    async with _client() as c:
        assert (await c.patch("/api/v2/dns/records/nope", json={"value": "x"})).status_code == 404


@pytest.mark.asyncio
async def test_delete_missing_404():
    async with _client() as c:
        assert (await c.delete("/api/v2/dns/records/nope")).status_code == 404
