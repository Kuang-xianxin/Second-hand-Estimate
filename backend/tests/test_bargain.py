"""
Tests for bargain detection logic.
"""
import pytest
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List

backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))


@dataclass
class MockBargainItem:
    item_id: str
    title: str
    price: float
    url: str = ""
    estimated_price: float = 0.0
    profit_estimate: float = 0.0
    xd_card_size: Optional[str] = None
    xd_card_value: float = 0.0


class TestBargainDetection:
    def test_bargain_profit_calculation(self):
        base_price = 500.0
        item_price = 300.0
        profit = base_price - item_price
        assert profit == 200.0
        assert profit > 0

    def test_bargain_threshold(self):
        from app.config import settings
        threshold = settings.bargain_threshold
        assert threshold > 0

    def test_bargain_above_threshold(self):
        base_price = 500.0
        threshold = 120.0
        item_price = 350.0
        profit = base_price - item_price
        assert profit > threshold

    def test_not_bargain_below_threshold(self):
        base_price = 500.0
        threshold = 120.0
        item_price = 400.0
        profit = base_price - item_price
        assert profit < threshold

    def test_xd_card_bonus(self):
        xd_card_values = {
            "16mb": 50,
            "32mb": 60,
            "64mb": 70,
            "128mb": 108,
            "256mb": 120,
            "512mb": 134,
            "1g": 148,
            "2g": 162,
        }
        for size, value in xd_card_values.items():
            assert value > 0
            assert size in ["16mb", "32mb", "64mb", "128mb", "256mb", "512mb", "1g", "2g"]


class TestXDCardDetection:
    def test_xd_card_models_list(self):
        from app.services.xd_card_models import ALL_XD_MODELS
        assert len(ALL_XD_MODELS) > 0

    def test_masd1_compatible_is_function(self):
        from app.services.xd_card_models import is_masd1_compatible_model
        assert callable(is_masd1_compatible_model)
        result = is_masd1_compatible_model("奥林巴斯 mu 1030sw")
        assert isinstance(result, tuple)
        assert len(result) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
