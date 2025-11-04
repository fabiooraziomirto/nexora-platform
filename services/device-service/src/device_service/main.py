from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from device_service.api import devices
from device_service.core.config import settings
from device_service.core.database import engine, init_db
from device_service.core.events import event_bus
from device_service.core.metrics import setup_metrics, get_metrics_response

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Device Service", version=settings.VERSION)
    
    # Initialize database
    await init_db()
    
    # Initialize event bus
    await event_bus.connect()
    
    # Setup metrics
    setup_metrics()
    
    logger.info("Device Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Device Service")
    await event_bus.disconnect()
    await engine.dispose()


app = FastAPI(
    title="Stack4Things Device Service",
    description="Device Management Service for Stack4Things v2.0",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(devices.router, prefix="/api/v2", tags=["devices"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "device-service"}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    # TODO: Check database connection, Redis, Kafka
    return {"status": "ready", "service": "device-service"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return get_metrics_response()

