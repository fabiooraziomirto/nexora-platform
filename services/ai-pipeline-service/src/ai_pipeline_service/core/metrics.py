from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import PlainTextResponse


HTTP_REQUESTS_TOTAL = Counter(
    "ai_pipeline_http_requests_total",
    "Total HTTP requests handled by ai-pipeline-service",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "ai_pipeline_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)

INSIGHTS_CREATED_TOTAL = Counter(
    "ai_pipeline_insights_created_total",
    "Total AI insights created",
    ["category", "severity"],
)

EVENTS_PROCESSED_TOTAL = Counter(
    "ai_pipeline_events_processed_total",
    "Total events processed by the AI pipeline",
    ["event_type"],
)


def metrics_response() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")
