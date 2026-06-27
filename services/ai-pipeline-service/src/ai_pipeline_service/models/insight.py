from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text

from ai_pipeline_service.core.database import Base


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(String(36), primary_key=True, index=True)
    tenant_id = Column(String(255), nullable=False, default="default", index=True)
    scope_type = Column(String(50), nullable=False, index=True)
    scope_id = Column(String(255), nullable=False, index=True)
    severity = Column(String(30), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="open", index=True)
    category = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    evidence = Column(Text, nullable=False)
    recommendations = Column(Text, nullable=False)
    probable_cause = Column(Text, nullable=True)
    confidence = Column(String(30), nullable=True)
    runbook_steps = Column(Text, nullable=True)
    related_events = Column(Text, nullable=True)
    risk_score = Column(String(30), nullable=True)
    model_used = Column(String(255), nullable=False, default="rules")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)


class AIRiskScore(Base):
    __tablename__ = "ai_risk_scores"

    id = Column(String(255), primary_key=True, index=True)
    scope_type = Column(String(50), nullable=False, index=True)
    scope_id = Column(String(255), nullable=False, index=True)
    score = Column(String(30), nullable=False)
    level = Column(String(30), nullable=False, index=True)
    evidence = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class AIFunctionDraft(Base):
    __tablename__ = "ai_function_drafts"

    id = Column(String(36), primary_key=True, index=True)
    prompt = Column(Text, nullable=False)
    function_name = Column(String(255), nullable=False)
    language = Column(String(50), nullable=False, default="assemblyscript")
    source_code = Column(Text, nullable=False)
    plugin_metadata = Column(Text, nullable=False)
    input_schema = Column(Text, nullable=False)
    review = Column(Text, nullable=False)
    placement_result = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="draft", index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
