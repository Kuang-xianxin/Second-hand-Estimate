from enum import Enum
from types import SimpleNamespace

from app.services.tier_coverage import count_tier_covered_models


class FakeTier(Enum):
    T0 = "t0"
    T1 = "t1"
    T2 = "t2"


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


def test_tier_coverage_counts_distinct_canonical_models_not_keyword_rows():
    covered, expected = count_tier_covered_models(
        cached_keywords=[
            "佳能ixus130",
            "canon ixus 130",
            "ixus130",
            "sd1400is",
            "sony t700",
        ],
        tier_keywords={
            FakeTier.T0: ["佳能ixus130", "索尼t700"],
            FakeTier.T1: ["尼康s7000"],
            FakeTier.T2: [],
        },
        resolver=_resolve,
    )

    assert expected[FakeTier.T0] == 2
    assert covered[FakeTier.T0] == 2
    assert covered[FakeTier.T0] <= expected[FakeTier.T0]


def test_tier_coverage_falls_back_to_normalized_cache_keyword():
    covered, expected = count_tier_covered_models(
        cached_keywords=["canon-ixus-130", "CANON-IXUS-130"],
        tier_keywords={
            FakeTier.T0: ["佳能ixus130"],
            FakeTier.T1: [],
            FakeTier.T2: [],
        },
        resolver=_resolve,
    )

    assert expected[FakeTier.T0] == 1
    assert covered[FakeTier.T0] == 1
