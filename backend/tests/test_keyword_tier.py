"""Tests for keyword tier and canonical model system."""
import sys
from pathlib import Path

backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

import pytest
from app.services.keyword_tier import (
    KeywordTier, CanonicalModel, get_canonical_model, get_model_by_id,
    get_keywords_by_tier, get_tier, get_canonical_keyword, get_display_name,
    get_tier_counts, get_t0_model_ids, get_model_keywords_for_pricing,
    get_all_keywords,
)
from app.services.ccd_keywords import get_model_keyword_groups


class TestKeywordTierIndices:
    def test_indices_built(self):
        assert len(get_all_keywords()) > 0
        counts = get_tier_counts()
        assert counts["t0"] > 0
        assert counts["t1"] > 0
        assert len(get_all_keywords()) == len(get_model_keyword_groups()) == 673

    def test_similar_models_stay_distinct_while_duplicates_are_removed(self):
        groups = get_model_keyword_groups()
        assert len(groups) == 673
        assert sum("ixus300" in [keyword.lower() for keyword in group] for group in groups) == 1
        assert sum("ixus300hs" in [keyword.lower() for keyword in group] for group in groups) == 1
        assert get_canonical_model("ixus300").model_id != get_canonical_model("ixus300hs").model_id

    def test_t0_models_defined(self):
        model_ids = get_t0_model_ids()
        assert len(model_ids) >= 40, f"T0 should have >=40 models, got {len(model_ids)}"

    def test_t0_keywords_have_canonical(self):
        t0_kw = get_keywords_by_tier(KeywordTier.T0_HOT)
        for kw in t0_kw[:10]:
            model = get_canonical_model(kw)
            assert model is not None, f"T0 keyword '{kw}' missing canonical model"
            assert model.tier == KeywordTier.T0_HOT


class TestCanonicalModelMapping:
    def test_ixus130_mapping(self):
        keywords = ["佳能ixus130", "canon ixus 130", "ixus130", "sd1400is"]
        model_ids = set()
        for kw in keywords:
            model = get_canonical_model(kw)
            assert model is not None
            model_ids.add(model.model_id)
        assert len(model_ids) == 1
        assert "canon-ixus-130" in model_ids

    def test_ixus130_pricing_keywords(self):
        pricing_kw = get_model_keywords_for_pricing("佳能ixus130")
        assert len(pricing_kw) >= 4

    def test_canonical_keyword(self):
        assert get_canonical_keyword("佳能ixus130") == "canon-ixus-130"
        assert get_canonical_keyword("sd1400is") == "canon-ixus-130"
        assert get_canonical_model("canon-ixus-130").model_id == "canon-ixus-130"

    def test_non_hot_aliases_share_one_model(self):
        group = next(
            group
            for group in get_model_keyword_groups()
            if "canon a5" in [keyword.lower() for keyword in group]
        )
        model_ids = {get_canonical_model(keyword).model_id for keyword in group}
        assert len(model_ids) == 1

    def test_unknown_keyword_tier(self):
        assert get_tier("不存在的关键词xyz123") == KeywordTier.T2_COLD


class TestKeywordTierFunctions:
    def test_t0_not_empty(self):
        assert len(get_keywords_by_tier(KeywordTier.T0_HOT)) > 0

    def test_t1_not_empty(self):
        assert len(get_keywords_by_tier(KeywordTier.T1_WARM)) > 0

    def test_no_duplicates_between_tiers(self):
        t0 = set(kw.strip().lower() for kw in get_keywords_by_tier(KeywordTier.T0_HOT))
        t1 = set(kw.strip().lower() for kw in get_keywords_by_tier(KeywordTier.T1_WARM))
        overlap = t0 & t1
        assert len(overlap) == 0, f"T0/T1 overlap: {overlap}"

    def test_all_keywords_coverage(self):
        all_kw = set(kw.strip().lower() for kw in get_all_keywords())
        t0 = set(kw.strip().lower() for kw in get_keywords_by_tier(KeywordTier.T0_HOT))
        t1 = set(kw.strip().lower() for kw in get_keywords_by_tier(KeywordTier.T1_WARM))
        t2 = set(kw.strip().lower() for kw in get_keywords_by_tier(KeywordTier.T2_COLD))
        assert t0.issubset(all_kw)
        assert t1.issubset(all_kw)
        assert t2.issubset(all_kw)
        assert not (t0 & t1 or t0 & t2 or t1 & t2)
        assert len(all_kw) == len(t0) + len(t1) + len(t2)


class TestHotModelExamples:
    @pytest.mark.parametrize("keyword,expected_model_id", [
        ("佳能ixus130", "canon-ixus-130"),
        ("canon ixus 130", "canon-ixus-130"),
        ("ixus130", "canon-ixus-130"),
        ("sd1400is", "canon-ixus-130"),
        ("索尼t700", "sony-t700"),
        ("sony t700", "sony-t700"),
        ("dsc-t700", "sony-t700"),
        ("t700", "sony-t700"),
        ("富士f100", "fuji-f100fd"),
        ("f100fd", "fuji-f100fd"),
        ("尼康s7000", "nikon-s7000"),
        ("索尼w800", "sony-w800"),
        ("奥林巴斯μ300", "olympus-mu300"),
        ("mu300", "olympus-mu300"),
        ("松下fx01", "panasonic-fx01"),
        ("dmc-fx01", "panasonic-fx01"),
        ("卡西欧z3", "casio-z3"),
        ("ex-z3", "casio-z3"),
    ])
    def test_hot_model_mapping(self, keyword, expected_model_id):
        model = get_canonical_model(keyword)
        assert model is not None, f"'{keyword}' not found"
        assert model.model_id == expected_model_id, \
            f"'{keyword}' -> '{model.model_id}', expected '{expected_model_id}'"
        assert model.tier == KeywordTier.T0_HOT


class TestBackwardCompatibility:
    def test_get_all_keywords_returns_list(self):
        from app.services.keyword_tier import get_all_keywords as tier_get_all
        keywords = tier_get_all()
        assert isinstance(keywords, list)
        assert len(keywords) > 100
        assert all(isinstance(kw, str) for kw in keywords)

    def test_ccd_keywords_still_works(self):
        from app.services.ccd_keywords import get_all_keywords as old_get_all
        keywords = old_get_all()
        assert len(keywords) > 100
