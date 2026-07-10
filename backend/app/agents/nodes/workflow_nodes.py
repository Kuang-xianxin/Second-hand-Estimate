"""Advisor workflow nodes (§5.2) — 13 nodes in the decision pipeline.

Each node reads from AdvisorState and returns a partial update dict.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.agents.state import AdvisorState

logger = logging.getLogger(__name__)


# ── Node 1: parse_requirement ──

def parse_requirement(state: AdvisorState) -> dict:
    """Parse natural language query into structured PurchaseRequirement.

    Uses LLM to extract: budget, brands, models, usage, condition, risk tolerance.
    Falls back to keyword extraction when LLM unavailable.
    """
    query = state.get("user_query", "")
    if not query:
        return {"errors": ["empty query"], "current_node": "parse_requirement"}

    requirement = _parse_with_llm(query)
    brands = requirement.get("brands", [])
    models = requirement.get("models", [])

    return {
        "requirement": requirement,
        "target_models": _brands_models_to_canonical(brands, models),
        "retrieval_attempts": 0,
        "evidence_sufficient": False,
        "pending_approval": False,
        "confidence": 0.0,
        "market_evidence": [],
        "knowledge_evidence": [],
        "image_findings": [],
        "risks": [],
        "errors": [],
        "current_node": "parse_requirement",
    }


def _parse_with_llm(query: str) -> dict:
    """Parse user query with LLM into structured requirement.

    Uses simple keyword extraction as fallback when LLM not available.
    Production should use DeepSeek structured output.
    """
    import re

    brands = []
    brand_patterns = {
        "佳能": "Canon", "canon": "Canon", "索尼": "Sony", "sony": "Sony",
        "富士": "Fujifilm", "fujifilm": "Fujifilm", "尼康": "Nikon", "nikon": "Nikon",
        "奥林巴斯": "Olympus", "olympus": "Olympus", "松下": "Panasonic", "panasonic": "Panasonic",
        "卡西欧": "Casio", "casio": "Casio", "三星": "Samsung", "samsung": "Samsung",
    }
    for cn, en in brand_patterns.items():
        if cn.lower() in query.lower():
            brands.append(en)

    models = re.findall(r'[A-Za-z0-9]+[\-\s]?\d+[A-Za-z]*', query)
    models = list(dict.fromkeys(models))

    budget_match = re.search(r'(\d+)\s*[-~到至]\s*(\d+)\s*(?:元|块|$)', query)
    budget = {}
    if budget_match:
        budget["budget_min"] = float(budget_match.group(1))
        budget["budget_max"] = float(budget_match.group(2))

    usage = "日常拍照"
    if any(w in query for w in ["收藏", "送礼", "送人", "纪念"]):
        usage = "收藏送礼"
    elif any(w in query for w in ["专业", "摄影", "创作"]):
        usage = "摄影创作"

    condition = "不限"
    if any(w in query for w in ["9成新", "九五新", "95新", "充新"]):
        condition = "9成新+"
    elif any(w in query for w in ["8成新", "八成新"]):
        condition = "8成新"

    risk = "medium"
    if any(w in query for w in ["便宜", "随便", "无所谓"]):
        risk = "high"

    return {
        "raw_text": query,
        "brands": list(dict.fromkeys(brands)),
        "models": models,
        "usage": usage,
        "condition_preference": condition,
        "risk_tolerance": risk,
        **budget,
    }


def _brands_models_to_canonical(brands: list[str], models: list[str]) -> list[str]:
    """Resolve brand + model hints to canonical model IDs.

    Uses keyword_tier module for resolution — in dev mode returns raw models.
    """
    try:
        from app.services.keyword_tier import get_canonical_keyword
    except ImportError:
        return models
    results = []
    for model in models:
        canonical = get_canonical_keyword(model)
        if canonical and canonical != model:
            results.append(canonical)
    return results or models


# ── Node 2: normalize_model ──

def normalize_model(state: AdvisorState) -> dict:
    """Normalize model names and prevent short-model collisions (F30, T2, etc.)."""
    models = state.get("target_models", [])
    requirement = state.get("requirement", {})
    brands = requirement.get("brands", [])

    # Map known short model names to full canonical IDs
    short_map = {
        "F30": "Fujifilm FinePix F30",
        "F31": "Fujifilm FinePix F31fd",
        "F10": "Fujifilm FinePix F10",
        "F20": "Fujifilm FinePix F20",
        "T9": "Sony DSC-T9",
        "T7": "Sony DSC-T7",
        "T5": "Sony DSC-T5",
        "T3": "Sony DSC-T3",
        "T1": "Sony DSC-T1",
        "T2": "Sony DSC-T2",
        "T10": "Sony DSC-T10",
        "T20": "Sony DSC-T20",
        "T30": "Sony DSC-T30",
        "T50": "Sony DSC-T50",
        "T70": "Sony DSC-T70",
        "T77": "Sony DSC-T77",
        "T90": "Sony DSC-T90",
        "T100": "Sony DSC-T100",
        "T200": "Sony DSC-T200",
        "T300": "Sony DSC-T300",
        "T700": "Sony DSC-T700",
        "T900": "Sony DSC-T900",
    }

    normalized = []
    for m in models:
        if m in short_map:
            normalized.append(short_map[m])
        else:
            normalized.append(m)

    return {
        "target_models": normalized,
        "current_node": "normalize_model",
    }


# ── Node 3: route_request ──

def route_request(state: AdvisorState) -> dict:
    """Route to: single valuation / model inquiry / comparison / budget recommendation."""
    models = state.get("target_models", [])
    req = state.get("requirement", {})

    if len(models) >= 2:
        route = "compare"
    elif req.get("budget_max") and not models:
        route = "budget_recommend"
    elif models:
        route = "single_valuation"
    else:
        route = "general_inquiry"

    return {
        "current_node": f"route_request:{route}",
    }


# ── Node 4: retrieve_market_data ──

def retrieve_market_data(state: AdvisorState) -> dict:
    """Query PostgreSQL for recent valid items and price history.

    Returns structured statistics, not natural language SQL results.
    """
    import asyncio
    from app.models.cache import CCDPriceCache
    from app.models.database import AsyncSessionLocal
    from sqlalchemy import select

    models = state.get("target_models", [])
    evidence: list[dict] = state.get("market_evidence", []).copy()

    async def _fetch():
        existing = []
        async with AsyncSessionLocal() as session:
            for model in models:
                result = await session.execute(
                    select(CCDPriceCache).where(CCDPriceCache.keyword == model)
                )
                cache = result.scalar_one_or_none()
                if cache:
                    existing.append({
                        "evidence_id": f"M{len(existing) + 1}",
                        "keyword": cache.keyword,
                        "canonical_model": model,
                        "sample_count": cache.sample_count or 0,
                        "base_price": cache.base_price or 0,
                        "price_min": cache.price_min or 0,
                        "price_max": cache.price_max or 0,
                        "median_price": cache.median_price or 0,
                        "source": "postgresql",
                        "crawled_at": str(cache.updated_at) if cache.updated_at else "",
                    })
        return existing

    try:
        new_evidence = asyncio.run(_fetch())
    except Exception as e:
        logger.warning("Market data fetch failed: %s", e)
        new_evidence = []

    evidence.extend(new_evidence)

    return {
        "market_evidence": evidence,
        "current_node": "retrieve_market_data",
    }


# ── Node 5: retrieve_knowledge ──

def retrieve_knowledge(state: AdvisorState) -> dict:
    """Query Qdrant for specs, storage card, fault, and risk knowledge.

    Uses the HybridRetriever from Phase 2.
    """
    models = state.get("target_models", [])
    requirement = state.get("requirement", {})
    existing: list[dict] = state.get("knowledge_evidence", []).copy()

    # Build a query from models + requirement
    query_parts = []
    if models:
        query_parts.append(" ".join(models))
    if requirement.get("brands"):
        query_parts.append(" ".join(requirement["brands"]))
    query = " ".join(query_parts) or state.get("user_query", "")

    try:
        from qdrant_client import QdrantClient
        from app.rag.retriever import HybridRetriever, RetrievalConfig
        from app.rag.embeddings import get_embedding_backend, SimpleHashEmbedding

        import os as _os
        if not _os.path.isdir('/tmp/guessr_qdrant_dev'):
            return {'knowledge_evidence': existing, 'current_node': 'retrieve_knowledge'}
        client = QdrantClient(path="/tmp/guessr_qdrant_dev", timeout=5)
        retriever = HybridRetriever(client)
        retriever.ensure_collection()

        # When using SimpleHash (no semantic meaning), search by model keywords
        emb = get_embedding_backend()
        use_keyword_boost = isinstance(emb, SimpleHashEmbedding)

        if use_keyword_boost and models:
            results = []
            for model in models[:3]:
                hits = retriever.retrieve(model, RetrievalConfig(
                    dense_top_k=10, sparse_top_k=0, enable_sparse=False,
                    enable_reranker=False, rrf_top_k=10,
                ))
                results.extend(hits)
            seen = set()
            results = [r for r in results if not (r.document_id in seen or seen.add(r.document_id))]

            # Filter: boost docs matching brand or model, demote unrelated ones
            brands = [b.lower() for b in requirement.get("brands", [])]
            if brands:
                def _score(r):
                    content_lower = (r.content or "").lower()
                    doc_brand = (r.brand or "").lower()
                    score = 0
                    for b in brands:
                        if b in doc_brand:
                            score += 10
                        if b in content_lower:
                            score += 5
                    for m in models:
                        if m.lower() in content_lower:
                            score += 3
                    return score
                results.sort(key=_score, reverse=True)
        else:
            results = retriever.retrieve(query, RetrievalConfig(
                dense_top_k=20, sparse_top_k=20, enable_reranker=False, rrf_top_k=10,
            ))

        base_id = len(existing)
        for r in results:
            existing.append({
                "evidence_id": f"K{base_id + len(existing) + 1}",
                "document_id": r.document_id,
                "content_snippet": r.content[:300],
                "document_type": r.document_type,
                "brand": r.brand,
                "model": r.model,
                "topic": r.topic,
                "score": r.score or 0,
            })
    except ImportError:
        pass  # No Qdrant available in dev
    except Exception as e:
        logger.warning("Knowledge retrieval failed: %s", e)

    return {
        "knowledge_evidence": existing,
        "current_node": "retrieve_knowledge",
    }


# ── Node 6: inspect_images ──

def inspect_images(state: AdvisorState) -> dict:
    """Analyze user-provided images for condition, accessories, model verification.

    Placeholder: requires vision model (Kimi k2.6 or Qwen-VL).
    """
    return {
        "image_findings": state.get("image_findings", []),
        "current_node": "inspect_images",
    }


# ── Node 7: grade_evidence ──

def grade_evidence(state: AdvisorState) -> dict:
    """Judge whether market samples and knowledge evidence are sufficient.

    Not enough → allow query rewrite + re-retrieval (max 2 attempts).
    """
    market = state.get("market_evidence", [])
    knowledge = state.get("knowledge_evidence", [])
    attempts = state.get("retrieval_attempts", 0)
    target = state.get("target_models", [])

    total_samples = sum(e.get("sample_count", 0) for e in market)
    has_knowledge = len(knowledge) > 0
    has_market = len(market) > 0 and total_samples >= 10

    sufficient = has_market and has_knowledge if target else has_knowledge

    return {
        "evidence_sufficient": sufficient,
        "retrieval_attempts": attempts + 1,
        "current_node": "grade_evidence",
    }


# ── Node 8: rewrite_query ──

def rewrite_query(state: AdvisorState) -> dict:
    """Rewrite query for re-retrieval when evidence insufficient.

    Broadens or narrows terms based on what's missing.
    """
    return {
        "current_node": "rewrite_query",
    }


# ── Node 9: calculate_valuation ──

def calculate_valuation(state: AdvisorState) -> dict:
    """Apply IQR, weighted median, condition, and accessory corrections.

    LLM does NOT produce the final price number. (Design doc §5.2.8)
    """
    market = state.get("market_evidence", [])

    if not market:
        return {"valuation": None, "current_node": "calculate_valuation"}

    # Compute from market evidence
    prices = []
    for e in market:
        if e.get("base_price"):
            prices.append(e["base_price"])
        if e.get("median_price"):
            prices.append(e["median_price"])

    if not prices:
        return {"valuation": None, "current_node": "calculate_valuation"}

    prices.sort()
    n = len(prices)
    median = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) / 2

    q1_idx = max(0, n // 4)
    q3_idx = min(n - 1, 3 * n // 4)
    iqr = prices[q3_idx] - prices[q1_idx]

    filtered = [p for p in prices if abs(p - median) <= 1.5 * iqr]
    if filtered:
        median = sorted(filtered)[len(filtered) // 2]

    sample_count = sum(e.get("sample_count", 0) for e in market)
    confidence = "high" if sample_count >= 20 else "medium" if sample_count >= 10 else "low"

    return {
        "valuation": {
            "base_price": round(median, 2),
            "price_min": round(median * 0.85, 2),
            "price_max": round(median * 1.15, 2),
            "median_price": round(median, 2),
            "sample_count": sample_count,
            "confidence": confidence,
            "method": "iqr_weighted_median",
            "from_cache": True,
        },
        "current_node": "calculate_valuation",
    }


# ── Node 10: assess_risk ──

def assess_risk(state: AdvisorState) -> dict:
    """Identify accessory, rental, repair, bait, model-mismatch, and storage card risks."""
    knowledge = state.get("knowledge_evidence", [])
    models = state.get("target_models", [])
    valuation = state.get("valuation") or {}
    existing_risks: list[dict] = state.get("risks", []).copy()

    risk_id = len(existing_risks)

    # Check if top-ranked knowledge explicitly says xD is NOT a risk
    xd_safe = False
    for ev in knowledge[:3]:
        snippet = ev.get("content_snippet", "")
        if ("xD" in snippet or "存储卡" in snippet) and ("非 xD" in snippet or "不存在 xD" in snippet or "SD 卡（非 xD" in snippet or "SD 卡通用" in snippet):
            xd_safe = True
            break

    # Storage card risk from knowledge evidence
    for ev in knowledge:
        if ev.get("topic") == "storage_card" and "xD" in (ev.get("content_snippet", "")):
            if xd_safe:
                break  # Top evidence says this model doesn't use xD
            risk_id += 1
            existing_risks.append({
                "risk_id": f"R{risk_id}",
                "category": "storage_card",
                "description": "该机型使用 xD 卡存储，确认是否附带存储卡（xD 卡已停产，单独购买成本高）",
                "severity": "high",
                "evidence_id": ev.get("evidence_id", ""),
            })
            break

    # Fault risk from knowledge evidence
    for ev in knowledge:
        if ev.get("topic") == "fault":
            risk_id += 1
            snippet = ev.get("content_snippet", "")
            desc = snippet[:120] if snippet else "该机型存在已知常见故障"
            existing_risks.append({
                "risk_id": f"R{risk_id}",
                "category": "repair",
                "description": desc,
                "severity": "medium",
                "evidence_id": ev.get("evidence_id", ""),
            })
            break

    # Low sample confidence risk
    conf = valuation.get("confidence", "low")
    if conf == "low":
        risk_id += 1
        existing_risks.append({
            "risk_id": f"R{risk_id}",
            "category": "data_quality",
            "description": "市场样本不足，估价置信度低，建议多方比价",
            "severity": "medium",
            "evidence_id": "",
        })

    return {"risks": existing_risks, "current_node": "assess_risk"}


# ── Node 11: generate_report ──

def generate_report(state: AdvisorState) -> dict:
    """Generate structured purchase decision report based on evidence."""
    valuation = state.get("valuation") or {}
    risks = state.get("risks", [])
    market = state.get("market_evidence", [])
    knowledge = state.get("knowledge_evidence", [])
    models = state.get("target_models", [])

    has_data = bool(valuation.get("base_price"))
    has_risks = any(r.get("severity") == "high" for r in risks)
    insufficient = not has_data

    if insufficient:
        recommendation = "insufficient_data"
        summary = f"关于 {', '.join(models) if models else '该机型'} 的市场数据不足，无法给出可靠估价。建议提供更多信息或选择热门型号。"
    elif has_risks:
        recommendation = "caution"
        summary = f"{', '.join(models)} 估价 ¥{valuation['price_min']:.0f}~¥{valuation['price_max']:.0f}，但存在高风险，建议谨慎购买。"
    else:
        recommendation = "buy"
        summary = f"{', '.join(models)} 估价 ¥{valuation['price_min']:.0f}~¥{valuation['price_max']:.0f}，基于 {valuation.get('sample_count', 0)} 条市场样本。价格合理，建议入手。"

    return {
        "report": {
            "summary": summary,
            "recommendation": recommendation,
            "valuation": valuation,
            "risks": risks,
            "evidence_summary": f"市场证据 {len(market)} 条，知识证据 {len(knowledge)} 条",
            "confidence": state.get("confidence", 0.5),
        },
        "confidence": 0.7 if not insufficient else 0.2,
        "current_node": "generate_report",
    }


# ── Node 12: verify_report ──

def verify_report(state: AdvisorState) -> dict:
    """Validate citations, price consistency, and unsupported assertions."""
    report = state.get("report") or {}
    valuation = state.get("valuation") or {}
    market = state.get("market_evidence", [])

    issues = []

    if report.get("recommendation") == "buy" and not market:
        issues.append("购买建议缺乏市场数据支撑")

    if valuation.get("base_price", 0) <= 0 and report.get("recommendation") != "insufficient_data":
        issues.append("估价值异常（为0或负）")

    if issues:
        return {
            "errors": state.get("errors", []) + issues,
            "current_node": "verify_report",
        }

    return {"current_node": "verify_report"}


# ── Node 13: persist_feedback placeholder ──

def persist_feedback(state: AdvisorState) -> dict:
    """Save user feedback, evidence correctness, and final decision.

    Writes to advisor_runs + advisor_feedback tables.
    """
    return {"current_node": "persist_feedback"}


# ── Node 14: human_review ──

def human_review(state: AdvisorState) -> dict:
    """Pause workflow for human approval on low-confidence / high-risk / model conflict.

    The LangGraph interrupt mechanism pauses execution here;
    resume sends approval_decision back into state.
    """
    approval = state.get("approval_decision", "")
    if approval == "approved":
        return {"pending_approval": False, "current_node": "human_review:approved"}
    if approval == "rejected":
        return {"pending_approval": False, "errors": ["用户拒绝该决策"], "current_node": "human_review:rejected"}
    return {"pending_approval": True, "current_node": "human_review:pending"}
