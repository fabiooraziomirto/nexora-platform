from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Response
from fastapi.responses import PlainTextResponse

# Device lifecycle operation counter — tracks create/update/delete/register/heartbeat
device_operations = Counter(
    "s4t_device_operations_total",
    "Total device operations",
    ["operation", "status"],
)

# Per-operation duration histogram
device_operation_duration = Histogram(
    "s4t_device_operation_duration_seconds",
    "Device operation duration in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, float("inf")),
)

# Active devices currently in 'online' state
active_devices = Gauge(
    "s4t_active_devices_total",
    "Number of devices with status=online",
)

# Provisioning time: delta from device.created_at to first heartbeat received.
# Measures the time a new device takes to bootstrap and check in for the first time.
device_provisioning_seconds = Histogram(
    "s4t_device_provisioning_seconds",
    "Time from device registration to first heartbeat",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float("inf")),
)

# Registration type breakdown: new vs re-register
device_registrations_total = Counter(
    "s4t_device_registrations_total",
    "Device agent registrations",
    ["registration_type"],  # new | re_register
)

# Heartbeat counter — useful for computing churn rate in Prometheus
device_heartbeats_total = Counter(
    "s4t_device_heartbeats_total",
    "Device heartbeat calls received",
    ["status"],  # ok | not_found
)


def setup_metrics() -> None:
    active_devices.set(0)


def get_metrics_response() -> Response:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")
