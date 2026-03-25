import json
import statistics
from typing import List, Tuple
from dataclasses import dataclass


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


def calculate_price(
    prices: List[float],
    low_weight: float = 0.15,
    high_weight: float = 0.05,
) -> PricingResult:
    """
    核心估价算法：
    1. IQR 去极值
    2. 正常价格取均值作为基准
    3. 低价和高价做加权修正（低价有一定参考，说明市场有低价存在）
    4. 计算合理区间
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

    base = statistics.mean(normal)

    # 低价修正：如果市场有大量低价，说明竞争激烈，适当下调基准
    if low:
        low_avg = statistics.mean(low)
        base = base * (1 - low_weight) + low_avg * low_weight

    # 高价修正：高价参考权重低
    if high:
        high_avg = statistics.mean(high)
        base = base * (1 - high_weight) + high_avg * high_weight

    # 合理区间：基准 ± 20%
    price_min = round(base * 0.80, 2)
    price_max = round(base * 1.20, 2)
    base = round(base, 2)

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
