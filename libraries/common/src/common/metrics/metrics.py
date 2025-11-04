"""
Prometheus metrics utilities.
"""

from typing import Optional, Dict, Any
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import Response

from common.config import settings
from common.logging import get_logger

logger = get_logger(__name__)


class Metrics:
    """Prometheus metrics manager."""

    def __init__(self, prefix: str = "stack4things"):
        self.prefix = prefix
        self._counters: Dict[str, Counter] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._summaries: Dict[str, Summary] = {}

    def counter(
        self,
        name: str,
        documentation: str = "",
        labelnames: Optional[tuple] = None,
    ) -> Counter:
        """Get or create counter metric."""
        full_name = f"{self.prefix}_{name}"
        
        if full_name not in self._counters:
            self._counters[full_name] = Counter(
                full_name,
                documentation,
                labelnames=labelnames or [],
            )
        
        return self._counters[full_name]

    def histogram(
        self,
        name: str,
        documentation: str = "",
        labelnames: Optional[tuple] = None,
        buckets: Optional[tuple] = None,
    ) -> Histogram:
        """Get or create histogram metric."""
        full_name = f"{self.prefix}_{name}"
        
        if full_name not in self._histograms:
            default_buckets = buckets or (
                0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0
            )
            
            self._histograms[full_name] = Histogram(
                full_name,
                documentation,
                labelnames=labelnames or [],
                buckets=default_buckets,
            )
        
        return self._histograms[full_name]

    def gauge(
        self,
        name: str,
        documentation: str = "",
        labelnames: Optional[tuple] = None,
    ) -> Gauge:
        """Get or create gauge metric."""
        full_name = f"{self.prefix}_{name}"
        
        if full_name not in self._gauges:
            self._gauges[full_name] = Gauge(
                full_name,
                documentation,
                labelnames=labelnames or [],
            )
        
        return self._gauges[full_name]

    def summary(
        self,
        name: str,
        documentation: str = "",
        labelnames: Optional[tuple] = None,
    ) -> Summary:
        """Get or create summary metric."""
        full_name = f"{self.prefix}_{name}"
        
        if full_name not in self._summaries:
            self._summaries[full_name] = Summary(
                full_name,
                documentation,
                labelnames=labelnames or [],
            )
        
        return self._summaries[full_name]

    def get_metrics_response(self) -> Response:
        """Get Prometheus metrics response."""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )


# Global metrics instance
_metrics: Optional[Metrics] = None


def get_metrics(prefix: str = "stack4things") -> Metrics:
    """Get or create global metrics instance."""
    global _metrics
    
    if _metrics is None:
        _metrics = Metrics(prefix=prefix)
    
    return _metrics


# Common metric decorators

def track_request_duration(metrics: Metrics, endpoint: str):
    """Decorator to track request duration."""
    histogram = metrics.histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        labelnames=("method", "endpoint", "status"),
    )
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                status_code = getattr(result, "status_code", 200)
                
                histogram.labels(
                    method=kwargs.get("method", "GET"),
                    endpoint=endpoint,
                    status=status_code,
                ).observe(time.time() - start_time)
                
                return result
            except Exception as e:
                histogram.labels(
                    method=kwargs.get("method", "GET"),
                    endpoint=endpoint,
                    status=500,
                ).observe(time.time() - start_time)
                raise
        
        return wrapper
    return decorator


def track_request_count(metrics: Metrics):
    """Decorator to track request count."""
    counter = metrics.counter(
        "http_requests_total",
        "Total HTTP requests",
        labelnames=("method", "endpoint", "status"),
    )
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                status_code = getattr(result, "status_code", 200)
                
                counter.labels(
                    method=kwargs.get("method", "GET"),
                    endpoint=kwargs.get("endpoint", "unknown"),
                    status=status_code,
                ).inc()
                
                return result
            except Exception as e:
                counter.labels(
                    method=kwargs.get("method", "GET"),
                    endpoint=kwargs.get("endpoint", "unknown"),
                    status=500,
                ).inc()
                raise
        
        return wrapper
    return decorator

