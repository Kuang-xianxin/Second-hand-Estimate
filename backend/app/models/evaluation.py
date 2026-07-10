"""Evaluation models — gold datasets, evaluation runs, metrics."""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.sql import func

from app.models.database import Base


class EvaluationCase(Base):
    """Gold-standard evaluation sample (manual annotation)."""

    __tablename__ = "evaluation_cases"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(64), unique=True, nullable=False, index=True)
    category = Column(String(64), nullable=False)        # model_query / price_trend / risk / multi_condition
    query = Column(Text, nullable=False)
    expected_models = Column(JSON, nullable=True)        # ["canon-ixus-130"]
    expected_price_range = Column(JSON, nullable=True)   # {"min": 300, "max": 500}
    expected_risks = Column(JSON, nullable=True)         # ["dependency_xd_card"]
    expected_tools = Column(JSON, nullable=True)         # ["market_tool", "risk_tool"]
    expected_path = Column(JSON, nullable=True)          # expected node sequence
    difficulty = Column(String(16), default="medium")     # easy / medium / hard
    tags = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class EvaluationRun(Base):
    """One evaluation execution against the gold dataset."""

    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    prompt_version_id = Column(Integer, ForeignKey("prompt_versions.id"), nullable=True)
    config_snapshot = Column(JSON, nullable=True)       # frozen config at eval time
    total_cases = Column(Integer, default=0)
    passed_cases = Column(Integer, default=0)
    metrics = Column(JSON, nullable=True)               # Recall@K, MRR, nDCG, etc.
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)


class EvaluationResult(Base):
    """Per-case result within an evaluation run."""

    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("evaluation_runs.run_id"), nullable=False, index=True)
    case_id = Column(String(64), nullable=False, index=True)
    passed = Column(Boolean, default=False)
    actual_models = Column(JSON, nullable=True)
    actual_tools = Column(JSON, nullable=True)
    actual_path = Column(JSON, nullable=True)
    citation_correct = Column(Boolean, nullable=True)
    price_consistent = Column(Boolean, nullable=True)
    evidence_faithful = Column(Boolean, nullable=True)
    notes = Column(Text, nullable=True)
    trace_url = Column(String(1024), nullable=True)      # LangSmith trace link
