import json
import asyncio
import logging
from typing import Optional, List
from dataclasses import dataclass

import httpx
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMValuation:
    model_name: str
    suggested_price: float
    price_min: float
    price_max: float
    reasoning: str
    confidence: str  # 高/中/低
    error: Optional[str] = None


def _build_prompt(keyword: str, base_price: float, prices: list, sample_count: int) -> str:
    prices_str = ", ".join([f"{p}元" for p in sorted(prices)[:30]])
    return f"""你是一位二手商品定价专家。请根据以下市场数据，对「{keyword}」进行估价分析。

市场数据：
- 参考样本数量：{sample_count} 条
- 算法基准价：{base_price} 元
- 市场价格样本（部分）：{prices_str}

请返回 JSON 格式，字段如下：
{{
  "suggested_price": 建议成交价（数字，元）, 
  "price_min": 合理区间下限（数字，元）, 
  "price_max": 合理区间上限（数字，元）, 
  "reasoning": "你的分析理由（100字以内）", 
  "confidence": "高" 或 "中" 或 "低"
}}

只返回 JSON，不要其他内容。"""


def _parse_llm_json(text: str, model_name: str) -> dict:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                text = part
                break
    try:
        return json.loads(text)
    except Exception:
        logger.warning(f"{model_name} 返回非 JSON: {text[:200]}")
        return {}


def _map_http_error(provider: str, status_code: int, raw_error: str) -> str:
    if status_code == 401:
        return f"{provider} 认证失败(401)：请检查 API Key 是否正确"
    if status_code == 403:
        return f"{provider} 权限不足(403)：请检查账号或模型权限"
    if status_code == 429:
        return f"{provider} 触发限流(429)：请稍后重试"
    if status_code >= 500:
        return f"{provider} 服务异常({status_code})：请稍后重试"
    return f"{provider} 请求失败({status_code})：{raw_error[:180]}"


def _map_request_error(provider: str, e: Exception) -> str:
    return f"{provider} 网络异常：{repr(e)}"


async def call_deepseek(prompt: str) -> dict:
    if not settings.deepseek_api_key:
        return {"error": "未配置 DeepSeek API Key"}
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.deepseek_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": settings.deepseek_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_llm_json(content, settings.deepseek_model)
    except httpx.HTTPStatusError as e:
        return {"error": _map_http_error("DeepSeek", e.response.status_code, e.response.text)}
    except Exception as e:
        return {"error": _map_request_error("DeepSeek", e)}


async def call_qwen(prompt: str) -> dict:
    if not settings.qwen_api_key:
        return {"error": "未配置 Qwen API Key"}
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.qwen_base_url.rstrip('/')}/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.qwen_api_key}"},
                json={
                    "model": settings.qwen_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_llm_json(content, settings.qwen_model)
    except httpx.HTTPStatusError as e:
        return {"error": _map_http_error("Qwen", e.response.status_code, e.response.text)}
    except Exception as e:
        return {"error": _map_request_error("Qwen", e)}


async def call_kimi(prompt: str) -> dict:
    if not settings.kimi_api_key:
        return {"error": "未配置 Kimi API Key"}
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.kimi_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.kimi_api_key}"},
                json={
                    "model": settings.kimi_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_llm_json(content, settings.kimi_model)
    except httpx.HTTPStatusError as e:
        return {"error": _map_http_error("Kimi", e.response.status_code, e.response.text)}
    except Exception as e:
        return {"error": _map_request_error("Kimi", e)}


def _to_valuation(data: dict, model_name: str) -> LLMValuation:
    if "error" in data:
        return LLMValuation(
            model_name=model_name,
            suggested_price=0,
            price_min=0,
            price_max=0,
            reasoning="",
            confidence="低",
            error=data["error"],
        )
    return LLMValuation(
        model_name=model_name,
        suggested_price=float(data.get("suggested_price", 0)),
        price_min=float(data.get("price_min", 0)),
        price_max=float(data.get("price_max", 0)),
        reasoning=data.get("reasoning", ""),
        confidence=data.get("confidence", "中"),
    )


def _fallback_by_algorithm(model_name: str, base_price: float) -> LLMValuation:
    price_min = round(base_price * 0.9, 2)
    price_max = round(base_price * 1.1, 2)
    return LLMValuation(
        model_name=model_name,
        suggested_price=round(base_price, 2),
        price_min=price_min,
        price_max=price_max,
        reasoning="当前大模型服务暂不可用，已回退到算法估价结果",
        confidence="低",
        error="模型服务不可用，使用算法估价回退",
    )


async def classify_camera_items_by_llm(keyword: str, items: List[dict]) -> List[dict]:
    """使用 DeepSeek 对样本进行品牌/型号/整机/功能状态筛选，返回通过项。"""
    if not items:
        return []

    if not settings.deepseek_api_key:
        # 未配置模型时直接回退到规则过滤结果（由调用方先做）
        return items

    compact = []
    for idx, it in enumerate(items, start=1):
        compact.append({
            "idx": idx,
            "title": str(it.get("title", ""))[:120],
            "description": str(it.get("description", ""))[:160],
            "price": it.get("price", 0),
        })

    prompt = f"""你是二手相机市场数据清洗助手。请识别并剔除明显的配件/零件/耗材商品，保留整机。

目标关键词：{keyword}

【强制排除规则】（满足任意一条立即排除）：
- 商品是单独的电池、充电器、数据线、屏幕/液晶屏、镜头盖、USB盖、外壳、背带、贴膜、读卡器、内存卡、滤镜等配件
- 商品是维修零件、拆机件、说明书
- 价格低于 200 元且标题不含"整机"/"相机"/"机身"等整机词（配件通常低于100元，整机通常高于400元）

【保留规则】：
- 标题或描述中有整机特征词：整机、相机、机身、套机、CCD、长焦、像素、变焦等
- 价格在 400 元以上的二手相机商品
- 有疑问时，价格 > 300 元的优先保留

候选列表(JSON)：
{json.dumps(compact, ensure_ascii=False)}

只返回 JSON：
{{"keep_indices": [1,2,...], "reason": "一句话"}}
不要输出任何其他文本。"""
    try:
        data = await call_deepseek(prompt)
        if "error" in data:
            logger.warning(f"LLM样本筛选失败: {data['error']}")
            return items

        keep_indices = data.get("keep_indices", [])
        if not isinstance(keep_indices, list):
            return items

        keep_set = {int(x) for x in keep_indices if str(x).isdigit()}
        if not keep_set:
            # LLM 清零保护：fallback 到原始列表
            logger.warning("LLM筛选后0条，自动回退到规则筛选结果")
            return items

        filtered = []
        for idx, it in enumerate(items, start=1):
            if idx in keep_set:
                filtered.append(it)
        return filtered
    except Exception as e:
        logger.warning(f"LLM样本筛选异常: {repr(e)}")
        return items


async def multi_model_valuation(
    keyword: str,
    base_price: float,
    prices: list,
    sample_count: int,
) -> list[LLMValuation]:
    """并发调用三个大模型，返回估价结果列表"""
    prompt = _build_prompt(keyword, base_price, prices, sample_count)
    ds, qw, km = await asyncio.gather(
        call_deepseek(prompt),
        call_qwen(prompt),
        call_kimi(prompt),
    )

    results = [
        _to_valuation(ds, settings.deepseek_model),
        _to_valuation(qw, settings.qwen_model),
        _to_valuation(km, settings.kimi_model),
    ]

    if all(r.error for r in results):
        logger.warning("三个模型全部不可用，回退到算法估价")
        return [
            _fallback_by_algorithm(settings.deepseek_model, base_price),
            _fallback_by_algorithm(settings.qwen_model, base_price),
            _fallback_by_algorithm(settings.kimi_model, base_price),
        ]

    return results
