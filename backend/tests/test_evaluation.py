"""Tests for evaluation dataset and runner."""
from app.evaluation.gold_dataset import (
    EDGE_CASES,
    MODEL_DISCRIMINATION,
    MODEL_SPEC_QUERIES,
    MULTI_CONDITION,
    PRICE_QUERIES,
    RISK_QUERIES,
    get_gold_dataset,
)
from app.evaluation.runner import AdvisorEvalMetrics, AdvisorEvalResult


def test_gold_dataset_total_count():
    ds = get_gold_dataset()
    assert len(ds) >= 100, f"Expected >=100, got {len(ds)}"


def test_gold_dataset_categories():
    assert len(MODEL_SPEC_QUERIES) >= 25
    assert len(PRICE_QUERIES) >= 20
    assert len(MODEL_DISCRIMINATION) >= 15
    assert len(RISK_QUERIES) >= 15
    assert len(MULTI_CONDITION) >= 10
    assert len(EDGE_CASES) >= 5


def test_gold_dataset_has_diverse_queries():
    ds = get_gold_dataset()
    queries = [q.query for q in ds if q.query]
    brands = ["佳能", "索尼", "富士", "奥林巴斯", "尼康", "松下"]
    found = sum(1 for b in brands if any(b in q for q in queries))
    assert found >= 4, f"Only {found} brands covered"


def test_advisor_eval_metrics_aggregation():
    m = AdvisorEvalMetrics(total=10, passed=8, avg_latency_ms=150.0,
                           valuation_rate=0.8, risk_detection_rate=0.6,
                           evidence_rate=0.9, error_rate=0.0)
    assert m.passed == 8
    assert m.valuation_rate == 0.8


def test_eval_result_passed():
    r = AdvisorEvalResult(query_id="T1", query="test", passed=True,
                          recommendation="buy", has_valuation=True,
                          has_risks=True, latency_ms=100)
    assert r.passed
    assert r.recommendation == "buy"
