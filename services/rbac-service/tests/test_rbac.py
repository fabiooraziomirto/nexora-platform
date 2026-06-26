"""
Tests for the rbac-service policy engine and authorize API.
Cache and audit are disabled (POLICY_CACHE_ENABLED=false, AUDIT_ENABLED=false).
"""
import json

import pytest
from fastapi.testclient import TestClient

from rbac_service.main import app
from rbac_service.core.policy_engine import PolicyEngine

client = TestClient(app)


# ── PolicyEngine unit tests ───────────────────────────────────────────────────

def test_admin_role_always_allowed():
    eng = PolicyEngine()
    assert eng.authorize("u1", "alice", ["admin"], "delete", "device") is True


def test_non_admin_denied_by_default():
    eng = PolicyEngine()
    assert eng.authorize("u2", "bob", ["reader"], "delete", "device") is False


def test_engine_ready():
    assert PolicyEngine().is_ready() is True


def test_list_roles_contains_admin():
    names = {r["name"] for r in PolicyEngine().list_roles()}
    assert "admin" in names and "auditor" in names


def test_custom_policy_grants_reader(tmp_path, monkeypatch):
    pol = tmp_path / "policy.json"
    pol.write_text(json.dumps({"device:read": "role:reader"}))
    monkeypatch.setenv("POLICY_FILE", str(pol))
    eng = PolicyEngine()
    assert eng.authorize("u3", "carol", ["reader"], "read", "device") is True
    # A role not granted by the rule is still denied.
    assert eng.authorize("u4", "dave", ["member"], "read", "device") is False


# ── Authorize API ─────────────────────────────────────────────────────────────

def test_authorize_endpoint_allow():
    r = client.post("/api/v2/rbac/authorize", json={
        "user_id": "u1", "user_name": "alice", "roles": ["admin"],
        "action": "delete", "resource_type": "device",
    })
    assert r.status_code == 200
    assert r.json()["allowed"] is True


def test_authorize_endpoint_deny():
    r = client.post("/api/v2/rbac/authorize", json={
        "user_id": "u2", "user_name": "bob", "roles": ["reader"],
        "action": "delete", "resource_type": "device",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is False
    assert body["reason"]


def test_health_and_ready():
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_roles_endpoint():
    r = client.get("/api/v2/rbac/roles")
    assert r.status_code == 200
    assert any(role["name"] == "admin" for role in r.json()["roles"])
