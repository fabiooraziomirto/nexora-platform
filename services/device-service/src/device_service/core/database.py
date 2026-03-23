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

