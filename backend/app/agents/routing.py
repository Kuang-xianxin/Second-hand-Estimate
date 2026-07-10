"""Routing logic — conditional edges for the LangGraph workflow.

Decides which node to execute next based on current state.
"""
from __future__ import annotations

from app.agents.state import AdvisorState


def after_parse_requirement(state: AdvisorState) -> str:
    """After parsing, route to normalize if models found, else end."""
    if state.get("errors"):
        return "__end__"
    if state.get("target_models"):
        return "normalize_model"
    return "retrieve_knowledge"


def after_normalize_model(state: AdvisorState) -> str:
    return "route_request"


def after_route_request(state: AdvisorState) -> str:
    """Route to parallel evidence gathering."""
    return "retrieve_market_data"


def after_evidence_gathering(state: AdvisorState) -> str:
    """After market + knowledge + images, grade evidence."""
    return "grade_evidence"


def after_grade_evidence(state: AdvisorState) -> str:
    """If sufficient → valuation; if can retry → rewrite; else → report."""
    if state.get("evidence_sufficient"):
        return "calculate_valuation"
    attempts = state.get("retrieval_attempts", 0)
    if attempts < 3:
        return "rewrite_query"
    return "calculate_valuation"


def after_rewrite_query(state: AdvisorState) -> str:
    """Re-retrieve after query rewrite."""
    return "retrieve_knowledge"


def after_calculate_valuation(state: AdvisorState) -> str:
    return "assess_risk"


def after_assess_risk(state: AdvisorState) -> str:
    return "generate_report"


def after_generate_report(state: AdvisorState) -> str:
    """Check if report needs human review before verification."""
    risks = state.get("risks", [])
    confidence = state.get("confidence", 0)
    has_high_risk = any(r.get("severity") == "high" or r.get("severity") == "critical" for r in risks)
    if has_high_risk or confidence < 0.3:
        return "human_review"
    return "verify_report"


def after_human_review(state: AdvisorState) -> str:
    """After human review: approved → verify, rejected → end."""
    if state.get("approval_decision") == "approved":
        return "verify_report"
    return "__end__"


def after_verify_report(state: AdvisorState) -> str:
    return "persist_feedback"


def after_persist_feedback(state: AdvisorState) -> str:
    return "__end__"
