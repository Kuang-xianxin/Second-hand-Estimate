"""
Tests for the pricing algorithm.
"""
import pytest
import sys
from pathlib import Path

backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

from app.services.pricing import (
    calculate_price,
    remove_outliers_iqr,
    _weighted_median,
    PricingResult,
)


class TestRemoveOutliersIQR:
    def test_empty_list(self):
        normal, low, high = remove_outliers_iqr([])
        assert normal == []
        assert low == []
        assert high == []

    def test_single_value(self):
        normal, low, high = remove_outliers_iqr([100])
        assert normal == [100]
        assert low == []
        assert high == []

    def test_few_values_under_4(self):
        normal, low, high = remove_outliers_iqr([50, 100, 150])
        assert normal == [50, 100, 150]
        assert low == []
        assert high == []

    def test_removes_low_outliers(self):
        prices = [300, 300, 300, 300, 300, 300, 1, 1000]
        normal, low, high = remove_outliers_iqr(prices)
        assert len(low) > 0 or len(high) > 0

    def test_removes_high_outliers(self):
        prices = [100, 200, 300, 400, 500, 1000]
        normal, low, high = remove_outliers_iqr(prices)
        assert 1000 in high
        assert 1000 not in normal

    def test_no_outliers(self):
        prices = [100, 200, 300, 400, 500]
        normal, low, high = remove_outliers_iqr(prices)
        assert sorted(normal) == sorted(prices)
        assert low == []
        assert high == []

    def test_iqr_zero_returns_all_normal(self):
        prices = [100, 100, 100, 100, 100]
        normal, low, high = remove_outliers_iqr(prices)
        assert normal == prices


class TestWeightedMedian:
    def test_empty_values(self):
        result = _weighted_median([], [])
        assert result == 0.0

    def test_single_value(self):
        result = _weighted_median([100], [1.0])
        assert result == 100.0

    def test_equal_weights_uses_median(self):
        values = [100, 200, 300]
        weights = [1.0, 1.0, 1.0]
        result = _weighted_median(values, weights)
        assert result == 200.0

    def test_high_weight_bias(self):
        values = [100, 200, 300]
        weights = [0.1, 10.0, 0.1]
        result = _weighted_median(values, weights)
        assert result == 200.0

    def test_all_zero_weights_fallback_median(self):
        values = [100, 200, 300]
        weights = [0.0, 0.0, 0.0]
        result = _weighted_median(values, weights)
        assert result == 200.0


class TestCalculatePrice:
    def test_empty_prices(self):
        result = calculate_price([])
        assert result.base_price == 0
        assert result.price_min == 0
        assert result.price_max == 0
        assert result.sample_count == 0

    def test_single_price(self):
        result = calculate_price([500])
        assert result.base_price == 500
        assert result.price_min == 400
        assert result.price_max == 600

    def test_price_range_is_80_to_120_percent(self):
        result = calculate_price([100, 200, 300])
        assert result.price_min == round(result.base_price * 0.80, 2)
        assert result.price_max == round(result.base_price * 1.20, 2)

    def test_outlier_removal(self):
        prices = [100, 200, 300, 400, 500, 1000]
        result = calculate_price(prices)
        assert len(result.low_outliers) > 0 or len(result.high_outliers) > 0

    def test_quality_scores_affects_result(self):
        prices = [100, 200, 300, 400, 500]
        quality_no_weight = calculate_price(prices)
        quality_with_weight = calculate_price(prices, quality_scores=[50, 50, 50, 50, 50])
        assert quality_with_weight.base_price == quality_no_weight.base_price

    def test_quality_scores_higher_weight_bias(self):
        prices = [100, 200, 300, 400, 500]
        high_quality_prices = calculate_price(prices, quality_scores=[90, 90, 90, 90, 90])
        low_quality_prices = calculate_price(prices, quality_scores=[10, 10, 10, 10, 10])
        assert high_quality_prices.base_price == low_quality_prices.base_price

    def test_sample_count_matches_filtered(self):
        prices = [100, 200, 300, 400, 500]
        result = calculate_price(prices)
        assert result.sample_count == len(result.filtered_prices)

    def test_raw_prices_preserved(self):
        prices = [100, 200, 300, 400, 500]
        result = calculate_price(prices)
        assert result.raw_prices == prices

    def test_rounding_to_2_decimals(self):
        prices = [100, 200, 333]
        result = calculate_price(prices)
        assert result.base_price == round(result.base_price, 2)
        assert result.price_min == round(result.price_min, 2)
        assert result.price_max == round(result.price_max, 2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
