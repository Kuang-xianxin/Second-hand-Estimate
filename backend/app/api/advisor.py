"""Advisor API — FastAPI router for LangGraph advisor workflow.

Endpoints:
  POST /api/advisor/runs          — start a new advisor run
  GET  /api/advisor/runs/{id}/stream  — SSE node-level events
  GET  /api/advisor/runs/{id}     — get run state
  POST /api/advisor/runs/{id}/decisions  — human approval
  POST /api/advisor/runs/{id}/feedback   — user feedback
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.advisor_graph import run_advisor, stream_advisor, resume_advisor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


class AdvisorRunRequest(BaseModel):
    query: str
    thread_id: Optional[str] = None


class AdvisorRunResponse(BaseModel):
    run_id: str
    thread_id: str
    status: str


class ApprovalRequest(BaseModel):
    decision: str  # "approved" | "rejected"


class FeedbackRequest(BaseModel):
    rating: int | None = None
    evidence_correct: bool | None = None
    price_accurate: bool | None = None
    advice_adopted: bool | None = None
    comment: str = ""


@router.post("/runs", response_model=AdvisorRunResponse)
async def start_advisor_run(req: AdvisorRunRequest):
    """Start a new advisor run."""
    thread_id = req.thread_id or str(uuid.uuid4())

    try:
        result = await run_advisor(req.query, thread_id)
        status = "completed"
        if result.get("pending_approval"):
            status = "paused"
        elif result.get("errors"):
            status = "failed"

        return AdvisorRunResponse(
            run_id=thread_id,
            thread_id=thread_id,
            status=status,
        )
    except Exception as e:
        logger.exception("Advisor run failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}/stream")
async def stream_advisor_run(run_id: str, query: str = Query(...)):
    """Stream advisor node-level events via SSE."""
    async def event_generator():
        try:
            async for event in stream_advisor(query, run_id):
                yield f"data: {json.dumps(event, default=str)}\n\n"
            yield "data: {\"event_type\": \"done\"}\n\n"
        except Exception as e:
            yield f"data: {{\"event_type\": \"error\", \"error\": \"{str(e)}\"}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs/{run_id}")
async def get_advisor_run(run_id: str):
    """Get current state of an advisor run."""
    from app.agents.advisor_graph import get_graph
    graph = get_graph()
    config = {"configurable": {"thread_id": run_id}}
    try:
        state = await graph.aget_state(config)
        if state is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return {
            "run_id": run_id,
            "status": "paused" if state.values.get("pending_approval") else "completed",
            "state": {k: v for k, v in state.values.items()
                      if k not in ("messages",) and not callable(v)},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runs/{run_id}/decisions")
async def submit_decision(run_id: str, req: ApprovalRequest):
    """Submit human approval decision to resume a paused run."""
    if req.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    try:
        result = await resume_advisor(run_id, req.decision)
        return {
            "run_id": run_id,
            "status": "completed" if not result.get("errors") else "failed",
            "state": {
                "report": result.get("report"),
                "confidence": result.get("confidence"),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runs/{run_id}/feedback")
async def submit_feedback(run_id: str, req: FeedbackRequest):
    """Save user feedback for an advisor run."""
    # Phase 4: persist to advisor_feedback table
    return {"run_id": run_id, "status": "recorded"}
