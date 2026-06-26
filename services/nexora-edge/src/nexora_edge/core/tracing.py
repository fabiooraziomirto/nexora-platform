"""
OpenTelemetry setup for nexora-edge.

Context is extracted from the "traceparent" field in incoming Kafka envelopes
(injected by execution-service) and used to create child spans for delivery.
"""
import os
import logging
from contextlib import nullcontext
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
except ImportError:
    trace = None
    SERVICE_NAME = "service.name"
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    ConsoleSpanExporter = None
    TraceContextTextMapPropagator = None

logger = logging.getLogger("nexora-edge")

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() == "true"
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
SERVICE = "nexora-edge"

class _NoopSpan:
    def get_span_context(self):
        return type("SpanContext", (), {"trace_id": 0})()


class _NoopTracer:
    def start_as_current_span(self, *args: Any, **kwargs: Any):
        return nullcontext(_NoopSpan())


class _NoopTrace:
    @staticmethod
    def get_tracer(service: str) -> _NoopTracer:
        return _NoopTracer()

    @staticmethod
    def get_current_span() -> _NoopSpan:
        return _NoopSpan()

    @staticmethod
    def set_tracer_provider(provider: Any) -> None:
        return None


class _NoopPropagator:
    def extract(self, carrier: dict) -> None:
        return None


_trace_api = trace or _NoopTrace()
_propagator = TraceContextTextMapPropagator() if TraceContextTextMapPropagator else _NoopPropagator()
tracer = _trace_api.get_tracer(SERVICE)


def setup_tracing() -> None:
    global tracer
    if trace is None:
        tracer = _NoopTracer()
        logger.info("OpenTelemetry not installed; tracing disabled")
        return

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


def extract_trace_context(carrier: dict) -> Any:
    """Extract W3C traceparent from a Kafka envelope dict."""
    return _propagator.extract(carrier)
