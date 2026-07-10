"""Evaluation runner — automated evaluation against gold dataset.

Runs retrieval evaluation (Phase 2) and advisor evaluation (Phase 3)
against the gold dataset and generates comparison reports.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.rag.evaluation import (
    EvalMetrics,
    EvalQuery,
    evaluate_retrieval,
    format_comparison_report,
    run_baseline_comparison,
)

logger = logging.getLogger(__name__)


@dataclass
class AdvisorEvalResult:
    """Per-query advisor evaluation result."""
    query_id: str
    query: str
    passed: bool
    recommendation: str = ""
    has_valuation: bool = False
    has_risks: bool = False
    has_evidence: bool = False
    latency_ms: float = 0
    node_count: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class AdvisorEvalMetrics:
    """Aggregated advisor evaluation metrics."""
    total: int = 0
    passed: int = 0
    avg_latency_ms: float = 0
    valuation_rate: float = 0.0
    risk_detection_rate: float = 0.0
    evidence_rate: float = 0.0
    error_rate: float = 0.0
    per_query: list[AdvisorEvalResult] = field(default_factory=list)


async def evaluate_advisor_async(queries: list[EvalQuery]) -> AdvisorEvalMetrics:
    """Run advisor evaluation over gold queries."""
    from app.agents.advisor_graph import run_advisor

    metrics = AdvisorEvalMetrics(total=len(queries))
    results = []

    for eq in queries:
        start = time.monotonic()
        try:
            result = await run_advisor(eq.query)
            latency = (time.monotonic() - start) * 1000

            report = result.get("report") or {}
            recommendation = report.get("recommendation", "")

            # Determine pass/fail based on query category
            if eq.category == "insufficient":
                passed = recommendation == "insufficient_data"
            elif eq.min_expected_hits == 0:
                passed = True
            else:
                passed = recommendation in ("buy", "caution")

            r = AdvisorEvalResult(
                query_id=eq.query_id,
                query=eq.query[:80],
                passed=passed,
                recommendation=recommendation,
                has_valuation=result.get("valuation") is not None,
                has_risks=len(result.get("risks", [])) > 0,
                has_evidence=len(result.get("market_evidence", [])) + len(result.get("knowledge_evidence", [])) > 0,
                latency_ms=round(latency, 1),
                node_count=sum(1 for _ in result.get("current_node", "").split()),
                errors=result.get("errors", []),
            )
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            r = AdvisorEvalResult(
                query_id=eq.query_id,
                query=eq.query[:80],
                passed=False,
                latency_ms=round(latency, 1),
                errors=[str(e)],
            )

        results.append(r)

    passed_count = sum(1 for r in results if r.passed)
    latencies = [r.latency_ms for r in results if r.latency_ms > 0]
    with_valuation = sum(1 for r in results if r.has_valuation)
    with_risks = sum(1 for r in results if r.has_risks)
    with_evidence = sum(1 for r in results if r.has_evidence)
    with_errors = sum(1 for r in results if r.errors)

    metrics.passed = passed_count
    metrics.avg_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else 0
    metrics.valuation_rate = round(with_valuation / len(queries), 3) if queries else 0
    metrics.risk_detection_rate = round(with_risks / len(queries), 3) if queries else 0
    metrics.evidence_rate = round(with_evidence / len(queries), 3) if queries else 0
    metrics.error_rate = round(with_errors / len(queries), 3) if queries else 0
    metrics.per_query = results

    return metrics


def format_advisor_report(metrics: AdvisorEvalMetrics) -> str:
    """Format advisor evaluation results."""
    lines = [
        "Advisor 评测报告",
        "=" * 50,
        f"  总用例: {metrics.total}",
        f"  通过: {metrics.passed} ({metrics.passed / max(metrics.total, 1) * 100:.1f}%)",
        f"  平均延迟: {metrics.avg_latency_ms:.0f}ms",
        f"  估价生成率: {metrics.valuation_rate:.1%}",
        f"  风险检测率: {metrics.risk_detection_rate:.1%}",
        f"  证据覆盖率: {metrics.evidence_rate:.1%}",
        f"  错误率: {metrics.error_rate:.1%}",
        "",
        "  目标指标:",
        "    结构化输出成功率 ≥ 99%",
        "    引用正确率 ≥ 95%",
        f"    Recall@20 ≥ 90%",
        "    SSE 首事件 < 1s",
        "    p95 延迟 < 15s",
        "",
    ]
    # Category breakdown
    cats = {}
    for r in metrics.per_query:
        cats.setdefault(r.query_id[0], {"total": 0, "passed": 0})
        cats[r.query_id[0]]["total"] += 1
        if r.passed:
            cats[r.query_id[0]]["passed"] += 1

    lines.append("  分类通过率:")
    for cat, counts in sorted(cats.items()):
        rate = counts["passed"] / max(counts["total"], 1) * 100
        lines.append(f"    {cat}: {counts['passed']}/{counts['total']} ({rate:.0f}%)")

    return "\n".join(lines)
