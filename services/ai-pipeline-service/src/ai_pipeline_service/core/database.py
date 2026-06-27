from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from ai_pipeline_service.core.config import settings


engine_kwargs = {"pool_pre_ping": True, "echo": settings.DEBUG}
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_size": settings.DATABASE_POOL_SIZE,
            "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        }
    )

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def ensure_ai_columns() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("ai_insights"):
        return
    existing = {col["name"] for col in inspector.get_columns("ai_insights")}
    additions = {
        "probable_cause": "TEXT",
        "confidence": "VARCHAR(30)",
        "runbook_steps": "TEXT",
        "related_events": "TEXT",
        "risk_score": "VARCHAR(30)",
    }
    with engine.begin() as conn:
        for name, ddl_type in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE ai_insights ADD COLUMN {name} {ddl_type}"))
