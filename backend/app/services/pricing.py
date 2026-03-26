import statistics
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class PricingResult:
    base_price: float        # 基准估价
    price_min: float         # 合理区间下限
    price_max: float         # 合理区间上限
    sample_count: int        # 参与计算的样本数
    raw_prices: List[float]  # 原始价格列表
    filtered_prices: List[float]  # 去极值后的价格列表
    low_outliers: List[float]     # 过低价格（可能捡漏）
    high_outliers: List[float]    # 过高价格


def remove_outliers_iqr(prices: List[float]) -> Tuple[List[float], List[float], List[float]]:
    """
    使用 IQR 方法去除极端值。
    返回 (正常价格, 过低价格, 过高价格)
    """
    if len(prices) < 4:
        return prices, [], []

    sorted_p = sorted(prices)
    n = len(sorted_p)
    q1 = sorted_p[n // 4]
    q3 = sorted_p[(3 * n) // 4]
    iqr = q3 - q1

    if iqr == 0:
        return prices, [], []

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    normal = [p for p in prices if lower_bound <= p <= upper_bound]
    low = [p for p in prices if p < lower_bound]
    high = [p for p in prices if p > upper_bound]

    return normal, low, high


def _weighted_median(values: List[float], weights: List[float]) -> float:
    if not values:
        return 0.0
    pairs = sorted(zip(values, weights), key=lambda x: x[0])
    total = sum(w for _, w in pairs)
    if total <= 0:
        return statistics.median(values)

    acc = 0.0
    half = total / 2
    for v, w in pairs:
        acc += w
        if acc >= half:
            return v
    return pairs[-1][0]


def calculate_price(
    prices: List[float],
    quality_scores: Optional[List[float]] = None,
) -> PricingResult:
    """
    第一版强鲁棒 + 质量加权估价：
    1. IQR 去极值，超低/超高价群基本不影响结果
    2. 默认使用正常样本中位数
    3. 若提供质量分（功能优先），改用质量加权中位数
    """
    if not prices:
        return PricingResult(
            base_price=0, price_min=0, price_max=0,
            sample_count=0, raw_prices=[], filtered_prices=[],
            low_outliers=[], high_outliers=[]
        )

    normal, low, high = remove_outliers_iqr(prices)
    if not normal:
        normal = prices
        low, high = [], []

    base = statistics.median(normal)

    if quality_scores and len(quality_scores) == len(prices):
        if len(prices) >= 4:
            sorted_p = sorted(prices)
            n = len(sorted_p)
            q1 = sorted_p[n // 4]
            q3 = sorted_p[(3 * n) // 4]
            iqr = q3 - q1
            if iqr > 0:
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                values = []
                weights = []
                for p, q in zip(prices, quality_scores):
                    if lower_bound <= p <= upper_bound:
                        values.append(p)
                        weights.append(max(0.1, float(q) / 100.0))
                if values:
                    base = _weighted_median(values, weights)
            else:
                weights = [max(0.1, float(q) / 100.0) for q in quality_scores]
                base = _weighted_median(prices, weights)
        else:
            weights = [max(0.1, float(q) / 100.0) for q in quality_scores]
            base = _weighted_median(prices, weights)

    base = round(base, 2)
    price_min = round(base * 0.80, 2)
    price_max = round(base * 1.20, 2)

    return PricingResult(
        base_price=base,
        price_min=price_min,
        price_max=price_max,
        sample_count=len(normal),
        raw_prices=prices,
        filtered_prices=normal,
        low_outliers=low,
        high_outliers=high,
    )
