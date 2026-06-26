import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC_PREFIX = os.getenv("KAFKA_TOPIC_PREFIX", "nxr")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() == "true"
KAFKA_REQUIRED = os.getenv("KAFKA_REQUIRED", "false").lower() == "true"

MAX_DELIVERY_ATTEMPTS = int(os.getenv("MAX_DELIVERY_ATTEMPTS", "3"))
DELIVERY_BACKOFF_SECONDS = float(os.getenv("DELIVERY_BACKOFF_SECONDS", "0.5"))

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").lower() == "true"
REDIS_REQUIRED = os.getenv("REDIS_REQUIRED", "false").lower() == "true"

# Heartbeat-based TTL: session expires if not refreshed within this window.
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "300"))
# Dispatch TTL matches EXECUTION_RUNNING_TIMEOUT_SECONDS in execution-service.
DISPATCH_TTL_SECONDS = int(os.getenv("DISPATCH_TTL_SECONDS", "3600"))
