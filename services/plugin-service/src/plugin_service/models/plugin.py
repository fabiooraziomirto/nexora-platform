from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from plugin_service.core.database import Base


class Plugin(Base):
    __tablename__ = "plugins"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(64), nullable=False, default="0.1.0")

    # "plugin" = legacy module metadata; "function" = FaaS WASM/WASI artifact
    module_type = Column(String(30), nullable=False, default="plugin")

    # FaaS function fields (nullable for legacy plugins)
    artifact_uri = Column(String(1024), nullable=True)      # download URL for WASM artifact
    artifact_checksum = Column(String(128), nullable=True)  # sha256:<hex>
    runtime_type = Column(String(50), nullable=True)        # "wasm-wasi"
    entrypoint = Column(String(255), nullable=True)         # exported fn name, e.g. "_start"
    timeout_seconds = Column(Integer, nullable=True, default=30)
    memory_limit_mb = Column(Integer, nullable=True, default=64)
    permissions = Column(Text, nullable=True)               # JSON list: ["network","fs_read"]
    required_capabilities = Column(Text, nullable=True)     # JSON list: ["wasm_wasi"]
    env_schema = Column(Text, nullable=True)                # JSON Schema for env vars
    input_schema = Column(Text, nullable=True)              # JSON Schema for function args
    # draft → active → deprecated | archived
    status = Column(String(30), nullable=False, default="draft")
    owner_id = Column(String(64), nullable=True, index=True)
    tenant_id = Column(String(255), nullable=True, index=True)

    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
