from sqlalchemy import Column, String

from plugin_service.core.database import Base


class Plugin(Base):
    __tablename__ = "plugins"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(64), nullable=False, default="0.1.0")
