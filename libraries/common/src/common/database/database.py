"""
Database utilities using SQLAlchemy async.
"""

from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine, Engine
from sqlalchemy.pool import NullPool

from common.config import settings

# Base class for models
Base = declarative_base()

# Async engine for MySQL/MariaDB
_async_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker] = None

# Sync engine for Alembic migrations
_sync_engine: Optional[Engine] = None


def get_async_engine() -> AsyncEngine:
    """Get or create async database engine."""
    global _async_engine
    
    if _async_engine is None:
        # Convert MySQL URL to async format (aiomysql)
        database_url = str(settings.DATABASE_URL)
        if database_url.startswith("mysql+pymysql://"):
            database_url = database_url.replace("mysql+pymysql://", "mysql+aiomysql://")
        
        _async_engine = create_async_engine(
            database_url,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
            echo=settings.DATABASE_ECHO,
            future=True,
        )
    
    return _async_engine


def get_sync_engine() -> Engine:
    """Get or create sync database engine (for Alembic)."""
    global _sync_engine
    
    if _sync_engine is None:
        _sync_engine = create_engine(
            str(settings.DATABASE_URL),
            pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
            echo=settings.DATABASE_ECHO,
            poolclass=NullPool if settings.DEBUG else None,
        )
    
    return _sync_engine


def get_async_session_factory() -> async_sessionmaker:
    """Get or create async session factory."""
    global _async_session_factory
    
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    session_factory = get_async_session_factory()
    
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    engine = get_async_engine()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    global _async_engine, _sync_engine
    
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
    
    if _sync_engine:
        _sync_engine.dispose()
        _sync_engine = None


# Export sync engine for Alembic
sync_engine = property(lambda self: get_sync_engine())

