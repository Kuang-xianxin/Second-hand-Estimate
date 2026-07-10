"""Citation tracking — fact classification and evidence formatting.

Design doc §6.6:
  Three fact types:
    - market_fact: from PostgreSQL market data
    - knowledge_fact: from Qdrant documents
    - inference: model-derived conclusions

Rules:
  - Every claim must cite evidence
  - Evidence format: [市场证据 M12] or [知识证据 K03]
  - Insufficient evidence → explicitly state, don't fabricate
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FactType(str, Enum):
    MARKET = "market_fact"
    KNOWLEDGE = "knowledge_fact"
    INFERENCE = "inference"


@dataclass
class Citation:
    """One cited fact with evidence source."""

    fact_type: FactType
    source_id: str          # M12, K03, etc.
    claim: str              # the factual statement
    evidence_snippet: str   # supporting text from source
    document_id: str = ""   # source document
    document_type: str = ""  # camera_knowledge / market_item / rule
    confidence: float = 1.0
    is_verified: bool = False


@dataclass
class EvidenceReport:
    """Structured evidence for a decision report."""

    market_facts: list[Citation] = field(default_factory=list)
    knowledge_facts: list[Citation] = field(default_factory=list)
    inferences: list[Citation] = field(default_factory=list)
    is_sufficient: bool = False
    missing_evidence: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable evidence summary."""
        lines = []
        for i, c in enumerate(self.market_facts, 1):
            lines.append(f"  [市场证据 M{i}] {c.claim}")
        for i, c in enumerate(self.knowledge_facts, 1):
            lines.append(f"  [知识证据 K{i}] {c.claim}")
        for i, c in enumerate(self.inferences, 1):
            lines.append(f"  [推断 I{i}] {c.claim} (置信度: {c.confidence:.0%})")
        if self.missing_evidence:
            lines.append(f"  ⚠ 证据不足: {', '.join(self.missing_evidence)}")
        if not self.is_sufficient:
            lines.append("  ⚠ 不足以形成可靠结论")
        return "\n".join(lines) if lines else "无证据"


def make_market_citation(
    claim: str, evidence: str, doc_id: str = "", index: int = 1
) -> Citation:
    return Citation(
        fact_type=FactType.MARKET,
        source_id=f"M{index}",
        claim=claim,
        evidence_snippet=evidence,
        document_id=doc_id,
        document_type="market_item",
    )


def make_knowledge_citation(
    claim: str, evidence: str, doc_id: str = "", index: int = 1
) -> Citation:
    return Citation(
        fact_type=FactType.KNOWLEDGE,
        source_id=f"K{index}",
        claim=claim,
        evidence_snippet=evidence,
        document_id=doc_id,
        document_type="camera_knowledge",
    )


def make_inference(claim: str, confidence: float = 0.5) -> Citation:
    return Citation(
        fact_type=FactType.INFERENCE,
        source_id=f"I-generated",
        claim=claim,
        evidence_snippet="",
        confidence=confidence,
    )
