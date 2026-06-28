"""matter-bridge — Nexora Matter protocol gateway.

Bridges Matter (CHIP) devices into the Nexora platform:
  - Commissioning: POST /commission starts CHIP pairing, registers device on device-service
  - Attribute subscription: streams cluster attribute changes → Kafka telemetry + device shadow
  - Command dispatch: consumes nxr.execution.dispatched → Matter cluster invocations

Depends on python-matter-server running as a sidecar (MATTER_SERVER_URL).
Falls back to mock/simulation mode when matter-server is unreachable (dev/CI).
"""
import logging
import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from prometheus_client import generate_latest, Counter, Gauge

from matter_bridge.core import config
from matter_bridge.core.commission import start_commissioning, get_session, list_sessions
from matter_bridge.core.attribute_watcher import start_watcher, set_kafka_producer
from matter_bridge.core.command_handler import start_consumer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("matter-bridge")

# ---------------------------------------------------------------------------
# Optional dependencies (graceful degradation)
# ---------------------------------------------------------------------------

matter_client: Any = None
kafka_producer: Any = None
kafka_consumer: Any = None

COMMISSIONING_TOTAL = Counter(
    "matter_bridge_commissioning_total",
    "Total commissioning attempts",
    ["status"],
)
ACTIVE_NODES = Gauge("matter_bridge_active_nodes", "Matter nodes currently commissioned")


async def _connect_matter_server() -> Any:
    """Try to connect to python-matter-server. Returns None if unavailable."""
    try:
        from matter_server.client.client import MatterClient
        import aiohttp

        session = aiohttp.ClientSession()
        client = MatterClient(config.MATTER_SERVER_URL, session)
        await client.connect()
        logger.info("Connected to matter-server", url=config.MATTER_SERVER_URL)
        return client
    except ImportError:
        logger.warning(
            "python-matter-server not installed — running in mock mode. "
            "Install 'python-matter-server' for real Matter support."
        )
        return None
    except Exception as exc:
        logger.warning(
            "matter-server unreachable — running in mock mode",
            url=config.MATTER_SERVER_URL,
            error=str(exc),
        )
        return None


async def _connect_kafka():
    """Try to connect Kafka producer and consumer. Returns (None, None) if disabled."""
    if not config.KAFKA_ENABLED:
        return None, None
    try:
        import aiokafka

        producer = aiokafka.AIOKafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        )
        await producer.start()

        topic = f"{config.KAFKA_TOPIC_PREFIX}.execution.dispatched"
        consumer = aiokafka.AIOKafkaConsumer(
            topic,
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
            group_id="matter-bridge",
            auto_offset_reset="latest",
        )
        await consumer.start()

        logger.info("Kafka connected", topic=topic)
        return producer, consumer
    except Exception as exc:
        logger.warning("Kafka unavailable — telemetry publishing disabled", error=str(exc))
        return None, None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global matter_client, kafka_producer, kafka_consumer

    matter_client = await _connect_matter_server()
    kafka_producer, kafka_consumer = await _connect_kafka()

    set_kafka_producer(kafka_producer)

    await start_watcher(matter_client)
    if kafka_consumer is not None:
        await start_consumer(matter_client, kafka_consumer)

    logger.info(
        "matter-bridge ready",
        matter_mode="real" if matter_client else "mock",
        kafka="enabled" if kafka_producer else "disabled",
    )

    yield

    if kafka_consumer:
        await kafka_consumer.stop()
    if kafka_producer:
        await kafka_producer.stop()
    if matter_client:
        try:
            await matter_client.disconnect()
        except Exception:
            pass


app = FastAPI(title="Nexora Matter Bridge", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CommissionRequest(BaseModel):
    commissioning_id: str
    setup_code: str | None = None
    manual_code: str | None = None
    name: str
    description: str | None = None
    owner_id: str
    tenant_id: str | None = None


class CommissionResponse(BaseModel):
    commissioning_id: str
    status: str
    node_id: int | None = None
    device_id: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "matter_mode": "real" if matter_client else "mock",
        "kafka": "enabled" if kafka_producer else "disabled",
    }


@app.get("/ready")
async def ready():
    return {"status": "ok"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return generate_latest()


@app.post("/commission", response_model=CommissionResponse, status_code=202)
async def commission(body: CommissionRequest):
    """Start Matter commissioning for a device.

    Called by device-service when an owner initiates commissioning.
    Returns immediately; actual CHIP pairing runs in the background.
    """
    session = await start_commissioning(
        commissioning_id=body.commissioning_id,
        setup_code=body.setup_code,
        manual_code=body.manual_code,
        name=body.name,
        description=body.description,
        owner_id=body.owner_id,
        tenant_id=body.tenant_id,
        matter_client=matter_client,
    )
    COMMISSIONING_TOTAL.labels(status="started").inc()
    return CommissionResponse(
        commissioning_id=session["commissioning_id"],
        status=session["status"],
        node_id=session["node_id"],
    )


@app.get("/commission/{commissioning_id}", response_model=CommissionResponse)
async def commission_status(commissioning_id: str):
    """Poll the status of a commissioning session."""
    session = get_session(commissioning_id)
    if session is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Commissioning session not found")

    if session["status"] == "commissioned":
        COMMISSIONING_TOTAL.labels(status="succeeded").inc()
        ACTIVE_NODES.inc()
    elif session["status"] == "failed":
        COMMISSIONING_TOTAL.labels(status="failed").inc()

    return CommissionResponse(
        commissioning_id=commissioning_id,
        status=session["status"],
        node_id=session.get("node_id"),
        device_id=session.get("device_id"),
        error=session.get("error"),
    )


@app.get("/nodes")
async def list_nodes():
    """List all commissioned Matter nodes (for debugging)."""
    return {"nodes": list_sessions()}
