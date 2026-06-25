from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Response
from fastapi.responses import PlainTextResponse

# Metrics
device_operations = Counter(
    "device_operations_total",
    "Total device operations",
    ["operation", "status"]
)

device_operation_duration = Histogram(
    "device_operation_duration_seconds",
    "Device operation duration",
    ["operation"]
)

active_devices = Gauge(
    "active_devices_total",
    "Total number of active devices"
)


def setup_metrics() -> None:
    active_devices.set(0)


def get_metrics_response() -> Response:
    """Get Prometheus metrics endpoint response."""
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")

