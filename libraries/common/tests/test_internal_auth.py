"""Tests for common.internal_auth — validates both sending and receiving sides."""
import pytest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# _is_valid_internal_key
# ---------------------------------------------------------------------------

def test_valid_key_accepted():
    with patch.dict("os.environ", {"INTERNAL_SERVICE_KEY": "my-secret"}):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)
        assert m._is_valid_internal_key("my-secret") is True


def test_wrong_key_rejected():
    with patch.dict("os.environ", {"INTERNAL_SERVICE_KEY": "my-secret"}):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)
        assert m._is_valid_internal_key("wrong") is False


def test_no_key_configured_always_passes():
    with patch.dict("os.environ", {}, clear=True):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)
        assert m._is_valid_internal_key(None) is True
        assert m._is_valid_internal_key("anything") is True


# ---------------------------------------------------------------------------
# _is_valid_bootstrap_token
# ---------------------------------------------------------------------------

def test_valid_bootstrap_token():
    env = {
        "INTERNAL_SERVICE_KEY": "key",
        "AGENT_BOOTSTRAP_TOKENS": "bridge:secret:4102444800",
    }
    with patch.dict("os.environ", env):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)
        assert m._is_valid_bootstrap_token("bridge:secret") is True


def test_wrong_bootstrap_token():
    env = {
        "INTERNAL_SERVICE_KEY": "key",
        "AGENT_BOOTSTRAP_TOKENS": "bridge:secret:4102444800",
    }
    with patch.dict("os.environ", env):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)
        assert m._is_valid_bootstrap_token("bridge:wrong") is False


def test_expired_bootstrap_token_rejected():
    env = {
        "INTERNAL_SERVICE_KEY": "key",
        "AGENT_BOOTSTRAP_TOKENS": "bridge:secret:1",  # expiry in 1970
    }
    with patch.dict("os.environ", env):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)
        assert m._is_valid_bootstrap_token("bridge:secret") is False


# ---------------------------------------------------------------------------
# internal_headers()
# ---------------------------------------------------------------------------

def test_internal_headers_when_key_set():
    with patch.dict("os.environ", {"INTERNAL_SERVICE_KEY": "abc"}):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)
        assert m.internal_headers() == {"X-Internal-Key": "abc"}


def test_internal_headers_empty_when_no_key():
    with patch.dict("os.environ", {}, clear=True):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)
        assert m.internal_headers() == {}


# ---------------------------------------------------------------------------
# FastAPI dependency integration
# ---------------------------------------------------------------------------

def _make_app(key: str, tokens: str):
    env = {}
    if key:
        env["INTERNAL_SERVICE_KEY"] = key
    if tokens:
        env["AGENT_BOOTSTRAP_TOKENS"] = tokens

    with patch.dict("os.environ", env):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)

        app = FastAPI()

        @app.post("/callback")
        async def callback(_: None = m.require_internal_or_bootstrap.__wrapped__ if hasattr(m.require_internal_or_bootstrap, "__wrapped__") else None):
            return {"ok": True}

        # Re-apply dependency with reloaded module
        from fastapi import Depends
        app2 = FastAPI()

        @app2.post("/callback")
        async def callback2(auth=Depends(m.require_internal_or_bootstrap)):
            return {"ok": True}

        return app2, m


def test_fastapi_dep_accepts_valid_internal_key():
    with patch.dict("os.environ", {"INTERNAL_SERVICE_KEY": "s3cr3t"}):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)
        from fastapi import Depends, FastAPI
        app = FastAPI()

        @app.post("/cb")
        async def cb(_=Depends(m.require_internal_or_bootstrap)):
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post("/cb", headers={"x-internal-key": "s3cr3t"})
        assert resp.status_code == 200


def test_fastapi_dep_rejects_missing_credentials():
    with patch.dict("os.environ", {"INTERNAL_SERVICE_KEY": "s3cr3t"}):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)
        from fastapi import Depends, FastAPI
        app = FastAPI()

        @app.post("/cb")
        async def cb(_=Depends(m.require_internal_or_bootstrap)):
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/cb")
        assert resp.status_code == 403


def test_fastapi_dep_accepts_valid_bootstrap_token():
    env = {
        "INTERNAL_SERVICE_KEY": "s3cr3t",
        "AGENT_BOOTSTRAP_TOKENS": "dev:tok:4102444800",
    }
    with patch.dict("os.environ", env):
        import importlib
        import common.internal_auth as m
        importlib.reload(m)
        from fastapi import Depends, FastAPI
        app = FastAPI()

        @app.post("/cb")
        async def cb(_=Depends(m.require_internal_or_bootstrap)):
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post("/cb", headers={"x-bootstrap-token": "dev:tok"})
        assert resp.status_code == 200
