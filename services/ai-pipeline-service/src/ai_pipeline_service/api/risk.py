from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ai_pipeline_service.core.database import SessionLocal
from ai_pipeline_service.core.jsonutil import json_load
from ai_pipeline_service.core.risk import compute_and_store_device_risk, compute_and_store_fleet_risk

router = APIRouter()


class RiskResponse(BaseModel):
    scope_type: str
    scope_id: str
    score: int
    level: str
    evidence: dict[str, Any]
    updated_at: str


class RecomputeRequest(BaseModel):
    scope_type: str
    scope_id: str


def _risk_response(row) -> RiskResponse:
    return RiskResponse(
        scope_type=row.scope_type,
        scope_id=row.scope_id,
        score=int(row.score),
        level=row.level,
        evidence=json_load(row.evidence, {}),
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


@router.get("/api/v2/ai/risk/devices/{device_id}", response_model=RiskResponse)
async def get_device_risk(device_id: str) -> RiskResponse:
    with SessionLocal() as db:
        row = await compute_and_store_device_risk(db, device_id)
        return _risk_response(row)


@router.get("/api/v2/ai/risk/fleets/{fleet_id}", response_model=RiskResponse)
async def get_fleet_risk(fleet_id: str) -> RiskResponse:
    with SessionLocal() as db:
        row = await compute_and_store_fleet_risk(db, fleet_id)
        return _risk_response(row)


@router.post("/api/v2/ai/risk/recompute", response_model=RiskResponse)
async def recompute_risk(body: RecomputeRequest) -> RiskResponse:
    with SessionLocal() as db:
        if body.scope_type == "fleet":
            row = await compute_and_store_fleet_risk(db, body.scope_id)
        else:
            row = await compute_and_store_device_risk(db, body.scope_id)
        return _risk_response(row)
