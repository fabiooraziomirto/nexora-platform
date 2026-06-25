import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./plugin_service.db")
DB_CONNECT_TIMEOUT_SECONDS = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5"))

AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
AUTH_DEV_TOKEN = os.getenv("AUTH_DEV_TOKEN", "dev-token")
AUTH_DEV_BYPASS_ENABLED = os.getenv("AUTH_DEV_BYPASS_ENABLED", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "")
AUTH_WRITE_ROLE = os.getenv("AUTH_WRITE_ROLE", "writer")
