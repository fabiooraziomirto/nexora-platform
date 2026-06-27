from typing import Any

import httpx

from ai_pipeline_service.core.config import settings


def fallback_summary(title: str, evidence: dict[str, Any], recommendations: list[str]) -> str:
    scope = evidence.get("device_id") or evidence.get("execution_id") or evidence.get("scope_id")
    first_action = recommendations[0] if recommendations else "Review the evidence and monitor the scope."
    if scope:
        return f"{title}. Scope {scope} needs operator review. Recommended next step: {first_action}"
    return f"{title}. Recommended next step: {first_action}"


async def summarize_with_ollama(
    title: str,
    category: str,
    severity: str,
    evidence: dict[str, Any],
    recommendations: list[str],
) -> tuple[str, str]:
    if not settings.AI_LLM_ENABLED:
        return fallback_summary(title, evidence, recommendations), "rules"

    prompt = (
        "You are Nexora's local AIOps assistant. Write one concise operational "
        "summary for an edge IoT operator. Do not invent actions beyond the "
        "recommendations. Keep it under 70 words.\n\n"
        f"Title: {title}\nCategory: {category}\nSeverity: {severity}\n"
        f"Evidence: {evidence}\nRecommendations: {recommendations}\n"
    )
    try:
        async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
            )
            response.raise_for_status()
            data = response.json()
            summary = (data.get("response") or "").strip()
            if summary:
                return summary, settings.OLLAMA_MODEL
    except Exception:
        pass

    return fallback_summary(title, evidence, recommendations), "rules"
