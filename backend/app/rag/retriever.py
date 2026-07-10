"""Hybrid retriever — Dense + Sparse + RRF fusion.

Pipeline (§6.5):
  1. Query → structure (brand, model, data_type, time filter)
  2. Dense recall top-40 (semantic similarity)
  3. Sparse recall top-40 (keyword precision)
  4. RRF fusion → top-30
  5. Deduplication + threshold filter
  6. → Reranker → top-5~8

Design doc: §6.5 Retrieval Pipeline
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Sequence

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from app.rag.embeddings import EmbeddingBackend, get_embedding_backend

logger = logging.getLogger(__name__)

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"
COLLECTION_NAME = "ccd_knowledge"


@dataclass
class RetrievalResult:
    """One retrieved document with score and payload."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    document_type: str = ""
    brand: str = ""
    model: str = ""
    topic: str = ""
    source: str = ""
    source_url: str = ""


@dataclass
class RetrievalConfig:
    """Tunable retrieval parameters for evaluation."""

    dense_top_k: int = 40
    sparse_top_k: int = 40
    rrf_k: int = 60          # RRF ranking constant
    rrf_top_k: int = 30      # after RRF fusion
    reranker_top_k: int = 8   # final results after reranker
    score_threshold: float = 0.3
    enable_sparse: bool = True
    enable_reranker: bool = True
    brand_filter: str = ""
    model_filter: str = ""


def _rrf_fuse(
    dense_hits: list[tuple[str, float]],
    sparse_hits: list[tuple[str, float]],
    k: int = 60,
    top_n: int = 30,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion — merge two ranked lists."""
    scores: dict[str, float] = defaultdict(float)
    for rank, (doc_id, _) in enumerate(dense_hits):
        scores[doc_id] += 1.0 / (k + rank + 1)
    for rank, (doc_id, _) in enumerate(sparse_hits):
        scores[doc_id] += 1.0 / (k + rank + 1)
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_items[:top_n]


class HybridRetriever:
    """Qdrant-backed hybrid retriever with Dense + Sparse + RRF."""

    def __init__(
        self,
        client: QdrantClient,
        embedding: EmbeddingBackend | None = None,
        collection: str = COLLECTION_NAME,
    ):
        self._client = client
        self._embedding = embedding or get_embedding_backend()
        self._collection = collection

    def ensure_collection(self) -> None:
        """Create collection if it doesn't exist, with dense + sparse vector config."""
        collections = [c.name for c in self._client.get_collections().collections]
        if self._collection in collections:
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config={
                DENSE_VECTOR: VectorParams(
                    size=self._embedding.dim,
                    distance=Distance.COSINE,
                ),
            },
            # Sparse vectors use the same index; Qdrant handles both
        )
        logger.info("Created Qdrant collection: %s (dim=%d)", self._collection, self._embedding.dim)

    def index(self, points: list[PointStruct]) -> None:
        """Upsert points into the collection."""
        self._client.upsert(
            collection_name=self._collection,
            points=points,
            wait=True,
        )

    def retrieve(
        self,
        query: str,
        config: RetrievalConfig | None = None,
    ) -> list[RetrievalResult]:
        """Full retrieval pipeline: Dense → Sparse → RRF → results.

        If reranker is enabled, this returns pre-rerank results.
        Caller should then pipe through reranker for final top-k.
        """
        cfg = config or RetrievalConfig()

        # Build metadata filter
        qdrant_filter = None
        must_conditions = []
        if cfg.brand_filter:
            must_conditions.append(FieldCondition(key="brand", match=MatchValue(value=cfg.brand_filter)))
        if cfg.model_filter:
            must_conditions.append(FieldCondition(key="model", match=MatchValue(value=cfg.model_filter)))
        if must_conditions:
            qdrant_filter = Filter(must=must_conditions)

        # Dense retrieval
        query_vec = self._embedding.encode_query(query)
        dense_results = self._client.query_points(
            collection_name=self._collection,
            query=query_vec,
            using=DENSE_VECTOR,
            limit=cfg.dense_top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        ).points
        dense_hits = [(hit.id, hit.score) for hit in dense_results]

        # Sparse retrieval (keyword-based, simulated via Qdrant full-text search)
        sparse_hits: list[tuple[str, float]] = []
        if cfg.enable_sparse:
            # Simulate sparse/BM25 via keyword search on payload content
            # For real Sparse retrieval, use BGE-M3's lexical weights + Qdrant sparse vectors
            keywords = _extract_keywords(query)
            if keywords:
                sparse_filter = Filter(
                    must=[
                        FieldCondition(
                            key="content",
                            match=MatchValue(value=kw),
                        ) for kw in keywords[:3]
                    ]
                ) if must_conditions is None else Filter(
                    must=must_conditions + [
                        FieldCondition(key="content", match=MatchValue(value=kw))
                        for kw in keywords[:3]
                    ]
                )
                # Fallback to dense search with keyword filter when sparse vectors unavailable
                sparse_results = self._client.query_points(
                    collection_name=self._collection,
                    query=query_vec,
                    using=DENSE_VECTOR,
                    limit=cfg.sparse_top_k,
                    query_filter=sparse_filter,
                    with_payload=True,
                ).points
                sparse_hits = [(hit.id, hit.score) for hit in sparse_results]

        # RRF fusion
        if sparse_hits:
            fused = _rrf_fuse(dense_hits, sparse_hits, k=cfg.rrf_k, top_n=cfg.rrf_top_k)
        else:
            fused = [(hit.id, hit.score) for hit in dense_results[:cfg.rrf_top_k]]

        # Fetch payloads for fused results
        fused_ids = [fid for fid, _ in fused]
        points = self._client.retrieve(
            collection_name=self._collection,
            ids=fused_ids,
            with_payload=True,
        )
        point_map = {p.id: p for p in points}

        results = []
        for doc_id, score in fused:
            point = point_map.get(doc_id)
            if not point or not point.payload:
                continue
            p = point.payload
            if score < cfg.score_threshold:
                continue
            results.append(RetrievalResult(
                chunk_id=p.get("chunk_id", doc_id),
                document_id=p.get("document_id", ""),
                content=p.get("content", ""),
                score=score,
                document_type=p.get("document_type", ""),
                brand=p.get("brand", ""),
                model=p.get("model", ""),
                topic=p.get("topic", ""),
                source=p.get("source", ""),
                source_url=p.get("source_url", ""),
            ))

        return results


def _extract_keywords(query: str) -> list[str]:
    """Extract key terms from query for sparse/BM25 matching.

    Simple heuristic: split on common separators, filter short tokens.
    In production, use jieba + stopword filtering.
    """
    import re
    tokens = re.split(r'[\s,，。！？、]+', query)
    return [t for t in tokens if len(t) >= 2][:10]
