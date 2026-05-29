"""
Tests for valuate.py keyword canonicalization and utility functions.
"""
import pytest
import sys
from pathlib import Path

backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

from app.api.valuate import (
    _canonicalize_keyword,
    _condition_bucket,
    _price_bucket,
    _bucket_fill_items,
)


class TestCanonicalizeKeyword:
    def test_empty_keyword(self):
        assert _canonicalize_keyword("") == ""

    def test_whitespace_trimming(self):
        assert _canonicalize_keyword("  Sony T700  ") == "Sony T700"

    def test_multiple_spaces_reduced(self):
        assert _canonicalize_keyword("Sony   T700") == "Sony T700"

    def test_sony_to_sony(self):
        assert _canonicalize_keyword("索尼 T700") == "Sony T700"

    def test_sony_lowercase(self):
        assert _canonicalize_keyword("sony t700") == "Sony T700"

    def test_sony_t700_specific_case(self):
        result = _canonicalize_keyword("索尼T700")
        assert "Sony" in result
        assert "T700" in result

    def test_preserves_numbers(self):
        result = _canonicalize_keyword("Canon IXUS 130")
        assert "130" in result

    def test_canon_ixus_normalization(self):
        result = _canonicalize_keyword("佳能 IXUS 130")
        assert "Canon" in result or "IXUS" in result


class TestConditionBucket:
    def test_quanxin_high_condition(self):
        assert _condition_bucket("全新") == "高成色"
        assert _condition_bucket("99新") == "高成色"
        assert _condition_bucket("95新") == "高成色"
        assert _condition_bucket("9.5新") == "高成色"
        assert _condition_bucket("9成新") == "高成色"

    def test_empty_condition_unknown(self):
        assert _condition_bucket("") == "成色未知"
        assert _condition_bucket("成色未标注") == "成色未知"

    def test_normal_condition(self):
        assert _condition_bucket("8成新") == "普通成色"
        assert _condition_bucket("7成新") == "普通成色"
        assert _condition_bucket("有磨损") == "普通成色"


class TestPriceBucket:
    def test_low_price(self):
        assert _price_bucket(100) == "低价"
        assert _price_bucket(549) == "低价"

    def test_mid_price(self):
        assert _price_bucket(550) == "中价"
        assert _price_bucket(700) == "中价"
        assert _price_bucket(849) == "中价"

    def test_high_price(self):
        assert _price_bucket(850) == "高价"
        assert _price_bucket(1000) == "高价"


class TestBucketFillItems:
    def test_already_enough_items(self, sample_items):
        result = _bucket_fill_items(sample_items[:3], sample_items[3:], 2)
        assert len(result) == 3

    def test_fills_from_candidates(self, sample_items):
        base = sample_items[:2]
        candidates = sample_items[2:]
        result = _bucket_fill_items(base, candidates, target_count=5)
        assert len(result) >= 5

    def test_empty_candidates(self, sample_items):
        result = _bucket_fill_items(sample_items[:3], [], 5)
        assert len(result) == 3

    def test_no_duplicates(self, sample_items):
        base = sample_items[:2]
        candidates = sample_items[2:4]
        result = _bucket_fill_items(base, candidates, target_count=10)
        item_ids = [item.item_id for item in result]
        assert len(item_ids) == len(set(item_ids)), "Duplicates found in result"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
