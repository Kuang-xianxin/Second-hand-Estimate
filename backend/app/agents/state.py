"""Advisor State — LangGraph shared state for the decision workflow.

Design doc §5.1: State holds only serializable data and resource IDs.
No database connections, HTTP clients, or large model instances.
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class PurchaseRequirement(TypedDict, total=False):
    """Parsed user purchase requirement."""
    budget_min: float
    budget_max: float
    brands: list[str]
    models: list[str]
    usage: str                     # 日常拍照 / 收藏 / 送礼 / ...
    condition_preference: str      # 9成新 / 95新 / 不限
    risk_tolerance: str            # low / medium / high
    raw_text: str


class MarketEvidence(TypedDict, total=False):
    """One piece of market data evidence."""
    evidence_id: str               # M1, M2, ...
    keyword: str
    canonical_model: str
    sample_count: int
    base_price: float
    price_min: float
    price_max: float
    median_price: float
    source: str
    crawled_at: str


class KnowledgeEvidence(TypedDict, total=False):
    """One piece of domain knowledge evidence."""
    evidence_id: str               # K1, K2, ...
    document_id: str
    content_snippet: str
    document_type: str
    brand: str
    model: str
    topic: str
    score: float


class ImageFinding(TypedDict, total=False):
    """Result of visual image analysis."""
    image_index: int
    camera_model_detected: str
    condition_flags: list[str]
    accessories_visible: list[str]
    confidence: float


class ValuationResult(TypedDict, total=False):
    """Deterministic valuation output."""
    base_price: float
    price_min: float
    price_max: float
    median_price: float
    sample_count: int
    confidence: str
    method: str
    from_cache: bool


class RiskItem(TypedDict, total=False):
    """One identified risk."""
    risk_id: str
    category: str
    description: str
    severity: str
    evidence_id: str


class DecisionReport(TypedDict, total=False):
    """Final structured decision report."""
    summary: str
    recommendation: str            # buy / caution / skip / insufficient_data
    valuation: dict
    risks: list[dict]
    evidence_summary: str
    confidence: float


class AdvisorState(TypedDict, total=False):
    """Full LangGraph state (§5.1).

    All fields are serializable. Nodes read the state dict and return
    partial updates via the standard LangGraph reducer (last-write-wins
    for scalars, override for lists).
    """
    thread_id: str
    user_query: str

    # Parsed requirement
    requirement: dict               # PurchaseRequirement
    target_models: list[str]

    # Evidence collections
    market_evidence: list[dict]     # list[MarketEvidence]
    knowledge_evidence: list[dict]  # list[KnowledgeEvidence]
    image_findings: list[dict]      # list[ImageFinding]

    # Results
    valuation: Optional[dict]       # ValuationResult
    risks: list[dict]               # list[RiskItem]
    report: Optional[dict]          # DecisionReport
    confidence: float

    # Control flow
    retrieval_attempts: int
    evidence_sufficient: bool
    pending_approval: bool
    approval_decision: str
    errors: list[str]
    current_node: str

    # LLM conversation
    messages: list
