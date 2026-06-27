from httpx import ASGITransport, AsyncClient
import pytest

from plugin_service.main import app

transport = ASGITransport(app=app)


@pytest.mark.asyncio
async def test_health() -> None:
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "plugin-service"


@pytest.mark.asyncio
async def test_plugin_crud_minimal() -> None:
    async with AsyncClient(transport=transport, base_url="http://test") as client:
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


@pytest.mark.asyncio
async def test_function_activation_requires_sbom_and_scan_pass() -> None:
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v2/plugins",
            json={
                "name": "demo-fn",
                "module_type": "function",
                "artifact_uri": "oci://registry.example/nexora/demo-fn:1.0.0",
                "entrypoint": "_start",
            },
        )
        assert create_resp.status_code == 201
        plugin_id = create_resp.json()["id"]

        missing_sbom = await client.patch(f"/api/v2/plugins/{plugin_id}/activate")
        assert missing_sbom.status_code == 400
        assert "sbom_uri" in missing_sbom.json()["detail"]

        scan_failed = await client.post(
            f"/api/v2/plugins/{plugin_id}/security/scan",
            json={
                "scan_tool": "grype",
                "sbom_uri": "s3://sbom/demo-fn-1.0.0.cdx.json",
                "vulnerability_counts": {"critical": 1, "high": 0, "medium": 0, "low": 0},
            },
        )
        assert scan_failed.status_code == 200
        assert scan_failed.json()["security_scan_status"] == "failed"

        blocked = await client.patch(f"/api/v2/plugins/{plugin_id}/activate")
        assert blocked.status_code == 409
        assert "security scan must pass" in blocked.json()["detail"]

        scan_passed = await client.post(
            f"/api/v2/plugins/{plugin_id}/security/scan",
            json={
                "scan_tool": "grype",
                "sbom_uri": "s3://sbom/demo-fn-1.0.0.cdx.json",
                "vulnerability_counts": {"critical": 0, "high": 0, "medium": 2, "low": 1},
            },
        )
        assert scan_passed.status_code == 200
        assert scan_passed.json()["security_scan_status"] == "passed"

        activate_resp = await client.patch(f"/api/v2/plugins/{plugin_id}/activate")
        assert activate_resp.status_code == 200
        assert activate_resp.json()["status"] == "active"
