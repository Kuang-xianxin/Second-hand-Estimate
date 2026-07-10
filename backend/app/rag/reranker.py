"""BGE Reranker — cross-encoder re-ranking for retrieval quality.

Design doc §6.5: "BGE Reranker performs joint reading of query and
candidate documents to improve top-K precision."

Two backends:
  - LocalReranker: BGE-reranker-v2-m3 via FlagEmbedding (requires GPU for speed)
  - IDENTITY: pass-through (no re-ranking, for baseline comparison)

Benchmark (design doc §9.4):
  Expect nDCG@10 improvement of ≥10% vs pure vector baseline after adding reranker.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.rag.retriever import RetrievalResult

logger = logging.getLogger(__name__)


class Reranker(ABC):
    """Abstract reranker."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int = 8,
    ) -> list[RetrievalResult]:
        """Rerank candidates and return top_k."""
        ...


class IdentityReranker(Reranker):
    """Pass-through reranker — returns candidates as-is (no re-ranking).

    Used as baseline in evaluation.
    """

    def rerank(self, query: str, candidates: list[RetrievalResult], top_k: int = 8) -> list[RetrievalResult]:
        return sorted(candidates, key=lambda r: r.score or 0, reverse=True)[:top_k]


class LocalReranker(Reranker):
    """BGE-reranker-v2-m3 via FlagEmbedding.

    Requires: pip install FlagEmbedding
    Model: BAAI/bge-reranker-v2-m3 (~2GB)
    """

    def __init__(self, use_fp16: bool = True):
        try:
            from FlagEmbedding import FlagReranker
        except ImportError:
            raise ImportError("FlagEmbedding not installed. Run: pip install FlagEmbedding")
        logger.info("Loading BGE Reranker (BAAI/bge-reranker-v2-m3)...")
        self._model = FlagReranker(
            "BAAI/bge-reranker-v2-m3",
            use_fp16=use_fp16,
            devices=None,
        )
        logger.info("BGE Reranker loaded")

    def rerank(self, query: str, candidates: list[RetrievalResult], top_k: int = 8) -> list[RetrievalResult]:
        if not candidates:
            return []
        pairs = [[query, c.content] for c in candidates]
        scores = self._model.compute_score(pairs, normalize=True)
        # Handle single-score case
        if not isinstance(scores, list):
            scores = [scores]
        # Sort by score descending
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        for result, score in ranked[:top_k]:
            result.score = score  # update score to reranker score
        return [r for r, _ in ranked[:top_k]]


# ── Factory ──

_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        try:
            _reranker = LocalReranker()
        except ImportError:
            logger.info("FlagEmbedding not available, using IdentityReranker (dev mode)")
            _reranker = IdentityReranker()
    return _reranker
