"""
End-to-end tests for the Nexora Function Runtime.

Exercises the real wasmtime WASI backend using committed fixtures
(tests/fixtures/echo.wasm, loop.wasm). When wasmtime is unavailable the
runtime-mode assertions are skipped, but the API-contract tests still run.
"""
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

import main
from conftest import fixture_bytes

ECHO = fixture_bytes("echo.wasm")
LOOP = fixture_bytes("loop.wasm")
WASMTIME = main._wasmtime_available()
requires_wasmtime = pytest.mark.skipif(not WASMTIME, reason="wasmtime not installed")


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Isolate install dir per test.
    monkeypatch.setattr(main, "INSTALL_DIR", tmp_path)
    main._installed.clear()
    return TestClient(main.app)


def _install_local(client, wasm_bytes, monkeypatch, **overrides):
    """Install a function by stubbing the artifact download with local bytes."""
    class _Resp:
        content = wasm_bytes
        def raise_for_status(self):  # noqa: D401
            return None

    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _Resp())
    payload = {
        "id": overrides.get("id", "fn-test"),
        "name": "echo",
        "artifact_uri": "https://example.test/echo.wasm",
        "artifact_checksum": "sha256:" + hashlib.sha256(wasm_bytes).hexdigest(),
        "entrypoint": "_start",
        "permissions": overrides.get("permissions", []),
        "timeout_seconds": overrides.get("timeout_seconds", 30),
    }
    return client.post("/runtime/functions/install", json=payload)


# ── Health & runtime mode ─────────────────────────────────────────────────────

def test_health_reports_runtime_mode(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["wasm_runtime"] in {"wasmtime", "stub"}


@requires_wasmtime
def test_runtime_mode_is_wasmtime():
    assert main.runtime_mode() == "wasmtime"


def test_force_stub_env(monkeypatch):
    monkeypatch.setattr(main, "WASM_FORCE_STUB", True)
    assert main.runtime_mode() == "stub"


# ── Direct execution against real WASM ────────────────────────────────────────

@requires_wasmtime
def test_execute_wasm_echo(tmp_path):
    wasm = tmp_path / "echo.wasm"
    wasm.write_bytes(ECHO)
    result = main._execute_wasm(wasm, "_start", {"k": "v"}, 30, [])
    assert result["runtime_mode"] == "wasmtime"
    assert result["exit_code"] == 0
    assert result["function_result"]["status"] == "ok"


@requires_wasmtime
def test_execute_wasm_fuel_timeout(tmp_path):
    wasm = tmp_path / "loop.wasm"
    wasm.write_bytes(LOOP)
    # Minimum fuel budget; the infinite loop must exhaust it and trap.
    result = main._execute_wasm(wasm, "_start", {}, 1, [])
    assert result["runtime_mode"] == "wasmtime"
    assert result["exit_code"] == 1
    assert result["stderr"]


# ── Install / invoke / delete API flow ────────────────────────────────────────

def test_install_rejects_non_https(client):
    r = client.post("/runtime/functions/install", json={
        "id": "bad", "artifact_uri": "http://169.254.169.254/meta",
    })
    assert r.status_code == 400


def test_install_checksum_mismatch(client, monkeypatch):
    class _Resp:
        content = ECHO
        def raise_for_status(self):
            return None
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _Resp())
    r = client.post("/runtime/functions/install", json={
        "id": "fn", "artifact_uri": "https://example.test/x.wasm",
        "artifact_checksum": "sha256:deadbeef",
    })
    assert r.status_code == 422


@requires_wasmtime
def test_install_invoke_delete_flow(client, monkeypatch):
    r = _install_local(client, ECHO, monkeypatch, id="fn-flow")
    assert r.status_code == 201

    r = client.post("/runtime/functions/fn-flow/invoke", json={"args": {"x": 1}})
    assert r.status_code == 200
    body = r.json()
    assert body["exit_code"] == 0
    assert body["runtime_mode"] == "wasmtime"
    assert body["function_result"]["status"] == "ok"

    r = client.delete("/runtime/functions/fn-flow")
    assert r.status_code == 204
    assert client.post("/runtime/functions/fn-flow/invoke", json={}).status_code == 404


def test_invoke_missing_function(client):
    assert client.post("/runtime/functions/nope/invoke", json={}).status_code == 404


# ── API-key enforcement ───────────────────────────────────────────────────────

def test_api_key_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(main, "RUNTIME_API_KEY", "s3cret")
    main._installed.clear()
    c = TestClient(main.app)
    # No header → 401
    assert c.post("/runtime/functions/x/invoke", json={}).status_code == 401
    # Wrong header → 401
    assert c.post("/runtime/functions/x/invoke", json={},
                  headers={"X-Runtime-Api-Key": "nope"}).status_code == 401
    # Correct header → passes auth (404 because not installed)
    assert c.post("/runtime/functions/x/invoke", json={},
                  headers={"X-Runtime-Api-Key": "s3cret"}).status_code == 404
