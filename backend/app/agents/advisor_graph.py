"""Advisor Graph — LangGraph workflow builder.

Assembles the 13-node decision pipeline from design doc §5.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncIterator, Optional

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import AdvisorState
from app.agents.nodes.workflow_nodes import (
    parse_requirement,
    normalize_model,
    route_request,
    retrieve_market_data,
    retrieve_knowledge,
    inspect_images,
    grade_evidence,
    rewrite_query,
    calculate_valuation,
    assess_risk,
    generate_report,
    verify_report,
    human_review,
    persist_feedback,
)
from app.agents.routing import (
    after_parse_requirement,
    after_normalize_model,
    after_route_request,
    after_evidence_gathering,
    after_grade_evidence,
    after_rewrite_query,
    after_calculate_valuation,
    after_assess_risk,
    after_generate_report,
    after_human_review,
    after_verify_report,
    after_persist_feedback,
)

logger = logging.getLogger(__name__)

# Singleton graph + checkpointer
_graph: Optional[StateGraph] = None
_checkpointer = MemorySaver()


def build_advisor_graph() -> StateGraph:
    """Build and compile the LangGraph advisor workflow.

    Workflow (design doc §5.3):
      parse_requirement → normalize_model → route_request
      → retrieve_market_data || retrieve_knowledge || inspect_images
      → grade_evidence
        ├─ insufficient & retries < 3 → rewrite_query → retrieve_knowledge
        ├─ insufficient & retries >= 3 → calculate_valuation (degraded)
        └─ sufficient → calculate_valuation
      → assess_risk → generate_report
        ├─ high_risk | low_confidence → human_review
        │   ├─ approved → verify_report → persist_feedback
        │   └─ rejected → END
        └─ → verify_report → persist_feedback → END
    """
    global _graph
    if _graph is not None:
        return _graph

    wf = StateGraph(AdvisorState)

    # Add all nodes
    wf.add_node("parse_requirement", parse_requirement)
    wf.add_node("normalize_model", normalize_model)
    wf.add_node("route_request", route_request)
    wf.add_node("retrieve_market_data", retrieve_market_data)
    wf.add_node("retrieve_knowledge", retrieve_knowledge)
    wf.add_node("inspect_images", inspect_images)
    wf.add_node("grade_evidence", grade_evidence)
    wf.add_node("rewrite_query", rewrite_query)
    wf.add_node("calculate_valuation", calculate_valuation)
    wf.add_node("assess_risk", assess_risk)
    wf.add_node("generate_report", generate_report)
    wf.add_node("verify_report", verify_report)
    wf.add_node("human_review", human_review)
    wf.add_node("persist_feedback", persist_feedback)

    # Entry
    wf.set_entry_point("parse_requirement")

    # Conditional edges
    wf.add_conditional_edges("parse_requirement", after_parse_requirement, {
        "normalize_model": "normalize_model",
        "retrieve_knowledge": "retrieve_knowledge",
        "__end__": END,
    })
    wf.add_edge("normalize_model", "route_request")
    wf.add_conditional_edges("route_request", after_route_request, {
        "retrieve_market_data": "retrieve_market_data",
    })

    # Parallel evidence gathering → grade
    wf.add_edge("retrieve_market_data", "retrieve_knowledge")
    wf.add_edge("retrieve_knowledge", "inspect_images")
    wf.add_edge("inspect_images", "grade_evidence")

    # Evidence grading loop
    wf.add_conditional_edges("grade_evidence", after_grade_evidence, {
        "calculate_valuation": "calculate_valuation",
        "rewrite_query": "rewrite_query",
    })
    wf.add_conditional_edges("rewrite_query", after_rewrite_query, {
        "retrieve_knowledge": "retrieve_knowledge",
    })

    # Valuation + risk → report
    wf.add_edge("calculate_valuation", "assess_risk")
    wf.add_edge("assess_risk", "generate_report")

    # Report → verify or human review
    wf.add_conditional_edges("generate_report", after_generate_report, {
        "human_review": "human_review",
        "verify_report": "verify_report",
    })

    # Human review gate
    wf.add_conditional_edges("human_review", after_human_review, {
        "verify_report": "verify_report",
        "__end__": END,
    })

    wf.add_edge("verify_report", "persist_feedback")
    wf.add_edge("persist_feedback", END)

    _graph = wf.compile(checkpointer=_checkpointer)
    logger.info("Advisor graph compiled (%d nodes)", len(wf.nodes))
    return _graph


def get_graph():
    """Get or build the singleton compiled graph."""
    return build_advisor_graph()


def get_checkpointer() -> MemorySaver:
    """Return the checkpointer (MemorySaver for dev, AsyncPostgresSaver for prod)."""
    return _checkpointer


async def run_advisor(
    user_query: str,
    thread_id: Optional[str] = None,
) -> dict:
    """Run the advisor workflow synchronously and return final state.

    Args:
        user_query: natural language purchase query
        thread_id: optional conversation thread ID (UUID if not provided)
    """
    graph = get_graph()
    config = {
        "configurable": {
            "thread_id": thread_id or str(uuid.uuid4()),
        }
    }
    initial_state: AdvisorState = {
        "thread_id": config["configurable"]["thread_id"],
        "user_query": user_query,
        "messages": [],
        "market_evidence": [],
        "knowledge_evidence": [],
        "image_findings": [],
        "risks": [],
        "errors": [],
        "target_models": [],
        "retrieval_attempts": 0,
        "evidence_sufficient": False,
        "pending_approval": False,
        "approval_decision": "",
        "confidence": 0.0,
    }

    final_state = await graph.ainvoke(initial_state, config)
    return final_state


async def stream_advisor(
    user_query: str,
    thread_id: Optional[str] = None,
) -> AsyncIterator[dict]:
    """Stream the advisor workflow node-by-node for SSE output.

    Yields dicts with {node, event_type, ...} for each step.
    """
    graph = get_graph()
    config = {
        "configurable": {
            "thread_id": thread_id or str(uuid.uuid4()),
        }
    }
    initial_state: AdvisorState = {
        "thread_id": config["configurable"]["thread_id"],
        "user_query": user_query,
        "messages": [],
        "market_evidence": [],
        "knowledge_evidence": [],
        "image_findings": [],
        "risks": [],
        "errors": [],
        "target_models": [],
        "retrieval_attempts": 0,
        "evidence_sufficient": False,
        "pending_approval": False,
        "approval_decision": "",
        "confidence": 0.0,
    }

    async for event in graph.astream_events(initial_state, config, version="v2"):
        kind = event.get("event")
        if kind == "on_chain_start":
            name = event.get("name", "")
            if name and name not in ("LangGraph", "__start__"):
                yield {"node": name, "event_type": "node_start", "thread_id": config["configurable"]["thread_id"]}
        elif kind == "on_chain_end":
            name = event.get("name", "")
            output = event.get("data", {}).get("output", {})
            if isinstance(output, dict):
                # Extract relevant fields
                current_node = output.get("current_node", name)
                yield {
                    "node": name,
                    "event_type": "node_end",
                    "thread_id": config["configurable"]["thread_id"],
                    "current_node": current_node,
                    "valuation": output.get("valuation"),
                    "risks": output.get("risks"),
                    "report": output.get("report"),
                    "errors": output.get("errors"),
                }


async def resume_advisor(
    thread_id: str,
    approval_decision: str,
) -> dict:
    """Resume a paused workflow with human approval decision.

    Args:
        thread_id: the conversation thread ID
        approval_decision: 'approved' or 'rejected'
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    return await graph.ainvoke(
        {"approval_decision": approval_decision, "pending_approval": False},
        config,
    )
