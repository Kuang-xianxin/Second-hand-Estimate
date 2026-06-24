from collections.abc import Callable, Iterable
from typing import Any


def _fallback_model_id(keyword: str) -> str:
    return (keyword or "").strip().lower()


def canonical_model_id(keyword: str, resolver: Callable[[str], Any]) -> str:
    """Return the stable model id for a keyword-like cache key."""
    model = resolver(keyword)
    if model is None:
        return _fallback_model_id(keyword)
    model_id = getattr(model, "model_id", None)
    if model_id:
        return str(model_id).strip().lower()
    return str(model).strip().lower()


def count_tier_covered_models(
    cached_keywords: Iterable[str],
    tier_keywords: dict[Any, Iterable[str]],
    resolver: Callable[[str], Any],
) -> tuple[dict[Any, int], dict[Any, int]]:
    """
    Count tier coverage by canonical model, not by raw keyword row.

    WHY: A single hot model can have many crawl/search aliases such as
    "佳能ixus130", "canon ixus 130", "ixus130", and "sd1400is"; counting rows
    makes T0 coverage exceed its own expected total.
    """
    expected_model_ids: dict[Any, set[str]] = {
        tier: {
            model_id
            for kw in keywords
            if (model_id := canonical_model_id(kw, resolver))
        }
        for tier, keywords in tier_keywords.items()
    }
    covered_model_ids: dict[Any, set[str]] = {tier: set() for tier in tier_keywords}

    for keyword in cached_keywords:
        model_id = canonical_model_id(keyword, resolver)
        if not model_id:
            continue
        for tier, expected_ids in expected_model_ids.items():
            if model_id in expected_ids:
                covered_model_ids[tier].add(model_id)
                break

    covered = {
        tier: min(len(ids), len(expected_model_ids[tier]))
        for tier, ids in covered_model_ids.items()
    }
    expected = {tier: len(ids) for tier, ids in expected_model_ids.items()}
    return covered, expected
