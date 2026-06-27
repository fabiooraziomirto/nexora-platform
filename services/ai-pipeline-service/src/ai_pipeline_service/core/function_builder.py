import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ai_pipeline_service.core.risk import compute_device_risk, fetch_device
from ai_pipeline_service.models.insight import AIFunctionDraft


def slugify_name(prompt: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", prompt.lower())
    base = "_".join(words[:5]) or "ai_function"
    if not base[0].isalpha():
        base = f"fn_{base}"
    return base[:64]


def generate_assemblyscript(prompt: str, function_name: str) -> str:
    threshold_match = re.search(r"(\d+(?:\.\d+)?)", prompt)
    threshold = threshold_match.group(1) if threshold_match else "80"
    return f"""// Generated draft for Nexora. Review and compile to WASM before deployment.
export function main(inputJson: string): string {{
  const input = JSON.parse(inputJson);
  const value = Number(input.value ?? input.temperature ?? input.metric_value ?? 0);
  const threshold = Number(input.threshold ?? {threshold});
  const triggered = value > threshold;
  return JSON.stringify({{
    function_name: "{function_name}",
    status: triggered ? "alert" : "ok",
    observed_value: value,
    threshold,
    message: triggered ? "Threshold exceeded" : "Within expected range"
  }});
}}
"""


def build_draft(db: Session, prompt: str, constraints: dict[str, Any] | None = None) -> AIFunctionDraft:
    function_name = slugify_name(prompt)
    source = generate_assemblyscript(prompt, function_name)
    constraints = constraints or {}
    metadata = {
        "name": function_name,
        "version": "0.1.0",
        "module_type": "function",
        "runtime_type": "wasm-wasi",
        "entrypoint": "_start",
        "artifact_uri": None,
        "artifact_checksum": None,
        "timeout_seconds": constraints.get("timeout_seconds", 30),
        "memory_limit_mb": constraints.get("memory_limit_mb", 64),
        "permissions": [],
        "required_capabilities": ["wasm_wasi"],
    }
    input_schema = {
        "type": "object",
        "properties": {
            "value": {"type": "number"},
            "temperature": {"type": "number"},
            "threshold": {"type": "number"},
        },
        "additionalProperties": True,
    }
    review = {
        "risk": "medium",
        "notes": [
            "Draft source must be reviewed and compiled to WASM before deployment.",
            "artifact_uri and artifact_checksum are intentionally empty in v1.",
            "No network or filesystem permission is requested by default.",
        ],
        "tests": [
            "Invoke with value below threshold and expect status ok.",
            "Invoke with value above threshold and expect status alert.",
        ],
    }
    now = datetime.now(timezone.utc)
    draft = AIFunctionDraft(
        id=str(uuid4()),
        prompt=prompt,
        function_name=function_name,
        language="assemblyscript",
        source_code=source,
        plugin_metadata=json.dumps(metadata),
        input_schema=json.dumps(input_schema),
        review=json.dumps(review),
        status="draft",
        created_at=now,
        updated_at=now,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


async def placement_for_draft(
    db: Session,
    draft: AIFunctionDraft,
    candidate_device_ids: list[str],
) -> dict[str, Any]:
    recommended: list[dict[str, Any]] = []
    avoid: list[dict[str, Any]] = []
    for device_id in candidate_device_ids:
        device = await fetch_device(device_id)
        risk = compute_device_risk(db, device_id, device)
        caps = (device or {}).get("capabilities") or {}
        status = (device or {}).get("status", "unknown")
        reasons = []
        if status != "online":
            reasons.append(f"status is {status}")
        if not caps.get("wasm_wasi"):
            reasons.append("missing wasm_wasi capability")
        if risk["score"] >= 60:
            reasons.append(f"risk level is {risk['level']}")
        score = max(0, 100 - risk["score"])
        if status == "online":
            score += 10
        if caps.get("wasm_wasi"):
            score += 15
        item = {
            "device_id": device_id,
            "score": min(score, 100),
            "risk_level": risk["level"],
            "reason": ", ".join(reasons) if reasons else "online, wasm_wasi capable, acceptable recent risk",
        }
        if reasons:
            avoid.append(item)
        else:
            recommended.append(item)
    recommended.sort(key=lambda item: item["score"], reverse=True)
    avoid.sort(key=lambda item: item["score"])
    result = {"recommended_targets": recommended, "avoid_targets": avoid}
    draft.placement_result = json.dumps(result)
    draft.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(draft)
    return result
