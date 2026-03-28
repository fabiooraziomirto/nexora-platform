import os

os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_plugin_service.db")

from plugin_service.main import Base, engine  # noqa: E402

Base.metadata.create_all(bind=engine)
