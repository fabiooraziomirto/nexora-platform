import os

os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS", "600")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_execution_service.db")

from main import Base, engine  # noqa: E402

Base.metadata.create_all(bind=engine)
