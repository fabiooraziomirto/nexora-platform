"""
Shared sync DB helpers for simple microservices.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


ServiceBase = declarative_base()


def build_sync_engine(database_url: str):
    """Create a sync SQLAlchemy engine with health checks enabled."""
    return create_engine(database_url, pool_pre_ping=True)


def build_session_factory(engine):
    """Create a session factory for CRUD service handlers."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
