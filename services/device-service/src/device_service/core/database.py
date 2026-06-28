from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from device_service.core.config import settings

# MySQL async engine with aiomysql.
# For sync operations (Alembic migrations), we use the sync URL.
if settings.DATABASE_URL.startswith("mysql+pymysql://"):
    DATABASE_URL_ASYNC = settings.DATABASE_URL.replace(
        "mysql+pymysql://", "mysql+aiomysql://", 1
    )
elif settings.DATABASE_URL.startswith("sqlite:///"):
    DATABASE_URL_ASYNC = settings.DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
else:
    DATABASE_URL_ASYNC = settings.DATABASE_URL
DATABASE_URL_SYNC = settings.DATABASE_URL  # Keep pymysql for sync operations

engine = create_async_engine(
    DATABASE_URL_ASYNC,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

# Sync engine for Alembic migrations
sync_engine = create_engine(
    DATABASE_URL_SYNC,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_device_schema)


def _ensure_device_schema(sync_conn) -> None:
    """Add columns introduced after initial create_all for dev databases."""
    from sqlalchemy import inspect as sa_inspect, text

    inspector = sa_inspect(sync_conn)
    table_names = set(inspector.get_table_names())

    if "devices" in table_names:
        existing = {col["name"] for col in inspector.get_columns("devices")}
        device_columns = [
            ("owner_id", "CHAR(36)"),
            ("tenant_id", "VARCHAR(255)"),
            ("privacy_level", "INTEGER NOT NULL DEFAULT 0"),
            ("capabilities", "TEXT"),
            ("runtime_env", "TEXT"),
            ("connection_protocol", "VARCHAR(50) NOT NULL DEFAULT 'nexora-agent'"),
            ("protocol_meta", "JSON"),
        ]
        for column_name, column_type in device_columns:
            if column_name not in existing:
                sync_conn.execute(
                    text(f"ALTER TABLE devices ADD COLUMN {column_name} {column_type}")
                )
        indexes = {idx["name"] for idx in inspector.get_indexes("devices")}
        if "idx_device_protocol" not in indexes:
            sync_conn.execute(
                text("CREATE INDEX idx_device_protocol ON devices (connection_protocol)")
            )

    if "device_telemetry" in table_names:
        existing = {col["name"] for col in inspector.get_columns("device_telemetry")}
        if "unit" not in existing:
            sync_conn.execute(text("ALTER TABLE device_telemetry ADD COLUMN unit VARCHAR(32)"))
