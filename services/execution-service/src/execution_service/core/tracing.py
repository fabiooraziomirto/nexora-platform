"""
OpenTelemetry setup for execution-service.

Initialises a TracerProvider backed by an OTLP/gRPC exporter.
When OTEL_ENABLED=false (default in tests) the SDK is still initialised
but uses a NoOpTracer so instrumentation code is safe to call unconditionally.

Context propagation across Kafka uses W3C TraceContext injected as the
"traceparent" string field inside the Kafka envelope payload.
"""
import os
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger("execution-service")

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() == "true"
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
SERVICE = "execution-service"

_propagator = TraceContextTextMapPropagator()
tracer: trace.Tracer = trace.get_tracer(SERVICE)


def setup_tracing() -> None:
    global tracer
    resource = Resource.create({SERVICE_NAME: SERVICE})
    provider = TracerProvider(resource=resource)

    if OTEL_ENABLED and OTEL_EXPORTER_OTLP_ENDPOINT:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OpenTelemetry OTLP exporter configured: %s", OTEL_EXPORTER_OTLP_ENDPOINT)
        except Exception:
            logger.warning("OTLP exporter setup failed — falling back to console", exc_info=True)
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif OTEL_ENABLED:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("OpenTelemetry console exporter active (set OTEL_EXPORTER_OTLP_ENDPOINT for Jaeger)")

    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(SERVICE)


def inject_trace_context(carrier: dict) -> None:
    """Inject W3C traceparent into a dict (Kafka envelope field)."""
    _propagator.inject(carrier)


def extract_trace_context(carrier: dict) -> "trace.Context":
    """Extract W3C traceparent from a dict and return an OTel context."""
    return _propagator.extract(carrier)
