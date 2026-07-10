"""Tests for LangGraph Advisor workflow."""
import asyncio
import uuid

import pytest

from app.agents.state import AdvisorState
from app.agents.nodes.workflow_nodes import (
    parse_requirement,
    normalize_model,
    route_request,
    retrieve_market_data,
    retrieve_knowledge,
    grade_evidence,
    calculate_valuation,
    assess_risk,
    generate_report,
    verify_report,
    human_review,
)
from app.agents.routing import (
    after_parse_requirement,
    after_grade_evidence,
    after_generate_report,
    after_human_review,
)


# ── Helpers ──

def _empty_state(**overrides) -> AdvisorState:
    s: AdvisorState = {
        "thread_id": str(uuid.uuid4()),
        "user_query": "",
        "requirement": {},
        "target_models": [],
        "market_evidence": [],
        "knowledge_evidence": [],
        "image_findings": [],
        "valuation": None,
        "risks": [],
        "report": None,
        "confidence": 0.0,
        "retrieval_attempts": 0,
        "evidence_sufficient": False,
        "pending_approval": False,
        "approval_decision": "",
        "errors": [],
        "current_node": "",
        "messages": [],
        **overrides,
    }
    return s


# ── Node tests ──

def test_parse_requirement_extracts_brands():
    s = _empty_state(user_query="想买一台佳能IXUS130，预算300到500")
    result = parse_requirement(s)
    req = result.get("requirement", {})
    assert "Canon" in req.get("brands", [])


def test_parse_requirement_extracts_models():
    s = _empty_state(user_query="索尼T900和富士F30哪个好")
    result = parse_requirement(s)
    target = result.get("target_models", [])
    assert any("T900" in m or "F30" in m for m in target)


def test_parse_requirement_extracts_budget():
    s = _empty_state(user_query="500到800元的CCD相机")
    result = parse_requirement(s)
    req = result.get("requirement", {})
    assert req.get("budget_min") == 500
    assert req.get("budget_max") == 800


def test_parse_requirement_empty_query():
    s = _empty_state(user_query="")
    result = parse_requirement(s)
    assert "empty query" in result.get("errors", [])


def test_normalize_model_resolves_short_names():
    s = _empty_state(target_models=["F30", "T900"])
    result = normalize_model(s)
    models = result.get("target_models", [])
    assert any("FinePix" in m for m in models)


def test_route_request_single_model():
    s = _empty_state(target_models=["Canon IXUS 130"])
    result = route_request(s)
    assert "single_valuation" in result.get("current_node", "")


def test_route_request_compare():
    s = _empty_state(target_models=["Canon IXUS 130", "Fujifilm F30"])
    result = route_request(s)
    assert "compare" in result.get("current_node", "")


def test_grade_evidence_insufficient():
    s = _empty_state(market_evidence=[], knowledge_evidence=[], retrieval_attempts=0)
    result = grade_evidence(s)
    assert result.get("evidence_sufficient") is False
    assert result.get("retrieval_attempts") == 1


def test_grade_evidence_sufficient():
    s = _empty_state(
        market_evidence=[{"sample_count": 20, "base_price": 400}],
        knowledge_evidence=[{"document_id": "test", "content_snippet": "test"}],
        target_models=["test"],
    )
    result = grade_evidence(s)
    assert result.get("evidence_sufficient") is True


def test_calculate_valuation_with_data():
    s = _empty_state(
        market_evidence=[
            {"base_price": 350, "median_price": 380, "sample_count": 10},
            {"base_price": 400, "median_price": 420, "sample_count": 15},
        ]
    )
    result = calculate_valuation(s)
    v = result.get("valuation", {})
    assert v.get("base_price", 0) > 0
    assert v.get("sample_count", 0) >= 20
    assert v.get("method") == "iqr_weighted_median"


def test_calculate_valuation_empty():
    s = _empty_state(market_evidence=[])
    result = calculate_valuation(s)
    assert result.get("valuation") is None


def test_assess_risk_adds_low_confidence():
    s = _empty_state(valuation={"confidence": "low", "sample_count": 3})
    result = assess_risk(s)
    risks = result.get("risks", [])
    assert any(r.get("category") == "data_quality" for r in risks)


def test_generate_report_insufficient_data():
    s = _empty_state(valuation=None, target_models=["Unknown"])
    result = generate_report(s)
    report = result.get("report", {})
    assert report.get("recommendation") == "insufficient_data"


def test_generate_report_buy():
    s = _empty_state(
        valuation={"base_price": 400, "price_min": 340, "price_max": 460, "sample_count": 25},
        target_models=["Canon IXUS 130"],
    )
    result = generate_report(s)
    report = result.get("report", {})
    assert report.get("recommendation") == "buy"


def test_verify_report_passes():
    s = _empty_state(
        report={"recommendation": "buy"},
        valuation={"base_price": 400},
        market_evidence=[{"sample_count": 20}],
    )
    result = verify_report(s)
    assert not result.get("errors")


def test_verify_report_flags_missing_data():
    s = _empty_state(
        report={"recommendation": "buy"},
        valuation={"base_price": 400},
        market_evidence=[],
    )
    result = verify_report(s)
    assert result.get("errors")


def test_human_review_pending():
    s = _empty_state(approval_decision="")
    result = human_review(s)
    assert result.get("pending_approval") is True


def test_human_review_approved():
    s = _empty_state(approval_decision="approved")
    result = human_review(s)
    assert result.get("pending_approval") is False


# ── Routing tests ──

def test_after_parse_requirement_with_models():
    s = _empty_state(target_models=["IXUS130"])
    assert after_parse_requirement(s) == "normalize_model"


def test_after_parse_requirement_no_models():
    s = _empty_state(target_models=[])
    assert after_parse_requirement(s) == "retrieve_knowledge"


def test_after_parse_requirement_error():
    s = _empty_state(errors=["error"])
    assert after_parse_requirement(s) == "__end__"


def test_after_grade_evidence_sufficient():
    s = _empty_state(evidence_sufficient=True)
    assert after_grade_evidence(s) == "calculate_valuation"


def test_after_grade_evidence_retry():
    s = _empty_state(evidence_sufficient=False, retrieval_attempts=1)
    assert after_grade_evidence(s) == "rewrite_query"


def test_after_grade_evidence_max_retries():
    s = _empty_state(evidence_sufficient=False, retrieval_attempts=3)
    assert after_grade_evidence(s) == "calculate_valuation"


def test_after_generate_report_high_risk():
    s = _empty_state(risks=[{"severity": "high", "category": "storage_card"}])
    assert after_generate_report(s) == "human_review"


def test_after_generate_report_low_confidence():
    s = _empty_state(confidence=0.1, risks=[])
    assert after_generate_report(s) == "human_review"


def test_after_generate_report_ok():
    s = _empty_state(confidence=0.7, risks=[{"severity": "low"}])
    assert after_generate_report(s) == "verify_report"


def test_after_human_review_approved():
    s = _empty_state(approval_decision="approved")
    assert after_human_review(s) == "verify_report"


def test_after_human_review_rejected():
    s = _empty_state(approval_decision="rejected")
    assert after_human_review(s) == "__end__"


# ── Graph compilation test ──

def test_graph_compiles():
    """Verify the graph compiles without errors."""
    from app.agents.advisor_graph import get_graph
    graph = get_graph()
    assert graph is not None
    # Graph should have nodes
    nodes = graph.get_graph().nodes
    assert len(nodes) >= 10


# ── Full run test ──

@pytest.mark.asyncio
async def test_full_advisor_run():
    """End-to-end test: run the graph with a real query."""
    from app.agents.advisor_graph import run_advisor
    result = await run_advisor("想买富士F30，预算300到500元")
    assert result is not None
    assert "thread_id" in result
    # Should have completed at least some nodes
    current = result.get("current_node", "")
    assert current  # at least one node executed
