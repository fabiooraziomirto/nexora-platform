import json
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_pipeline_service.core.config import settings
from ai_pipeline_service.models.insight import AIInsight, AIRiskScore


def risk_level(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def compute_device_risk(db: Session, device_id: str, device: dict[str, Any] | None = None) -> dict[str, Any]:
    insights = db.execute(
        select(AIInsight)
        .where(AIInsight.scope_type == "device", AIInsight.scope_id == device_id)
        .order_by(AIInsight.created_at.desc())
        .limit(50)
    ).scalars().all()
    score = 0
    reasons: list[str] = []
    if device:
        status = device.get("status")
        if status == "offline":
            score += 30
            reasons.append("device offline")
        elif status == "unknown":
            score += 15
            reasons.append("device status unknown")
        caps = device.get("capabilities") or {}
        if not caps.get("wasm_wasi"):
            score += 10
            reasons.append("missing wasm_wasi capability")
    for insight in insights:
        if insight.status == "resolved":
            continue
        if insight.severity == "critical":
            score += 25
        elif insight.severity == "warning":
            score += 12
        else:
            score += 4
        if insight.category == "delivery_risk":
            reasons.append("recent delivery risk")
        elif insight.category == "execution_failure":
            reasons.append("recent execution failure")
        elif insight.category == "slo_breach":
            reasons.append("recent SLO breach")
    score = min(score, 100)
    evidence = {
        "device_id": device_id,
        "insight_count": len(insights),
        "device_status": (device or {}).get("status"),
        "reasons": sorted(set(reasons)),
    }
    return {"scope_type": "device", "scope_id": device_id, "score": score, "level": risk_level(score), "evidence": evidence}


async def fetch_device(device_id: str) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{settings.DEVICE_SERVICE_URL}/api/v2/devices/{device_id}")
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        return None
    return None


async def fetch_fleet_members(fleet_id: str) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.FLEET_SERVICE_URL}/api/v2/fleets/{fleet_id}/members")
        if resp.status_code == 200:
            data = resp.json()
            return [item["device_id"] for item in data.get("items", data.get("members", []))]
    except Exception:
        return []
    return []


def upsert_risk_score(db: Session, payload: dict[str, Any]) -> AIRiskScore:
    risk_id = f"{payload['scope_type']}:{payload['scope_id']}"
    row = db.get(AIRiskScore, risk_id)
    now = datetime.now(timezone.utc)
    if not row:
        row = AIRiskScore(id=risk_id, scope_type=payload["scope_type"], scope_id=payload["scope_id"])
        db.add(row)
    row.score = str(payload["score"])
    row.level = payload["level"]
    row.evidence = json.dumps(payload["evidence"], default=str)
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return row


async def compute_and_store_device_risk(db: Session, device_id: str) -> AIRiskScore:
    device = await fetch_device(device_id)
    return upsert_risk_score(db, compute_device_risk(db, device_id, device))


async def compute_and_store_fleet_risk(db: Session, fleet_id: str) -> AIRiskScore:
    device_ids = await fetch_fleet_members(fleet_id)
    device_scores: list[dict[str, Any]] = []
    for device_id in device_ids:
        device = await fetch_device(device_id)
        device_scores.append(compute_device_risk(db, device_id, device))
    if device_scores:
        avg = round(sum(item["score"] for item in device_scores) / len(device_scores))
        worst = max(item["score"] for item in device_scores)
        score = min(100, round(avg * 0.7 + worst * 0.3))
    else:
        score = 20
    return upsert_risk_score(
        db,
        {
            "scope_type": "fleet",
            "scope_id": fleet_id,
            "score": score,
            "level": risk_level(score),
            "evidence": {"fleet_id": fleet_id, "devices": device_scores, "device_count": len(device_scores)},
        },
    )
