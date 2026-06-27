import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from plugin_service.core.config import DATABASE_URL, DB_CONNECT_TIMEOUT_SECONDS

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

# Columns added after initial schema — backfilled via ALTER TABLE on existing instances.
_NEW_COLUMNS: list[tuple[str, str]] = [
    ("module_type", "VARCHAR(30) NOT NULL DEFAULT 'plugin'"),
    ("artifact_uri", "VARCHAR(1024)"),
    ("artifact_checksum", "VARCHAR(128)"),
    ("runtime_type", "VARCHAR(50)"),
    ("entrypoint", "VARCHAR(255)"),
    ("timeout_seconds", "INTEGER DEFAULT 30"),
    ("memory_limit_mb", "INTEGER DEFAULT 64"),
    ("permissions", "TEXT"),
    ("required_capabilities", "TEXT"),
    ("env_schema", "TEXT"),
    ("input_schema", "TEXT"),
    ("sbom_uri", "VARCHAR(1024)"),
    ("security_scan_tool", "VARCHAR(64)"),
    ("security_scan_status", "VARCHAR(30) DEFAULT 'pending'"),
    ("security_scan_summary", "TEXT"),
    ("scanned_at", "TIMESTAMP"),
    ("status", "VARCHAR(30) NOT NULL DEFAULT 'draft'"),
    ("owner_id", "VARCHAR(64)"),
    ("tenant_id", "VARCHAR(255)"),
    ("created_at", "TIMESTAMP"),
    ("updated_at", "TIMESTAMP"),
]


def ensure_plugin_columns(db_engine=None) -> None:
    from sqlalchemy import inspect as sa_inspect, text

    _engine = db_engine or engine
    logger = logging.getLogger("plugin-service")
    inspector = sa_inspect(_engine)
    if "plugins" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("plugins")}
    with _engine.begin() as conn:
        for col_name, col_type in _NEW_COLUMNS:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE plugins ADD COLUMN {col_name} {col_type}"))
                logger.info("Added column %s to plugins table", col_name)
