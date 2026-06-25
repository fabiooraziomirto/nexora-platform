from prometheus_client import Counter, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "s4t_http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "s4t_http_request_duration_seconds",
    "HTTP request duration",
    ["service", "method", "path"],
)
