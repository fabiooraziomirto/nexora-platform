import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ai_pipeline.db")
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("KAFKA_REQUIRED", "false")
os.environ.setdefault("AI_LLM_ENABLED", "false")

import pytest
from httpx import ASGITransport, AsyncClient

from ai_pipeline_service.core.database import Base, SessionLocal, engine
from ai_pipeline_service.core.events import process_event
import ai_pipeline_service.core.function_builder as function_builder
import ai_pipeline_service.core.risk as risk_core
from ai_pipeline_service.core.llm import fallback_summary
from ai_pipeline_service.main import app
from ai_pipeline_service.models.insight import AIInsight


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.mark.asyncio
async def test_slo_violation_creates_warning_insight():
    insight = await process_event(
        "device.slo.violated",
        {
            "device_id": "device-1",
            "slo_id": "slo-1",
            "metric": "temperature",
            "observed_value": 84.0,
            "threshold": 70.0,
            "operator": "lt",
        },
    )

    assert insight is not None
    assert insight.category == "slo_breach"
    assert insight.severity == "warning"
    assert insight.model_used == "rules"


@pytest.mark.asyncio
async def test_repeated_slo_violations_escalate_to_critical():
    payload = {
        "device_id": "device-1",
        "slo_id": "slo-1",
        "metric": "cpu",
        "observed_value": 95.0,
        "threshold": 80.0,
        "operator": "lt",
    }

    await process_event("device.slo.violated", payload)
    await process_event("device.slo.violated", payload)
    insight = await process_event("device.slo.violated", payload)

    assert insight is not None
    assert insight.severity == "critical"


@pytest.mark.asyncio
async def test_execution_failure_creates_evidence():
    insight = await process_event(
        "execution.failed",
        {
            "execution_id": "exec-1",
            "device_id": "device-2",
            "status": "failed",
            "result_stderr": "runtime error",
        },
    )

    assert insight is not None
    assert insight.category == "execution_failure"
    assert "exec-1" in insight.evidence
    assert "runtime error" in insight.evidence


@pytest.mark.asyncio
async def test_execution_callback_envelope_failure_creates_insight():
    insight = await process_event(
        "execution.callback",
        {
            "event_type": "execution.callback",
            "resource_id": "exec-2",
            "payload": {
                "id": "exec-2",
                "device_id": "device-3",
                "status": "failed",
                "result_stderr": "callback failure",
            },
        },
    )

    assert insight is not None
    assert insight.category == "execution_failure"
    assert "exec-2" in insight.evidence
    assert "callback failure" in insight.evidence


def test_fallback_summary_is_deterministic():
    summary = fallback_summary(
        "SLO breach detected",
        {"device_id": "device-1"},
        ["Check telemetry trend."],
    )

    assert "device-1" in summary
    assert "Check telemetry trend." in summary


@pytest.mark.asyncio
async def test_api_list_detail_ack_resolve_and_filters():
    with SessionLocal() as db:
        insight = AIInsight(
            id="insight-1",
            tenant_id="default",
            scope_type="device",
            scope_id="device-1",
            severity="warning",
            status="open",
            category="slo_breach",
            title="SLO breach",
            summary="Device needs review",
            evidence='{"device_id": "device-1"}',
            recommendations='["Check telemetry"]',
            model_used="rules",
        )
        db.add(insight)
        db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_resp = await client.get("/api/v2/ai/insights?severity=warning&category=slo_breach")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 1

        detail_resp = await client.get("/api/v2/ai/insights/insight-1")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["evidence"]["device_id"] == "device-1"

        ack_resp = await client.post("/api/v2/ai/insights/insight-1/ack")
        assert ack_resp.status_code == 200
        assert ack_resp.json()["status"] == "acknowledged"

        resolve_resp = await client.post("/api/v2/ai/insights/insight-1/resolve")
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["status"] == "resolved"
        assert resolve_resp.json()["resolved_at"] is not None


@pytest.mark.asyncio
async def test_enrich_insight_adds_root_cause_runbook_and_related_events():
    with SessionLocal() as db:
        db.add(AIInsight(
            id="related-1",
            tenant_id="default",
            scope_type="device",
            scope_id="device-1",
            severity="warning",
            status="open",
            category="execution_failure",
            title="Execution failure",
            summary="failed",
            evidence='{"device_id": "device-1"}',
            recommendations='["Inspect logs"]',
            model_used="rules",
        ))
        db.add(AIInsight(
            id="insight-1",
            tenant_id="default",
            scope_type="device",
            scope_id="device-1",
            severity="critical",
            status="open",
            category="slo_breach",
            title="SLO breach",
            summary="Device needs review",
            evidence='{"device_id": "device-1", "metric": "temperature"}',
            recommendations='["Check telemetry"]',
            model_used="rules",
        ))
        db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v2/ai/insights/insight-1/enrich")

    assert response.status_code == 200
    data = response.json()
    assert data["probable_cause"]
    assert data["confidence"] == "high"
    assert len(data["runbook_steps"]) >= 2
    assert data["related_events"][0]["id"] == "related-1"


@pytest.mark.asyncio
async def test_risk_score_device_high_from_insights(monkeypatch):
    async def fake_fetch_device(device_id: str):
        return {"id": device_id, "status": "online", "capabilities": {"wasm_wasi": True}}

    monkeypatch.setattr(risk_core, "fetch_device", fake_fetch_device)
    with SessionLocal() as db:
        for idx in range(3):
            db.add(AIInsight(
                id=f"risk-{idx}",
                tenant_id="default",
                scope_type="device",
                scope_id="device-risk",
                severity="critical",
                status="open",
                category="slo_breach",
                title="SLO breach",
                summary="critical",
                evidence="{}",
                recommendations="[]",
                model_used="rules",
            ))
        db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v2/ai/risk/devices/device-risk")

    assert response.status_code == 200
    data = response.json()
    assert data["level"] in {"high", "critical"}
    assert data["score"] >= 60


@pytest.mark.asyncio
async def test_ai_query_rejects_unsupported_intent():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v2/ai/query", json={"query": "delete all devices"})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_function_draft_generates_assemblyscript_metadata():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v2/ai/functions/draft",
            json={"prompt": "alert when temperature is greater than 80"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["language"] == "assemblyscript"
    assert "export function main" in data["source_code"]
    assert data["plugin_metadata"]["module_type"] == "function"
    assert data["plugin_metadata"]["runtime_type"] == "wasm-wasi"
    assert data["plugin_metadata"]["required_capabilities"] == ["wasm_wasi"]
    assert data["plugin_metadata"]["artifact_uri"] is None


@pytest.mark.asyncio
async def test_placement_excludes_offline_or_missing_wasm(monkeypatch):
    devices = {
        "good": {"id": "good", "status": "online", "capabilities": {"wasm_wasi": True}},
        "offline": {"id": "offline", "status": "offline", "capabilities": {"wasm_wasi": True}},
        "missing": {"id": "missing", "status": "online", "capabilities": {"wasm_wasi": False}},
    }

    async def fake_fetch_device(device_id: str):
        return devices[device_id]

    monkeypatch.setattr(risk_core, "fetch_device", fake_fetch_device)
    monkeypatch.setattr(function_builder, "fetch_device", fake_fetch_device)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        draft = await client.post(
            "/api/v2/ai/functions/draft",
            json={"prompt": "alert when temperature is greater than 80"},
        )
        draft_id = draft.json()["id"]
        response = await client.post(
            f"/api/v2/ai/functions/{draft_id}/placement",
            json={"candidate_device_ids": ["offline", "good", "missing"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["recommended_targets"][0]["device_id"] == "good"
    avoided = {item["device_id"] for item in data["avoid_targets"]}
    assert {"offline", "missing"} <= avoided


@pytest.mark.asyncio
async def test_manual_device_analysis_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v2/ai/analyze/device/device-123")

    assert response.status_code == 201
    data = response.json()
    assert data["scope_id"] == "device-123"
    assert data["category"] == "operational_summary"


@pytest.mark.asyncio
async def test_ready_with_kafka_disabled():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["kafka_connected"] is False
