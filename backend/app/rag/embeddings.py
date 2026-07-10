"""Embedding interface — pluggable backends.

Backends:
  - VolcanoEmbedding: Doubao API (production, semantic)
  - SimpleHashEmbedding: deterministic hash (dev/testing fallback)
  - LocalBGE: BGE-M3 via FlagEmbedding (requires GPU, ~2GB RAM)

Priority: VolcanoEmbedding > LocalBGE > SimpleHash
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import logging
from typing import Sequence

logger = logging.getLogger(__name__)


class EmbeddingBackend(ABC):
    """Abstract embedding backend."""

    model_name: str = "unknown"
    _dim: int = 1024

    @property
    def dim(self) -> int:
        return self._dim

    @abstractmethod
    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        ...

    @abstractmethod
    def encode_query(self, query: str) -> list[float]:
        ...


class SimpleHashEmbedding(EmbeddingBackend):
    """Deterministic mock for testing — same input = same output, no semantics."""

    model_name: str = "simple-hash"

    def __init__(self, dim: int = 256):
        self._dim = dim

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._hash_vec(t) for t in texts]

    def encode_query(self, query: str) -> list[float]:
        return self._hash_vec(query)

    def _hash_vec(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        vec = []
        for i in range(self._dim):
            b = h[i % 32]
            vec.append(((b + (i // 32) * 7) % 256) / 255.0)
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class VolcanoEmbedding(EmbeddingBackend):
    """Volcano Engine (Doubao) embedding API.

    Endpoint: POST {base_url}/embeddings
    Requires: DOUBAO_API_KEY in .env
    """

    model_name: str = "doubao-embedding"

    def __init__(self, api_key: str = "", base_url: str = ""):
        from app.config import settings
        import httpx
        self._api_key = api_key or settings.doubao_api_key or ""
        self._base_url = (base_url or settings.doubao_base_url or
                          "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
        if not self._api_key:
            raise ValueError("DOUBAO_API_KEY not set")
        self._client = httpx.Client(timeout=30)
        self._dim = 1024

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            resp = self._client.post(
                f"{self._base_url}/embeddings",
                headers={"Authorization": f"Bearer {self._api_key}",
                         "Content-Type": "application/json"},
                json={"model": "doubao-embedding", "input": list(texts)},
            )
            if resp.status_code != 200:
                logger.warning("Embedding API %d: %s", resp.status_code, resp.text[:200])
                return [self._fallback(t) for t in texts]
            data = resp.json()
            vecs = [e.get("embedding", self._fallback(texts[i]))
                    for i, e in enumerate(data.get("data", []))]
            if vecs and vecs[0]:
                self._dim = len(vecs[0])
            return vecs
        except Exception as e:
            logger.warning("Embedding API error: %s", e)
            return [self._fallback(t) for t in texts]

    def encode_query(self, query: str) -> list[float]:
        vecs = self.encode([query])
        return vecs[0] if vecs else self._fallback(query)

    def _fallback(self, text: str) -> list[float]:
        return SimpleHashEmbedding(self._dim)._hash_vec(text)


# ── Factory ──

_embedding_backend: EmbeddingBackend | None = None


def get_embedding_backend() -> EmbeddingBackend:
    global _embedding_backend
    if _embedding_backend is None:
        # Default: SimpleHash (deterministic, works everywhere)
        # Volcano/LocalBGE are opt-in via explicit set_embedding_backend()
        _embedding_backend = SimpleHashEmbedding()
    return _embedding_backend


def reset_embedding_backend():
    global _embedding_backend
    _embedding_backend = None
