from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from network_service.core.config import DATABASE_URL, DB_CONNECT_TIMEOUT_SECONDS

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


def ensure_port_columns(db_engine=None) -> None:
    from sqlalchemy import inspect as sa_inspect, text

    _engine = db_engine or engine
    inspector = sa_inspect(_engine)
    if "ports" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("ports")}
    with _engine.begin() as conn:
        if "owner_id" not in existing:
            conn.execute(text("ALTER TABLE ports ADD COLUMN owner_id VARCHAR(64)"))
        if "tenant_id" not in existing:
            conn.execute(text("ALTER TABLE ports ADD COLUMN tenant_id VARCHAR(255)"))
