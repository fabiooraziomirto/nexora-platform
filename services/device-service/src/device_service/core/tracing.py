"""OpenTelemetry setup for device-service."""
import os
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

logger = logging.getLogger("device-service")

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() == "true"
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
SERVICE = "device-service"

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

    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(SERVICE)
