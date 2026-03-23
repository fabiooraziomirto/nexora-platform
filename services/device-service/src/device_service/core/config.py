from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    APP_NAME: str = "device-service"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["*"]
    
    # Database
    DATABASE_URL: str = Field(
        default="mysql+pymysql://stack4things:stack4things@mysql:3306/stack4things",
        description="Database connection string",
        example="mysql+pymysql://user:password@localhost:3306/stack4things",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string"
    )
    
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = Field(
        default="kafka:9092",
        description="Kafka bootstrap servers",
    )
    KAFKA_TOPIC_PREFIX: str = "stack4things"
    KAFKA_ENABLED: bool = True
    KAFKA_REQUIRED: bool = False
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Keycloak
    KEYCLOAK_URL: str = Field(
        default="http://keycloak:8080",
        description="Keycloak server URL"
    )
    KEYCLOAK_REALM: str = "stack4things"
    KEYCLOAK_CLIENT_ID: str = "device-service"
    KEYCLOAK_CLIENT_SECRET: str | None = None
    
    # Keystone (fallback)
    KEYSTONE_URL: str | None = None
    KEYSTONE_USERNAME: str | None = None
    KEYSTONE_PASSWORD: str | None = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

