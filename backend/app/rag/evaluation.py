"""Retrieval evaluation — metrics and baseline comparison.

Design doc §9: four evaluation configurations must be saved:
  1. Pure keyword retrieval
  2. Pure Dense vector retrieval
  3. Dense + Sparse + RRF
  4. Hybrid + Reranker + business rules

Metrics: Recall@K, Precision@K, MRR, nDCG, model exact-match rate.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Sequence

from qdrant_client import QdrantClient

from app.rag.retriever import HybridRetriever, RetrievalConfig, RetrievalResult

logger = logging.getLogger(__name__)


@dataclass
class EvalQuery:
    """One gold evaluation query with expected results."""

    query_id: str
    query: str
    expected_doc_ids: list[str]        # gold standard: documents that SHOULD be retrieved
    category: str = "general"          # model_query / price_trend / risk / fault
    min_expected_hits: int = 1         # minimum expected hits to consider success


@dataclass
class EvalMetrics:
    """Aggregated metrics over an evaluation run."""

    name: str                          # e.g. "dense_only", "hybrid_reranker"
    num_queries: int = 0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    recall_at_20: float = 0.0
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    mrr_at_10: float = 0.0
    ndcg_at_10: float = 0.0
    model_exact_match_rate: float = 0.0
    per_query: list[dict] = field(default_factory=list)


def _recall_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    if not expected_ids:
        return 1.0
    top_k = retrieved_ids[:k]
    hits = len(set(top_k) & set(expected_ids))
    return hits / len(expected_ids)


def _precision_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    if not retrieved_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = len(set(top_k) & set(expected_ids))
    return hits / min(k, len(top_k))


def _mrr(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    """Mean Reciprocal Rank — 1 / rank of first relevant document."""
    for i, doc_id in enumerate(retrieved_ids, 1):
        if doc_id in expected_ids:
            return 1.0 / i
    return 0.0


def _ndcg_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    """Normalized DCG at k."""
    import math
    top_k = retrieved_ids[:k]
    dcg = 0.0
    for i, doc_id in enumerate(top_k, 1):
        if doc_id in expected_ids:
            dcg += 1.0 / math.log2(i + 1)
    # Ideal DCG
    ideal_hits = min(len(expected_ids), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_retrieval(
    retriever: HybridRetriever,
    queries: list[EvalQuery],
    config: RetrievalConfig | None = None,
) -> EvalMetrics:
    """Run evaluation over a set of gold queries."""
    metrics = EvalMetrics(num_queries=len(queries))
    total_recall5 = 0.0
    total_recall10 = 0.0
    total_recall20 = 0.0
    total_prec5 = 0.0
    total_prec10 = 0.0
    total_mrr = 0.0
    total_ndcg = 0.0
    total_model_match = 0.0

    for eq in queries:
        results = retriever.retrieve(eq.query, config)
        retrieved_doc_ids = [r.document_id for r in results]

        r5 = _recall_at_k(retrieved_doc_ids, eq.expected_doc_ids, 5)
        r10 = _recall_at_k(retrieved_doc_ids, eq.expected_doc_ids, 10)
        r20 = _recall_at_k(retrieved_doc_ids, eq.expected_doc_ids, 20)
        p5 = _precision_at_k(retrieved_doc_ids, eq.expected_doc_ids, 5)
        p10 = _precision_at_k(retrieved_doc_ids, eq.expected_doc_ids, 10)
        mrr = _mrr(retrieved_doc_ids, eq.expected_doc_ids)
        ndcg = _ndcg_at_k(retrieved_doc_ids, eq.expected_doc_ids, 10)

        total_recall5 += r5
        total_recall10 += r10
        total_recall20 += r20
        total_prec5 += p5
        total_prec10 += p10
        total_mrr += mrr
        total_ndcg += ndcg

        # Model exact match: check if at least one expected doc was retrieved
        if len(set(retrieved_doc_ids[:5]) & set(eq.expected_doc_ids)) > 0:
            total_model_match += 1

        metrics.per_query.append({
            "query_id": eq.query_id,
            "query": eq.query[:80],
            "retrieved": retrieved_doc_ids[:5],
            "expected": eq.expected_doc_ids[:5],
            "recall@5": round(r5, 3),
            "mrr": round(mrr, 3),
        })

    n = len(queries)
    if n > 0:
        metrics.recall_at_5 = round(total_recall5 / n, 4)
        metrics.recall_at_10 = round(total_recall10 / n, 4)
        metrics.recall_at_20 = round(total_recall20 / n, 4)
        metrics.precision_at_5 = round(total_prec5 / n, 4)
        metrics.precision_at_10 = round(total_prec10 / n, 4)
        metrics.mrr_at_10 = round(total_mrr / n, 4)
        metrics.ndcg_at_10 = round(total_ndcg / n, 4)
        metrics.model_exact_match_rate = round(total_model_match / n, 4)

    return metrics


def run_baseline_comparison(
    client: QdrantClient,
    queries: list[EvalQuery],
) -> dict[str, EvalMetrics]:
    """Run all four retrieval configurations and return comparison.

    Config 1: Keyword only (dense disabled)
    Config 2: Dense only (sparse disabled)
    Config 3: Dense + Sparse + RRF (no reranker)
    Config 4: Dense + Sparse + RRF + Reranker
    """
    from app.rag.embeddings import get_embedding_backend
    from app.rag.reranker import get_reranker, IdentityReranker

    retriever = HybridRetriever(client, get_embedding_backend())

    configs = {
        "keyword_only": RetrievalConfig(
            dense_top_k=0, sparse_top_k=40, enable_sparse=True,
            enable_reranker=False,
        ),
        "dense_only": RetrievalConfig(
            dense_top_k=40, sparse_top_k=0, enable_sparse=False,
            enable_reranker=False,
        ),
        "hybrid_rrf": RetrievalConfig(
            dense_top_k=40, sparse_top_k=40, enable_sparse=True,
            enable_reranker=False, rrf_top_k=30,
        ),
        "hybrid_reranker": RetrievalConfig(
            dense_top_k=40, sparse_top_k=40, enable_sparse=True,
            enable_reranker=True, rrf_top_k=30, reranker_top_k=8,
        ),
    }

    results = {}
    for name, cfg in configs.items():
        metrics = evaluate_retrieval(retriever, queries, cfg)
        metrics.name = name

        if cfg.enable_reranker:
            # Apply reranker to each query's results
            reranker = get_reranker()
            if not isinstance(reranker, IdentityReranker):
                # Re-evaluate with reranker
                metrics_reranked = evaluate_retrieval(retriever, queries, cfg)
                metrics_reranked.name = name
                results[name] = metrics_reranked
                continue

        results[name] = metrics

    return results


def format_comparison_report(results: dict[str, EvalMetrics]) -> str:
    """Format evaluation results as a comparison table."""
    lines = ["检索评测对比报告", "=" * 60, ""]
    headers = ["配置", "Recall@5", "Recall@20", "Prec@5", "MRR@10", "nDCG@10", "Model%"]
    lines.append("  ".join(f"{h:<10}" for h in headers))
    lines.append("  " + "  ".join("-" * 10 for _ in headers))

    for name, m in results.items():
        row = [
            f"{name:<10}",
            f"{m.recall_at_5:<10.3f}",
            f"{m.recall_at_20:<10.3f}",
            f"{m.precision_at_5:<10.3f}",
            f"{m.mrr_at_10:<10.3f}",
            f"{m.ndcg_at_10:<10.3f}",
            f"{m.model_exact_match_rate:<10.3f}",
        ]
        lines.append("  ".join(row))

    lines.append("")
    lines.append("四套对照实验：")
    lines.append("  1. keyword_only — 纯关键词检索（基线）")
    lines.append("  2. dense_only — 纯 Dense 向量检索")
    lines.append("  3. hybrid_rrf — Dense + Sparse + RRF 融合")
    lines.append("  4. hybrid_reranker — 混合检索 + Reranker 精排")
    return "\n".join(lines)
