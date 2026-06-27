from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ai_pipeline_service.api.insights import insight_to_response
from ai_pipeline_service.core.database import SessionLocal
from ai_pipeline_service.models.insight import AIInsight

router = APIRouter()


class AIQueryRequest(BaseModel):
    query: str


class AIQueryResponse(BaseModel):
    intent: str
    answer: str
    items: list[dict[str, Any]]


def _intent(query: str) -> str:
    q = query.lower()
    if any(word in q for word in {"delete", "remove", "deploy", "create", "update", "modify", "cancel"}):
        return "unsupported"
    if "critical" in q or "critici" in q:
        return "list_critical_insights"
    if "risky" in q or "risch" in q:
        return "show_risky_devices"
    if "failure" in q or "failed" in q or "fall" in q:
        return "show_recent_failures"
    if "device" in q or "dispositivo" in q:
        return "explain_device"
    if "fleet" in q:
        return "summarize_fleet"
    return "unsupported"


@router.post("/api/v2/ai/query", response_model=AIQueryResponse)
async def ai_query(body: AIQueryRequest) -> AIQueryResponse:
    intent = _intent(body.query)
    if intent == "unsupported":
        raise HTTPException(status_code=400, detail="unsupported query intent")
    with SessionLocal() as db:
        q = select(AIInsight).order_by(AIInsight.created_at.desc()).limit(10)
        if intent == "list_critical_insights":
            q = q.where(AIInsight.severity == "critical")
        elif intent == "show_recent_failures":
            q = q.where(AIInsight.category == "execution_failure")
        elif intent == "show_risky_devices":
            q = q.where(AIInsight.severity.in_(["critical", "warning"]))
        items = db.execute(q).scalars().all()
    payload = [insight_to_response(item).model_dump(mode="json") for item in items]
    return AIQueryResponse(
        intent=intent,
        answer=f"Found {len(payload)} matching operational records for intent {intent}.",
        items=payload,
    )
