from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from fleet_service.core.config import DATABASE_URL, DB_CONNECT_TIMEOUT_SECONDS

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
