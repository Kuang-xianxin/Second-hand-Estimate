"""LangGraph Advisor models — threads, runs, feedback, knowledge, prompts."""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.sql import func

from app.models.database import Base


class AdvisorThread(Base):
    """User conversation thread.  One thread = one user session."""

    __tablename__ = "advisor_threads"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=True, index=True)
    title = Column(String(256), nullable=True)
    status = Column(String(32), default="active")   # active / closed
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AdvisorRun(Base):
    """One LangGraph execution within a thread."""

    __tablename__ = "advisor_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    thread_id = Column(String(64), ForeignKey("advisor_threads.thread_id"), nullable=False, index=True)
    user_query = Column(Text, nullable=False)
    requirement = Column(JSON, nullable=True)       # parsed PurchaseRequirement
    target_models = Column(JSON, nullable=True)     # resolved canonical model ids
    status = Column(String(32), default="running")   # running / paused / completed / failed
    confidence = Column(Float, nullable=True)
    report = Column(JSON, nullable=True)             # final DecisionReport
    node_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    errors = Column(JSON, nullable=True)
    langgraph_checkpoint_id = Column(String(128), nullable=True)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)


class AdvisorFeedback(Base):
    """User feedback on a completed advisor run."""

    __tablename__ = "advisor_feedback"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("advisor_runs.run_id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=True)
    rating = Column(Integer, nullable=True)           # 1-5
    evidence_correct = Column(Boolean, nullable=True)
    price_accurate = Column(Boolean, nullable=True)
    advice_adopted = Column(Boolean, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class KnowledgeDocument(Base):
    """RAG document registry — source of truth for vector index entries."""

    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String(128), unique=True, nullable=False, index=True)
    document_type = Column(String(64), nullable=False)   # camera_knowledge / market_item / rule / faq
    title = Column(String(512), nullable=True)
    source = Column(String(64), default="internal")     # internal / xianyu / manual
    source_url = Column(String(1024), nullable=True)
    content_hash = Column(String(128), nullable=False)
    chunk_count = Column(Integer, default=1)
    embedding_version = Column(String(32), default="bge-m3-v1")
    qdrant_status = Column(String(32), default="pending")  # pending / indexed / stale / error
    effective_at = Column(DateTime, nullable=True)
    indexed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PromptVersion(Base):
    """Versioned prompt templates for reproducible evaluation."""

    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    template = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True)         # expected template variables
    model = Column(String(64), nullable=True)        # which model this prompt targets
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
