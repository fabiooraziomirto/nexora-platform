from httpx import ASGITransport, AsyncClient
import pytest

from main import app

transport = ASGITransport(app=app)


def _client() -> AsyncClient:
    return AsyncClient(transport=transport, base_url="http://test")


async def _create(client, name="alpha"):
    return await client.post("/api/v2/fleets", json={"name": name})


@pytest.mark.asyncio
async def test_create_and_get():
    async with _client() as c:
        r = await _create(c, "fleet-cg")
        assert r.status_code == 201
        fid = r.json()["id"]
        g = await c.get(f"/api/v2/fleets/{fid}")
        assert g.status_code == 200
        assert g.json()["name"] == "fleet-cg"


@pytest.mark.asyncio
async def test_list_returns_total():
    async with _client() as c:
        await _create(c, "fleet-list")
        r = await c.get("/api/v2/fleets")
        assert r.status_code == 200
        assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_patch_updates_name():
    async with _client() as c:
        fid = (await _create(c, "before")).json()["id"]
        p = await c.patch(f"/api/v2/fleets/{fid}", json={"name": "after"})
        assert p.status_code == 200
        assert p.json()["name"] == "after"


@pytest.mark.asyncio
async def test_member_add_list_remove():
    async with _client() as c:
        fid = (await _create(c, "fleet-members")).json()["id"]
        a = await c.post(f"/api/v2/fleets/{fid}/members", json={"device_id": "dev-1"})
        assert a.status_code == 201

        lst = await c.get(f"/api/v2/fleets/{fid}/members")
        assert lst.status_code == 200
        assert lst.json()["total"] == 1

        rm = await c.delete(f"/api/v2/fleets/{fid}/members/dev-1")
        assert rm.status_code == 204


@pytest.mark.asyncio
async def test_member_duplicate_409():
    async with _client() as c:
        fid = (await _create(c, "fleet-dup")).json()["id"]
        await c.post(f"/api/v2/fleets/{fid}/members", json={"device_id": "dev-x"})
        dup = await c.post(f"/api/v2/fleets/{fid}/members", json={"device_id": "dev-x"})
        assert dup.status_code == 409


@pytest.mark.asyncio
async def test_member_requires_device_id():
    async with _client() as c:
        fid = (await _create(c, "fleet-nodev")).json()["id"]
        r = await c.post(f"/api/v2/fleets/{fid}/members", json={})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_add_member_to_missing_fleet_404():
    async with _client() as c:
        r = await c.post("/api/v2/fleets/nope/members", json={"device_id": "d"})
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_then_404():
    async with _client() as c:
        fid = (await _create(c, "fleet-del")).json()["id"]
        assert (await c.delete(f"/api/v2/fleets/{fid}")).status_code == 204
        assert (await c.get(f"/api/v2/fleets/{fid}")).status_code == 404


@pytest.mark.asyncio
async def test_get_missing_404():
    async with _client() as c:
        assert (await c.get("/api/v2/fleets/nope")).status_code == 404
