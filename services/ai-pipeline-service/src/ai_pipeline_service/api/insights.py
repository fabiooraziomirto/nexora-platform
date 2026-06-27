import json
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_pipeline_service.core.analyzer import manual_device_analysis
from ai_pipeline_service.core.database import SessionLocal
from ai_pipeline_service.core.enrichment import enrich_insight
from ai_pipeline_service.core.jsonutil import json_load
from ai_pipeline_service.core.llm import summarize_with_ollama
from ai_pipeline_service.core.metrics import INSIGHTS_CREATED_TOTAL
from ai_pipeline_service.models.insight import AIInsight

router = APIRouter()

InsightSeverity = Literal["info", "warning", "critical"]
InsightStatus = Literal["open", "acknowledged", "resolved"]
InsightCategory = Literal[
    "anomaly",
    "slo_breach",
    "execution_failure",
    "delivery_risk",
    "operational_summary",
]


class InsightResponse(BaseModel):
    id: str
    tenant_id: str
    scope_type: str
    scope_id: str
    severity: str
    status: str
    category: str
    title: str
    summary: str
    evidence: dict[str, Any]
    recommendations: list[str]
    probable_cause: str | None = None
    confidence: str | None = None
    runbook_steps: list[str] = []
    related_events: list[dict[str, Any]] = []
    risk_score: str | None = None
    model_used: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class InsightListResponse(BaseModel):
    items: list[InsightResponse]
    total: int


def _json_load(value: str | None, default: Any) -> Any:
    return json_load(value, default)


def insight_to_response(insight: AIInsight) -> InsightResponse:
    return InsightResponse(
        id=insight.id,
        tenant_id=insight.tenant_id,
        scope_type=insight.scope_type,
        scope_id=insight.scope_id,
        severity=insight.severity,
        status=insight.status,
        category=insight.category,
        title=insight.title,
        summary=insight.summary,
        evidence=_json_load(insight.evidence, {}),
        recommendations=_json_load(insight.recommendations, []),
        probable_cause=insight.probable_cause,
        confidence=insight.confidence,
        runbook_steps=_json_load(insight.runbook_steps, []),
        related_events=_json_load(insight.related_events, []),
        risk_score=insight.risk_score,
        model_used=insight.model_used,
        created_at=insight.created_at,
        updated_at=insight.updated_at,
        resolved_at=insight.resolved_at,
    )


def create_insight_from_analysis(
    db: Session,
    analysis: dict[str, Any],
    summary: str,
    model_used: str,
    insight_id: str,
) -> AIInsight:
    now = datetime.now(timezone.utc)
    insight = AIInsight(
        id=insight_id,
        tenant_id=analysis["tenant_id"],
        scope_type=analysis["scope_type"],
        scope_id=analysis["scope_id"],
        severity=analysis["severity"],
        status="open",
        category=analysis["category"],
        title=analysis["title"],
        summary=summary,
        evidence=json.dumps(analysis["evidence"], default=str),
        recommendations=json.dumps(analysis["recommendations"]),
        model_used=model_used,
        created_at=now,
        updated_at=now,
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)
    return insight


@router.get("/api/v2/ai/insights", response_model=InsightListResponse)
async def list_insights(
    severity: InsightSeverity | None = Query(None),
    status: InsightStatus | None = Query(None),
    category: InsightCategory | None = Query(None),
    scope_type: str | None = Query(None),
    scope_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> InsightListResponse:
    conditions = []
    if severity:
        conditions.append(AIInsight.severity == severity)
    if status:
        conditions.append(AIInsight.status == status)
    if category:
        conditions.append(AIInsight.category == category)
    if scope_type:
        conditions.append(AIInsight.scope_type == scope_type)
    if scope_id:
        conditions.append(AIInsight.scope_id == scope_id)

    query = select(AIInsight)
    if conditions:
        query = query.where(*conditions)
    query = query.order_by(AIInsight.created_at.desc()).limit(limit)

    with SessionLocal() as db:
        items = db.execute(query).scalars().all()
    return InsightListResponse(items=[insight_to_response(i) for i in items], total=len(items))


@router.get("/api/v2/ai/insights/{insight_id}", response_model=InsightResponse)
async def get_insight(insight_id: str) -> InsightResponse:
    with SessionLocal() as db:
        insight = db.get(AIInsight, insight_id)
    if not insight:
        raise HTTPException(status_code=404, detail="insight not found")
    return insight_to_response(insight)


def _transition_status(insight_id: str, status: str) -> InsightResponse:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        insight = db.get(AIInsight, insight_id)
        if not insight:
            raise HTTPException(status_code=404, detail="insight not found")
        insight.status = status
        insight.updated_at = now
        if status == "resolved":
            insight.resolved_at = now
        db.commit()
        db.refresh(insight)
        return insight_to_response(insight)


@router.post("/api/v2/ai/insights/{insight_id}/ack", response_model=InsightResponse)
async def acknowledge_insight(insight_id: str) -> InsightResponse:
    return _transition_status(insight_id, "acknowledged")


@router.post("/api/v2/ai/insights/{insight_id}/resolve", response_model=InsightResponse)
async def resolve_insight(insight_id: str) -> InsightResponse:
    return _transition_status(insight_id, "resolved")


@router.post("/api/v2/ai/insights/{insight_id}/enrich", response_model=InsightResponse)
async def enrich_existing_insight(insight_id: str) -> InsightResponse:
    with SessionLocal() as db:
        insight = db.get(AIInsight, insight_id)
        if not insight:
            raise HTTPException(status_code=404, detail="insight not found")
        insight = enrich_insight(db, insight)
        return insight_to_response(insight)


@router.post("/api/v2/ai/analyze/device/{device_id}", response_model=InsightResponse, status_code=201)
async def analyze_device(device_id: str) -> InsightResponse:
    analysis = manual_device_analysis(device_id)
    summary, model_used = await summarize_with_ollama(
        analysis["title"],
        analysis["category"],
        analysis["severity"],
        analysis["evidence"],
        analysis["recommendations"],
    )
    with SessionLocal() as db:
        insight = create_insight_from_analysis(
            db,
            analysis,
            summary,
            model_used,
            insight_id=__import__("uuid").uuid4().hex,
        )
        INSIGHTS_CREATED_TOTAL.labels(insight.category, insight.severity).inc()
        return insight_to_response(insight)
