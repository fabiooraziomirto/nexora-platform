"""Unit tests for nexora-runtime — no real WASM file needed."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr("nexora_runtime.function_store.STORE_DIR", tmp_path / "functions")
    return tmp_path / "functions"


@pytest.fixture
def client(tmp_store):
    import sys, os
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# function_store unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_install_downloads_and_stores(tmp_store):
    from nexora_runtime import function_store
    wasm_bytes = b"\x00asm\x01\x00\x00\x00"  # minimal WASM header
    checksum = "sha256:" + __import__("hashlib").sha256(wasm_bytes).hexdigest()

    with patch("nexora_runtime.function_store.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.content = wasm_bytes
        mock_client.get = AsyncMock(return_value=mock_resp)

        meta = await function_store.install(
            function_id="fn-test-001",
            artifact_uri="https://example.com/fn.wasm",
            checksum=checksum,
        )

    assert meta["function_id"] == "fn-test-001"
    assert meta["size_bytes"] == len(wasm_bytes)
    assert function_store.is_installed("fn-test-001")


@pytest.mark.asyncio
async def test_install_checksum_mismatch(tmp_store):
    from nexora_runtime import function_store
    wasm_bytes = b"\x00asm\x01\x00\x00\x00"

    with patch("nexora_runtime.function_store.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.content = wasm_bytes
        mock_client.get = AsyncMock(return_value=mock_resp)

        with pytest.raises(function_store.ChecksumMismatch):
            await function_store.install(
                function_id="fn-bad-checksum",
                artifact_uri="https://example.com/fn.wasm",
                checksum="sha256:deadbeefdeadbeef",
            )


def test_list_installed_empty(tmp_store):
    from nexora_runtime import function_store
    assert function_store.list_installed() == []


def test_uninstall_removes_files(tmp_store):
    from nexora_runtime import function_store
    fn_dir = tmp_store / "fn-to-remove"
    fn_dir.mkdir(parents=True)
    (fn_dir / "function.wasm").write_bytes(b"\x00asm")
    (fn_dir / "meta.json").write_text('{"function_id": "fn-to-remove"}')

    assert function_store.is_installed("fn-to-remove")
    function_store.uninstall("fn-to-remove")
    assert not function_store.is_installed("fn-to-remove")


# ---------------------------------------------------------------------------
# wasm_executor mock mode tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invoke_mock_mode(tmp_store):
    from nexora_runtime import function_store, wasm_executor

    # Install a fake function
    fn_dir = tmp_store / "fn-mock"
    fn_dir.mkdir(parents=True)
    (fn_dir / "function.wasm").write_bytes(b"\x00asm")
    import json as _json
    (fn_dir / "meta.json").write_text(_json.dumps({
        "function_id": "fn-mock",
        "timeout_ms": 5000,
        "memory_mb": 32,
    }))

    with patch.object(wasm_executor, "_WASMTIME_AVAILABLE", False):
        result = await wasm_executor.invoke("fn-mock", {"x": 42})

    assert result["output"]["mock"] is True
    assert result["output"]["args"]["x"] == 42


@pytest.mark.asyncio
async def test_invoke_function_not_found(tmp_store):
    from nexora_runtime import function_store, wasm_executor
    with pytest.raises(function_store.FunctionNotFound):
        await wasm_executor.invoke("nonexistent-fn", {})


# ---------------------------------------------------------------------------
# HTTP API tests
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "wasmtime_available" in data


def test_list_functions_empty(client):
    resp = client.get("/runtime/functions")
    assert resp.status_code == 200
    assert resp.json()["functions"] == []


def test_invoke_not_installed_returns_404(client):
    resp = client.post("/runtime/functions/nonexistent/invoke", json={"args": {}})
    assert resp.status_code == 404


def test_uninstall_not_installed_returns_404(client):
    resp = client.delete("/runtime/functions/nonexistent")
    assert resp.status_code == 404
