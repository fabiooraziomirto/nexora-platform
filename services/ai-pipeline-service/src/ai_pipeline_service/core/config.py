from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", case_sensitive=True)

    APP_NAME: str = "ai-pipeline-service"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["*"]

    DATABASE_URL: str = Field(default="mysql+pymysql://nxr:nxr@mysql:3306/nxr")
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_PREFIX: str = "nxr"
    KAFKA_ENABLED: bool = True
    KAFKA_REQUIRED: bool = False
    KAFKA_CONSUMER_GROUP: str = "ai-pipeline-service"

    AI_LLM_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:1b"
    OLLAMA_TIMEOUT_SECONDS: float = 4.0

    REPEATED_EVENT_WINDOW_MINUTES: int = 15
    REPEATED_EVENT_THRESHOLD: int = 3
    DEVICE_SERVICE_URL: str = "http://device-service:8000"
    FLEET_SERVICE_URL: str = "http://fleet-service:8000"

    LOG_LEVEL: str = "INFO"

settings = Settings()
