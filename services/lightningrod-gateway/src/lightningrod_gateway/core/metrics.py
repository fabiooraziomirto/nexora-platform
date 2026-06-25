from prometheus_client import Counter, Gauge, Histogram

DISPATCH_EVENTS_TOTAL = Counter(
    "s4t_lr_dispatch_events_total",
    "Total dispatch events consumed from Kafka",
    ["service"],
)
DELIVERY_ATTEMPTS_TOTAL = Counter(
    "s4t_lr_delivery_attempts_total",
    "Total delivery attempts to edge agents",
    ["service", "device_id"],
)
DELIVERY_FAILURES_TOTAL = Counter(
    "s4t_lr_delivery_failures_total",
    "Total delivery failures after retries exhausted",
    ["service", "device_id"],
)
AGENT_SESSIONS_GAUGE = Gauge(
    "s4t_lr_agent_sessions",
    "Number of currently registered agent sessions",
    ["service"],
)
PENDING_DISPATCH_GAUGE = Gauge(
    "s4t_lr_pending_dispatches",
    "Number of pending dispatches in cache",
    ["service"],
)
PER_DEVICE_PENDING_GAUGE = Gauge(
    "s4t_lr_per_device_pending_dispatches",
    "Pending dispatches per device",
    ["service", "device_id"],
)
REQUEST_DURATION = Histogram(
    "s4t_lr_request_duration_seconds",
    "HTTP request duration",
    ["service", "method", "path"],
)
# End-to-end dispatch latency: from kafka_dispatched_at to agent delivery.
DISPATCH_LATENCY = Histogram(
    "s4t_execution_dispatch_latency_seconds",
    "End-to-end dispatch latency from Kafka publish to agent delivery",
    ["service"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float("inf")),
)
# Phase 1a: time from Kafka publish to broker timestamp.
# Enable LogAppendTime on the topic for true network+commit lag measurement:
#   kafka-configs.sh --bootstrap-server kafka:29092 --entity-type topics \
#     --entity-name stack4things.execution.dispatched --alter \
#     --add-config message.timestamp.type=LogAppendTime
# Negative values indicate clock skew between producer host and broker.
BROKER_COMMIT_LAG = Histogram(
    "s4t_lr_kafka_broker_lag_seconds",
    "Lag between producer kafka_dispatched_at and Kafka broker record timestamp (msg.timestamp)",
    ["service"],
    buckets=(-0.1, -0.025, -0.005, -0.001, 0.0, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, float("inf")),
)
# Phase 1b: time from Kafka publish to gateway consumer receive.
KAFKA_INGESTION_LATENCY = Histogram(
    "s4t_lr_kafka_ingestion_latency_seconds",
    "Kafka broker-to-consumer ingestion latency for dispatch events",
    ["service"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, float("inf")),
)
# Phase 2: time a dispatch event waits in gateway cache before delivery.
QUEUE_WAIT = Histogram(
    "s4t_lr_dispatch_queue_wait_seconds",
    "Time a dispatch event waits in the gateway cache before agent delivery",
    ["service"],
    buckets=(0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float("inf")),
)
