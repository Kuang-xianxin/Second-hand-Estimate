from types import SimpleNamespace

from app.services.tier_coverage import count_model_covered_models


MODEL_ALIASES = {
    "佳能ixus130": "canon-ixus-130",
    "canon ixus 130": "canon-ixus-130",
    "ixus130": "canon-ixus-130",
    "sd1400is": "canon-ixus-130",
    "索尼t700": "sony-t700",
    "sony t700": "sony-t700",
    "尼康s7000": "nikon-s7000",
}


def _resolve(keyword: str):
    model_id = MODEL_ALIASES.get((keyword or "").strip().lower())
    if not model_id:
        return None
    return SimpleNamespace(model_id=model_id)


def test_model_coverage_counts_distinct_canonical_models_not_keyword_rows():
    covered, expected = count_model_covered_models(
        cached_keywords=[
            "佳能ixus130",
            "canon ixus 130",
            "ixus130",
            "sd1400is",
            "sony t700",
        ],
        expected_model_ids=["canon-ixus-130", "sony-t700", "nikon-s7000"],
        resolver=_resolve,
    )

    assert expected == 3
    assert covered == 2
    assert covered <= expected


def test_model_coverage_falls_back_to_normalized_cache_keyword():
    covered, expected = count_model_covered_models(
        cached_keywords=["canon-ixus-130", "CANON-IXUS-130"],
        expected_model_ids=["佳能ixus130"],
        resolver=_resolve,
    )

    assert expected == 1
    assert covered == 1
