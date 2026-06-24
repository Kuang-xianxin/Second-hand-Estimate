from collections.abc import Callable, Iterable


def _fallback_model_id(keyword: str) -> str:
    return (keyword or "").strip().lower()


def canonical_model_id(keyword: str, resolver: Callable[[str], object]) -> str:
    """Return the stable model id for a keyword-like cache key."""
    model = resolver(keyword)
    if model is None:
        return _fallback_model_id(keyword)
    model_id = getattr(model, "model_id", None)
    if model_id:
        return str(model_id).strip().lower()
    return str(model).strip().lower()


def count_model_covered_models(
    cached_keywords: Iterable[str],
    expected_model_ids: Iterable[str],
    resolver: Callable[[str], object],
) -> tuple[int, int]:
    """
    Count unified crawl coverage by canonical model, not by raw keyword row.

    WHY: A single hot model can have many crawl/search aliases such as
    "佳能ixus130", "canon ixus 130", "ixus130", and "sd1400is"; counting rows
    makes model coverage exceed its own expected total.
    """
    expected_ids = {
        model_id
        for kw in expected_model_ids
        if (model_id := canonical_model_id(kw, resolver))
    }
    covered_ids: set[str] = set()

    for keyword in cached_keywords:
        model_id = canonical_model_id(keyword, resolver)
        if model_id and model_id in expected_ids:
            covered_ids.add(model_id)

    return min(len(covered_ids), len(expected_ids)), len(expected_ids)
