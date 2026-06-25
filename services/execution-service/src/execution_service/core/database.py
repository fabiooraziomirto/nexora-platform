from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from execution_service.core.config import DATABASE_URL, DB_CONNECT_TIMEOUT_SECONDS

Base = declarative_base()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=(
        {"connect_timeout": DB_CONNECT_TIMEOUT_SECONDS}
        if "mysql" in DATABASE_URL
        else {"timeout": DB_CONNECT_TIMEOUT_SECONDS}
    ),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

_NEW_COLUMNS: list[tuple[str, str]] = [
    ("correlation_id", "VARCHAR(64)"),
    ("idempotency_key", "VARCHAR(128)"),
    ("exit_code", "INTEGER"),
    ("result_stdout", "TEXT"),
    ("result_stderr", "TEXT"),
    ("tenant_id", "VARCHAR(64)"),
    ("owner_id", "VARCHAR(64)"),
    ("created_at", "TIMESTAMP"),
    ("dispatched_at", "TIMESTAMP"),
    ("running_at", "TIMESTAMP"),
    # FaaS columns
    ("execution_type", "VARCHAR(30)"),
    ("plugin_id", "VARCHAR(36)"),
    ("args", "TEXT"),
    ("function_result", "TEXT"),
    ("invocation_mode", "VARCHAR(10)"),
]


def ensure_execution_columns(db_engine=None) -> None:
    from sqlalchemy import inspect as sa_inspect, text
    import logging

    _engine = db_engine or engine
    logger = logging.getLogger("execution-service")
    inspector = sa_inspect(_engine)
    existing = {col["name"] for col in inspector.get_columns("executions")}
    with _engine.begin() as conn:
        for col_name, col_type in _NEW_COLUMNS:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE executions ADD COLUMN {col_name} {col_type}"))
                logger.info("Added column %s to executions table", col_name)
