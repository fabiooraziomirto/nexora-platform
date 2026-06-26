import os

os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_dns_service.db")

from main import Base, engine  # noqa: E402

Base.metadata.create_all(bind=engine)
