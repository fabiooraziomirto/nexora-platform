from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_pipeline_service.core.config import settings
from ai_pipeline_service.models.insight import AIInsight


def _tenant(payload: dict[str, Any]) -> str:
    return str(payload.get("tenant_id") or payload.get("payload", {}).get("tenant_id") or "default")


def _event_body(payload: dict[str, Any]) -> dict[str, Any]:
    body = payload.get("payload")
    return body if isinstance(body, dict) else payload


def _count_recent(
    db: Session,
    *,
    scope_type: str,
    scope_id: str,
    category: str,
    since: datetime,
) -> int:
    return db.execute(
        select(func.count())
        .select_from(AIInsight)
        .where(
            AIInsight.scope_type == scope_type,
            AIInsight.scope_id == scope_id,
            AIInsight.category == category,
            AIInsight.created_at >= since,
        )
    ).scalar() or 0


def analyze_event(event_type: str, payload: dict[str, Any], db: Session) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=settings.REPEATED_EVENT_WINDOW_MINUTES)
    body = _event_body(payload)

    if event_type == "device.slo.violated":
        device_id = str(body.get("device_id") or "unknown")
        metric = str(body.get("metric") or "unknown")
        recent = _count_recent(
            db,
            scope_type="device",
            scope_id=device_id,
            category="slo_breach",
            since=window_start,
        )
        severity = "critical" if recent + 1 >= settings.REPEATED_EVENT_THRESHOLD else "warning"
        title = f"SLO breach detected for {metric}"
        return {
            "tenant_id": _tenant(payload),
            "scope_type": "device",
            "scope_id": device_id,
            "severity": severity,
            "category": "slo_breach",
            "title": title,
            "evidence": {
                "event_type": event_type,
                "device_id": device_id,
                "slo_id": body.get("slo_id"),
                "metric": metric,
                "observed_value": body.get("observed_value"),
                "threshold": body.get("threshold"),
                "operator": body.get("operator"),
                "violated_at": body.get("violated_at"),
                "recent_similar_count": recent + 1,
            },
            "recommendations": [
                "Check the device telemetry trend and confirm whether the SLO threshold is still valid.",
                "Inspect the edge runtime and device connectivity before dispatching additional work.",
                "Keep the device under observation until the metric returns inside the expected range.",
            ],
        }

    if event_type in {"execution.failed", "execution.timeout", "execution.callback"}:
        status = str(body.get("status") or payload.get("action") or "")
        if event_type == "execution.callback" and status not in {"failed", "timeout"}:
            return None
        execution_id = str(
            body.get("execution_id")
            or body.get("id")
            or payload.get("resource_id")
            or "unknown"
        )
        device_id = str(body.get("device_id") or "unknown")
        recent = _count_recent(
            db,
            scope_type="device",
            scope_id=device_id,
            category="execution_failure",
            since=window_start,
        )
        severity = "critical" if recent + 1 >= settings.REPEATED_EVENT_THRESHOLD else "warning"
        title = "Execution failure pattern detected"
        return {
            "tenant_id": _tenant(payload),
            "scope_type": "device",
            "scope_id": device_id,
            "severity": severity,
            "category": "execution_failure",
            "title": title,
            "evidence": {
                "event_type": event_type,
                "execution_id": execution_id,
                "device_id": device_id,
                "status": status,
                "error": body.get("error") or body.get("result_stderr"),
                "recent_similar_count": recent + 1,
            },
            "recommendations": [
                "Inspect execution stderr and runtime logs for this device.",
                "Retry the execution only after confirming the agent session is healthy.",
                "Compare recent failures against plugin or command changes.",
            ],
        }

    if event_type == "device.telemetry.ingested":
        sample_count = int(body.get("sample_count") or 0)
        metrics = body.get("metrics") or {}
        if sample_count >= 500 or len(metrics) >= 20:
            device_id = str(body.get("device_id") or "unknown")
            return {
                "tenant_id": _tenant(payload),
                "scope_type": "device",
                "scope_id": device_id,
                "severity": "info",
                "category": "anomaly",
                "title": "High-volume telemetry ingest observed",
                "evidence": {
                    "event_type": event_type,
                    "device_id": device_id,
                    "sample_count": sample_count,
                    "metrics": metrics,
                    "ingested_at": body.get("ingested_at"),
                },
                "recommendations": [
                    "Verify that the telemetry batch size is expected for this device.",
                    "Consider defining SLOs for the highest-volume metrics.",
                ],
            }
        return None

    if event_type in {"delivery_failed", "execution.delivery_failed"}:
        device_id = str(body.get("device_id") or "unknown")
        return {
            "tenant_id": _tenant(payload),
            "scope_type": "device",
            "scope_id": device_id,
            "severity": "warning",
            "category": "delivery_risk",
            "title": "Command delivery failure detected",
            "evidence": {
                "event_type": event_type,
                "device_id": device_id,
                "execution_id": body.get("execution_id") or payload.get("resource_id"),
                "error": body.get("error") or body.get("reason"),
            },
            "recommendations": [
                "Verify the edge agent session and heartbeat for this device.",
                "Check gateway delivery retries before creating more executions.",
            ],
        }

    return None


def manual_device_analysis(device_id: str) -> dict[str, Any]:
    return {
        "tenant_id": "default",
        "scope_type": "device",
        "scope_id": device_id,
        "severity": "info",
        "category": "operational_summary",
        "title": "Manual device analysis requested",
        "evidence": {
            "device_id": device_id,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "source": "manual",
        },
        "recommendations": [
            "Review latest telemetry and SLO violations for this device.",
            "Check recent executions before dispatching new commands.",
            "Keep the device under observation if new warnings appear.",
        ],
    }
