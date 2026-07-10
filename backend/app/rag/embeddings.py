"""Embedding interface — pluggable backends for BGE-M3, API-based, or mock.

Design:
  - Base class defines the interface
  - LocalBGE: uses FlagEmbedding / sentence-transformers (BGE-M3, ~2GB)
  - APIBackend: delegates to an external embedding service (future)
  - SimpleHash: fast deterministic mock for testing / CI

For production, use LocalBGE on GPU or an API-based embedding service.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import logging
from typing import Sequence

logger = logging.getLogger(__name__)


class EmbeddingBackend(ABC):
    """Abstract embedding backend."""

    model_name: str = "bge-m3"
    dim: int = 1024

    @abstractmethod
    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Encode texts → list of vectors."""
        ...

    @abstractmethod
    def encode_query(self, query: str) -> list[float]:
        """Encode a single query (may use instruction prefix)."""
        ...


class SimpleHashEmbedding(EmbeddingBackend):
    """Deterministic mock embedding for testing.

    Uses SHA-256 hash → scaled to unit vector.  Not semantically meaningful
    but deterministic — same input always produces same output.
    """

    dim: int = 256

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._hash_vec(t) for t in texts]

    def encode_query(self, query: str) -> list[float]:
        return self._hash_vec(query)

    def _hash_vec(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        # Stretch 32 bytes to dim by repeating + mixing
        vec = []
        for i in range(self.dim):
            b = h[i % 32]
            offset = (i // 32) * 7
            vec.append(((b + offset) % 256) / 255.0)
        # Normalize to unit vector
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class LocalBGE(EmbeddingBackend):
    """BGE-M3 local embedding via FlagEmbedding.

    Requires: pip install FlagEmbedding
    Model cache: ~/.cache/huggingface/hub/
    """

    model_name: str = "BAAI/bge-m3"
    dim: int = 1024

    def __init__(self, use_fp16: bool = True):
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError:
            raise ImportError(
                "FlagEmbedding not installed. Run: pip install FlagEmbedding"
            )
        logger.info("Loading BGE-M3 model (%s)...", self.model_name)
        self._model = BGEM3FlagModel(
            self.model_name,
            use_fp16=use_fp16,
            devices=None,  # auto-detect GPU
        )
        logger.info("BGE-M3 loaded (dim=%d)", self.dim)

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        output = self._model.encode(
            list(texts),
            batch_size=12,
            max_length=512,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return output["dense_vecs"].tolist()

    def encode_query(self, query: str) -> list[float]:
        # BGE-M3 uses instruction prefix for queries
        return self.encode([f"Represent this sentence for searching relevant passages: {query}"])[0]


# ── Factory ──

_embedding_backend: EmbeddingBackend | None = None


def get_embedding_backend() -> EmbeddingBackend:
    """Return the configured embedding backend, or SimpleHash as dev fallback."""
    global _embedding_backend
    if _embedding_backend is None:
        try:
            _embedding_backend = LocalBGE()
        except ImportError:
            logger.info("FlagEmbedding not available, using SimpleHash (dev mode)")
            _embedding_backend = SimpleHashEmbedding()
    return _embedding_backend
