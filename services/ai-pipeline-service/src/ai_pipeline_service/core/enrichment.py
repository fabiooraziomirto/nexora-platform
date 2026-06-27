import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_pipeline_service.core.jsonutil import json_load
from ai_pipeline_service.models.insight import AIInsight


def _confidence_for(insight: AIInsight, related: list[AIInsight]) -> str:
    score = 35
    if insight.severity == "critical":
        score += 30
    elif insight.severity == "warning":
        score += 15
    score += min(len(related) * 10, 30)
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _cause_for(insight: AIInsight, evidence: dict[str, Any], related: list[AIInsight]) -> str:
    if insight.category == "slo_breach":
        metric = evidence.get("metric", "the monitored metric")
        return f"{metric} breached its configured SLO and may indicate device or workload degradation."
    if insight.category == "execution_failure":
        return "Recent execution callbacks indicate runtime, command, or agent-side failures."
    if insight.category == "delivery_risk":
        return "The gateway could not reliably deliver work to the device, likely due to session or connectivity issues."
    if insight.category == "anomaly":
        return "Telemetry volume or shape differs from the expected operational pattern."
    if related:
        return "Multiple recent AI signals point to recurring operational risk on the same scope."
    return "Insufficient correlated evidence; operator review is recommended."


def _runbook_for(insight: AIInsight) -> list[str]:
    if insight.category == "slo_breach":
        return [
            "Open the device telemetry view and confirm the metric trend.",
            "Check whether the SLO threshold still matches expected operating conditions.",
            "Inspect recent executions on the same device before dispatching more work.",
            "Keep the device under observation until the metric returns inside bounds.",
        ]
    if insight.category == "execution_failure":
        return [
            "Inspect stderr, exit code, and function result for the failed execution.",
            "Verify the device agent heartbeat and runtime health.",
            "Compare the failed command or function with the last known successful execution.",
            "Retry only after connectivity and runtime state look healthy.",
        ]
    if insight.category == "delivery_risk":
        return [
            "Check the edge gateway session cache for this device.",
            "Verify the latest heartbeat timestamp.",
            "Avoid dispatching additional work until delivery stabilizes.",
        ]
    return [
        "Review the evidence attached to the insight.",
        "Check recent events and telemetry for the same scope.",
        "Escalate if the same signal repeats in the next monitoring window.",
    ]


def enrich_insight(db: Session, insight: AIInsight) -> AIInsight:
    evidence = json_load(insight.evidence, {})
    related = db.execute(
        select(AIInsight)
        .where(
            AIInsight.scope_type == insight.scope_type,
            AIInsight.scope_id == insight.scope_id,
            AIInsight.id != insight.id,
        )
        .order_by(AIInsight.created_at.desc())
        .limit(5)
    ).scalars().all()
    related_payload = [
        {
            "id": item.id,
            "category": item.category,
            "severity": item.severity,
            "title": item.title,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in related
    ]
    insight.probable_cause = _cause_for(insight, evidence, related)
    insight.confidence = _confidence_for(insight, related)
    insight.runbook_steps = json.dumps(_runbook_for(insight))
    insight.related_events = json.dumps(related_payload)
    if not insight.risk_score:
        insight.risk_score = "70" if insight.severity == "critical" else "45" if insight.severity == "warning" else "20"
    db.commit()
    db.refresh(insight)
    return insight
