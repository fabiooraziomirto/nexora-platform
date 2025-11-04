from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

from device_service.core.database import Base, sync_engine
from device_service.core.config import settings

# Import all models here so Alembic can detect them
from device_service.models import Device  # noqa: F401

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url from environment
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Use sync engine for migrations
    with sync_engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=Base.metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
