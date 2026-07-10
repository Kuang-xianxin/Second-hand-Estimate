"""Cost & latency tracking middleware for advisor runs.

Logs: model calls, token usage, node latency, errors.
Design doc §10.1: LangSmith Trace integration (opt-in).
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class NodeTrace:
    """Timing and status for one workflow node."""
    node_name: str
    started_at: str = ""
    finished_at: str = ""
    duration_ms: float = 0
    status: str = "pending"  # pending / ok / error / skipped
    error: str = ""


@dataclass
class RunTrace:
    """Full trace for one advisor run."""
    thread_id: str
    user_query: str
    started_at: str = ""
    finished_at: str = ""
    total_duration_ms: float = 0
    node_count: int = 0
    nodes: list[NodeTrace] = field(default_factory=list)
    model_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    langsmith_run_id: str = ""


# In-memory trace store (dev); production → PostgreSQL advisor_runs table
_traces: dict[str, RunTrace] = {}


def start_trace(thread_id: str, user_query: str) -> RunTrace:
    trace = RunTrace(
        thread_id=thread_id,
        user_query=user_query[:200],
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    _traces[thread_id] = trace
    return trace


def record_node(trace: RunTrace, node_name: str, duration_ms: float, status: str = "ok", error: str = ""):
    trace.nodes.append(NodeTrace(
        node_name=node_name,
        started_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=round(duration_ms, 1),
        status=status,
        error=error,
    ))


def finish_trace(trace: RunTrace, errors: list[str] | None = None):
    trace.finished_at = datetime.now(timezone.utc).isoformat()
    trace.errors = errors or []
    trace.node_count = len(trace.nodes)
    # Estimate cost: DeepSeek ~$0.14/1M input, $0.28/1M output
    if trace.tokens_in > 0:
        trace.estimated_cost_usd = round(
            (trace.tokens_in / 1_000_000) * 0.14
            + (trace.tokens_out / 1_000_000) * 0.28,
            6,
        )


def get_trace(thread_id: str) -> RunTrace | None:
    return _traces.get(thread_id)
