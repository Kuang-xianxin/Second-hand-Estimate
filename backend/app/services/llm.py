import json
import asyncio
import logging
from typing import Optional
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


async def call_qwen_secondary(prompt: str) -> dict:
    if not settings.qwen_api_key:
        return {"error": "未配置 Qwen API Key"}
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.qwen_base_url.rstrip('/')}/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.qwen_api_key}"},
                json={
                    "model": settings.qwen_model_secondary,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_llm_json(content, settings.qwen_model_secondary)
    except httpx.HTTPStatusError as e:
        return {"error": _map_http_error("Qwen-Secondary", e.response.status_code, e.response.text)}
    except Exception as e:
        return {"error": _map_request_error("Qwen-Secondary", e)}


async def call_openai(prompt: str) -> dict:
    if not settings.openai_api_key:
        return {"error": "未配置 OpenAI API Key"}
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.openai_base_url.rstrip('/')}/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.openai_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_llm_json(content, settings.openai_model)
    except httpx.HTTPStatusError as e:
        return {"error": _map_http_error("OpenAI", e.response.status_code, e.response.text)}
    except Exception as e:
        return {"error": _map_request_error("OpenAI", e)}


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


async def multi_model_valuation(
    keyword: str,
    base_price: float,
    prices: list,
    sample_count: int,
) -> list[LLMValuation]:
    """并发调用三个大模型，返回估价结果列表"""
    prompt = _build_prompt(keyword, base_price, prices, sample_count)
    ds, qw, qw2, oa = await asyncio.gather(
        call_deepseek(prompt),
        call_qwen(prompt),
        call_qwen_secondary(prompt),
        call_openai(prompt),
    )

    results = [
        _to_valuation(ds, settings.deepseek_model),
        _to_valuation(qw, settings.qwen_model),
        _to_valuation(qw2, settings.qwen_model_secondary),
        _to_valuation(oa, settings.openai_model),
    ]

    if all(r.error for r in results):
        logger.warning("三个模型全部不可用，回退到算法估价")
        return [
            _fallback_by_algorithm(settings.deepseek_model, base_price),
            _fallback_by_algorithm(settings.qwen_model, base_price),
            _fallback_by_algorithm(settings.qwen_model_secondary, base_price),
            _fallback_by_algorithm(settings.openai_model, base_price),
        ]

    return results
