"""
OpenTelemetry setup for nexora-edge.

Context is extracted from the "traceparent" field in incoming Kafka envelopes
(injected by execution-service) and used to create child spans for delivery.
"""
import os
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger("nexora-edge")

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() == "true"
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
SERVICE = "nexora-edge"

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


def extract_trace_context(carrier: dict) -> "trace.Context":
    """Extract W3C traceparent from a Kafka envelope dict."""
    return _propagator.extract(carrier)
