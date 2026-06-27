from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai_pipeline_service.core.database import SessionLocal
from ai_pipeline_service.core.function_builder import build_draft, placement_for_draft
from ai_pipeline_service.core.jsonutil import json_load
from ai_pipeline_service.models.insight import AIFunctionDraft

router = APIRouter()


class FunctionDraftRequest(BaseModel):
    prompt: str = Field(..., min_length=5)
    constraints: dict[str, Any] | None = None


class PlacementRequest(BaseModel):
    candidate_device_ids: list[str] = Field(default_factory=list)


class FunctionDraftResponse(BaseModel):
    id: str
    prompt: str
    function_name: str
    language: str
    source_code: str
    plugin_metadata: dict[str, Any]
    input_schema: dict[str, Any]
    review: dict[str, Any]
    placement_result: dict[str, Any] | None
    status: str


def draft_to_response(draft: AIFunctionDraft) -> FunctionDraftResponse:
    return FunctionDraftResponse(
        id=draft.id,
        prompt=draft.prompt,
        function_name=draft.function_name,
        language=draft.language,
        source_code=draft.source_code,
        plugin_metadata=json_load(draft.plugin_metadata, {}),
        input_schema=json_load(draft.input_schema, {}),
        review=json_load(draft.review, {}),
        placement_result=json_load(draft.placement_result, None),
        status=draft.status,
    )


@router.post("/api/v2/ai/functions/draft", response_model=FunctionDraftResponse, status_code=201)
async def create_function_draft(body: FunctionDraftRequest) -> FunctionDraftResponse:
    with SessionLocal() as db:
        draft = build_draft(db, body.prompt, body.constraints)
        return draft_to_response(draft)


@router.post("/api/v2/ai/functions/{draft_id}/placement")
async def calculate_placement(draft_id: str, body: PlacementRequest) -> dict[str, Any]:
    with SessionLocal() as db:
        draft = db.get(AIFunctionDraft, draft_id)
        if not draft:
            raise HTTPException(status_code=404, detail="function draft not found")
        result = await placement_for_draft(db, draft, body.candidate_device_ids)
        return result


@router.post("/api/v2/ai/functions/{draft_id}/review", response_model=FunctionDraftResponse)
async def review_function_draft(draft_id: str) -> FunctionDraftResponse:
    with SessionLocal() as db:
        draft = db.get(AIFunctionDraft, draft_id)
        if not draft:
            raise HTTPException(status_code=404, detail="function draft not found")
        review = json_load(draft.review, {})
        review["reviewed"] = True
        review.setdefault("notes", []).append("Human approval is required before creating plugin metadata or deployments.")
        import json
        from datetime import datetime, timezone
        draft.review = json.dumps(review)
        draft.status = "reviewed"
        draft.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(draft)
        return draft_to_response(draft)
