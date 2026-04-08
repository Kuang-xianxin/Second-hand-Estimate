import json
import asyncio
import logging
import re
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


def _build_prompt(
    keyword: str,
    base_price: float,
    prices: list,
    sample_count: int,
    is_xd_card_model: bool = False,
    xd_card_bundle_count: int = 0,
) -> str:
    prices_str = ", ".join([f"{p}元" for p in sorted(prices)[:30]])

    xd_context = ""
    if is_xd_card_model:
        xd_context = f"""
【特别重要：XD卡机型背景】
您查询的相机型号「{keyword}」是使用XD存储卡的老相机。
- XD卡（富士/奥林巴斯专用小卡，2cm×2cm）目前市场均价约¥50~175元/张
- 部分卖家会「捆绑销售」：相机总价中可能包含了一张XD卡的价格
- 部分卖家会「自备卡」：在标题/描述中写"自备XD卡"、"XD卡另购"等，实际商品不含卡

【估价要求】：
1. 如果样本中看到"自备XD卡"/"XD卡另购"等描述，该价格就是纯相机价格，纳入正常估价
2. 如果样本标题含"XD卡"/"带卡"/"送卡"且标明了容量（如"带1G卡"）：
   → 这类商品的总价包含了相机+卡的价格，需要降权处理！
   → 降权原因：卡的价值不应计入相机估价，且带卡卖家的相机往往成色稍差或着急出手
   → 处理方式：将带卡商品的价格视为虚高，参考不带卡/自备卡的纯相机样本做估价
3. 优先参考「自备XD卡」或「不带卡」的纯相机样本，它们更能反映真实市场价格

已知本次样本中带卡捆绑商品约 {xd_card_bundle_count} 件，请重点关注并适当降权处理。
"""

    return f"""你是一位二手商品定价专家。请根据以下市场数据，对「{keyword}」进行估价分析。

市场数据：
- 参考样本数量：{sample_count} 条
- 算法基准价：{base_price} 元
- 市场价格样本（部分）：{prices_str}
{xd_context}
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
                    "temperature": 1.0,
                    "max_tokens": 8000,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_llm_json(content, settings.deepseek_model)
    except httpx.HTTPStatusError as e:
        return {"error": _map_http_error("DeepSeek", e.response.status_code, e.response.text)}
    except Exception as e:
        return {"error": _map_request_error("DeepSeek", e)}


async def call_deepseek_vision(images: List[str], prompt: str) -> dict:
    """调用 DeepSeek 多模态接口分析图片（含视觉的 deepseek-chat）"""
    if not settings.deepseek_api_key:
        return {"error": "未配置 DeepSeek API Key"}
    if not images:
        return {"error": "无图片"}
    content = []
    for img_url in images[:3]:
        content.append({"type": "image_url", "image_url": {"url": img_url}})
    content.append({"type": "text", "text": prompt})
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.deepseek_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": settings.deepseek_vision_model,
                    "messages": [{"role": "user", "content": content}],
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            return _parse_llm_json(text, settings.deepseek_vision_model)
    except httpx.HTTPStatusError as e:
        return {"error": _map_http_error("DeepSeek-Vision", e.response.status_code, e.response.text)}
    except Exception as e:
        return {"error": _map_request_error("DeepSeek-Vision", e)}


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


async def call_doubao(prompt: str) -> dict:
    if not settings.doubao_api_key:
        return {"error": "未配置豆包 API Key"}
    try:
        async with httpx.AsyncClient(timeout=settings.doubao_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.doubao_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.doubao_api_key}"},
                json={
                    "model": settings.doubao_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_llm_json(content, settings.doubao_model)
    except httpx.HTTPStatusError as e:
        return {"error": _map_http_error("豆包", e.response.status_code, e.response.text)}
    except Exception as e:
        return {"error": _map_request_error("豆包", e)}


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


async def call_qwen_vision(images: List[str], prompt: str) -> dict:
    """调用 Qwen VL 多模态接口分析图片"""
    if not settings.qwen_api_key:
        return {"error": "未配置 Qwen API Key"}
    if not images:
        return {"error": "无图片"}
    content = []
    for img_url in images[:4]:
        content.append({"type": "image_url", "image_url": {"url": img_url}})
    content.append({"type": "text", "text": prompt})
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                resp = await client.post(
                    f"{settings.qwen_vision_base_url.rstrip('/')}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.qwen_api_key}"},
                    json={
                        "model": settings.qwen_vision_model,
                        "messages": [{"role": "user", "content": content}],
                        "temperature": 0.2,
                        "max_tokens": 400,
                    },
                )
                if resp.status_code == 429 and attempt == 0:
                    logger.warning("Qwen Vision 429，等待4秒后重试...")
                    await asyncio.sleep(4)
                    continue
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"]
                return _parse_llm_json(text, settings.qwen_vision_model)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt == 0:
                logger.warning("Qwen Vision 429，等待4秒后重试...")
                await asyncio.sleep(4)
                continue
            return {"error": _map_http_error("Qwen Vision", e.response.status_code, e.response.text)}
        except Exception as e:
            return {"error": _map_request_error("Qwen Vision", e)}
    return {"error": "Qwen Vision 持续限流(429)，请稍后重试"}


async def call_doubao_vision(images: List[str], prompt: str) -> dict:
    """调用豆包多模态接口分析图片，429时自动重试一次"""
    if not settings.doubao_api_key:
        return {"error": "未配置豆包 API Key"}
    if not images:
        return {"error": "无图片"}
    content = []
    for img_url in images[:4]:
        content.append({"type": "image_url", "image_url": {"url": img_url}})
    content.append({"type": "text", "text": prompt})
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=settings.doubao_timeout_seconds) as client:
                resp = await client.post(
                    f"{settings.doubao_vision_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.doubao_api_key}"},
                    json={
                        "model": settings.doubao_vision_model,
                        "messages": [{"role": "user", "content": content}],
                        "temperature": 0.2,
                        "max_tokens": 400,
                    },
                )
                if resp.status_code == 429 and attempt == 0:
                    logger.warning("豆包Vision 429，等待4秒后重试...")
                    await asyncio.sleep(4)
                    continue
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"]
                return _parse_llm_json(text, settings.doubao_vision_model)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt == 0:
                logger.warning("豆包Vision 429，等待4秒后重试...")
                await asyncio.sleep(4)
                continue
            return {"error": _map_http_error("豆包Vision", e.response.status_code, e.response.text)}
        except Exception as e:
            return {"error": _map_request_error("豆包Vision", e)}
    return {"error": "豆包Vision 持续限流(429)，请稍后重试"}


def _title_alias_match(keyword: str, title: str) -> bool:
    """关键词与标题的型号后缀别名匹配（如 j150 与 j150w）。"""
    kw = (keyword or "").lower().replace(" ", "")
    tt = (title or "").lower().replace(" ", "")

    # 富士 j/z/a/f/s + 数字：允许附加 w/s/f/fd 后缀
    m = re.search(r'([jzafs]\d{3,4})', kw)
    if m:
        core = m.group(1)
        aliases = {core, core + 'w', core + 's', core + 'f', core + 'fd'}
        return any(a in tt for a in aliases)

    return False


async def check_image_model_match(item_id: str, keyword: str, title: str, images: List[str]) -> dict:
    """轻量视觉核查：仅在“高置信明显不符”时排除，避免误杀。"""
    if not images:
        return {"item_id": item_id, "match": True, "reason": "无图片跳过"}

    prompt = f"""请观察图片，判断这个商品是否与目标型号一致。
目标型号：{keyword}
商品标题：{title}

请只返回 JSON：
{{"is_target_model": true或false, "confidence": "high"或"low", "reason": "一句话"}}
规则：
- 只有在你能明确看出是其他型号/配件时，才返回 is_target_model=false 且 confidence=high。
- 图片模糊、信息不足、看不清型号时，返回 is_target_model=true 且 confidence=low（默认保留）。
只返回JSON，不要其他文字。"""

    try:
        data = await call_qwen_vision(images, prompt)
        if isinstance(data, dict) and not data.get("error"):
            is_target = bool(data.get("is_target_model", True))
            confidence = str(data.get("confidence", "low")).lower()
            reason = data.get("reason", "")

            # 仅高置信不符才排除，且标题命中别名时优先保留
            if (not is_target) and confidence == "high":
                if _title_alias_match(keyword, title):
                    return {"item_id": item_id, "match": True, "reason": "标题命中型号别名，保留"}
                if "无法" in reason or "看不清" in reason or "不确定" in reason:
                    return {"item_id": item_id, "match": True, "reason": reason or "低确定性保留"}
                return {"item_id": item_id, "match": False, "reason": reason or "图片型号不符"}
            return {"item_id": item_id, "match": True, "reason": reason or "低置信保留"}
    except Exception:
        pass

    return {"item_id": item_id, "match": True, "reason": "检查失败默认保留"}

def _normalize_xd_size(size: str) -> str:
    """将模型返回的容量字符串标准化到XD_CARD_PRICES的key格式。"""
    s = (size or "").lower().strip()
    # 去掉空格和gb/mb等单位
    s = re.sub(r"\s+(gb|mb)", r"\1", s)
    # 处理 "512mb 高速" 之类
    is_high = "高速" in size or "hs" in s or "high" in s
    # 提取数字+单位
    m = re.search(r"(\d+)\s*(gb|mb)", s)
    if m:
        num, unit = m.group(1), m.group(2)
        key = f"{num}{unit}"
        if is_high:
            key += "高速"
        return key
    # 直接映射常见词
    for known in ["16mb", "32mb", "64mb", "128mb", "256mb", "512mb", "1g", "2g"]:
        if known in s:
            if is_high and known in ["512mb", "1g", "2g"]:
                return f"{known}高速"
            return known
    return ""


def _merge_xd_vote_results(results: list) -> dict:
    """
    多模型投票融合。
    results: 各模型返回的 dict 列表，每项含 has_xd_card / card_size / reason / model
    返回融合后的 dict：
    - has_xd_card: 任意一个模型high置信说有，且不超过1个模型说无 → True
    - card_size: 取票数最多的那个，或最高置信的那个
    """
    has_votes = {"yes": [], "no": [], "skip": []}
    size_votes = {}

    for r in results:
        if not isinstance(r, dict) or r.get("error"):
            continue
        has = bool(r.get("has_xd_card", False))
        size = r.get("card_size", "") or ""
        conf = str(r.get("confidence", "low")).lower()
        reason = r.get("reason", "")

        if conf == "low" and not has:
            has_votes["skip"].append(r)
        elif has:
            has_votes["yes"].append(r)
            size_votes[size] = size_votes.get(size, 0) + (2 if conf == "high" else 1)
        else:
            has_votes["no"].append(r)

    # 投票规则：有 > 无（且无的high不超过1个）→ 有
    high_no_count = sum(1 for r in has_votes["no"] if str(r.get("confidence", "low")).lower() == "high")
    if len(has_votes["yes"]) >= 1 and high_no_count <= 1:
        # 选容量：取票数最多者
        if size_votes:
            best_size = max(size_votes, key=size_votes.get)
        else:
            best_size = ""
        # 取reason：优先用high置信的理由
        all_reasons = has_votes["yes"]
        all_reasons.sort(key=lambda x: 0 if str(x.get("confidence", "")).lower() == "high" else 1)
        best_reason = all_reasons[0].get("reason", "") if all_reasons else ""
        return {
            "has_xd_card": True,
            "card_size": _normalize_xd_size(best_size),
            "confidence": "high" if len(has_votes["yes"]) >= 2 else "medium",
            "reason": best_reason,
            "vote_detail": {"yes": len(has_votes["yes"]), "no": len(has_votes["no"]), "skip": len(has_votes["skip"])},
        }
    return {
        "has_xd_card": False,
        "card_size": "",
        "confidence": "low",
        "reason": "多模型无明确有卡判断",
        "vote_detail": {"yes": len(has_votes["yes"]), "no": len(has_votes["no"]), "skip": len(has_votes["skip"])},
    }


XD_CARD_VISION_PROMPT_TEMPLATE = """你是一个专业的二手数码相机配件识别专家。请仔细观察这些图片，判断商品是否捆绑了XD存储卡（常见于富士/奥林巴斯老相机）。

商品标题：{title}

请严格观察以下内容：
1. 【配件全家福】：相机旁边是否有XD卡（超小型方形卡，约2cm×2cm，白色或银灰色，正面标注xD图标）
2. 【电池仓/卡槽】：有些XD卡槽设计在电池仓旁边，图片中是否能看到电池仓内或旁边有卡
3. 【拍照界面】：LCD屏幕上是否显示储存介质为"xD"或"xD-Picture"，而不是"IN"（索尼记忆棒）或"SD"
4. 【存储数量】：部分相机LCD显示可存储照片数量极大（如999+），说明可能配了大容量XD卡

注意：XD卡非常小（约拇指盖一半），不要和SD卡（长方形）混淆。

请只返回JSON，不要其他文字：
{{"has_xd_card": true或false,
  "card_size": "16mb"/"32mb"/"64mb"/"128mb"/"256mb"/"512mb"/"1g"/"2g"/"未知容量"（如不确定填"未知容量"）,
  "confidence": "high"或"low",
  "reason": "一句话描述你看到了什么"}}

判断规则：
- 清楚看到XD卡在相机旁边 → has_xd_card=true，confidence=high
- 看到电池仓旁边有小卡但不确定 → has_xd_card=true，confidence=low
- 拍照界面显示xD储存介质 → has_xd_card=true，confidence=high
- 照片数量显示999+极大 → has_xd_card=true，confidence=medium，卡容量填"未知容量"
- 只能看到相机没有卡 → has_xd_card=false
- 图片模糊什么都看不清 → has_xd_card=false，confidence=low"""


async def check_xd_card_from_images(item_id: str, title: str, images: List[str]) -> dict:
    """
    多模型并行检测商品图片是否捆绑XD卡。
    Qwen VL + Doubao Vision + DeepSeek Vision 三路并发，取投票结果。
    """
    if not images:
        return {"item_id": item_id, "has_xd_card": False, "card_size": "", "confidence": "low", "reason": "无图片跳过"}

    # 标题已声明自备卡，直接跳过
    title_lower = (title or "").lower()
    for pat in [r"xd卡自备", r"卡自备", r"不带卡", r"不含卡", r"无卡"]:
        if re.search(pat, title_lower):
            return {"item_id": item_id, "has_xd_card": False, "card_size": "", "confidence": "low", "reason": "标题已声明自备卡"}

    prompt = XD_CARD_VISION_PROMPT_TEMPLATE.format(title=title)
    imgs = images[:3]

    # 三模型并行（任一失败不影响其他）
    tasks = []
    model_names = []

    if settings.qwen_api_key:
        tasks.append(call_qwen_vision(imgs, prompt))
        model_names.append("qwen")

    if settings.doubao_api_key:
        tasks.append(call_doubao_vision(imgs, prompt))
        model_names.append("doubao")

    if settings.deepseek_api_key:
        tasks.append(call_deepseek_vision(imgs, prompt))
        model_names.append("deepseek")

    if not tasks:
        return {"item_id": item_id, "has_xd_card": False, "card_size": "", "confidence": "low", "reason": "未配置任何视觉模型"}

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # 给结果打上模型标签
    labeled = []
    for i, r in enumerate(raw_results):
        if isinstance(r, Exception):
            labeled.append({"model": model_names[i] if i < len(model_names) else "unknown", "error": str(r)})
        else:
            r["model"] = model_names[i] if i < len(model_names) else "unknown"
            labeled.append(r)

    # 投票融合
    merged = _merge_xd_vote_results(labeled)
    final_size = _normalize_xd_size(merged.get("card_size", ""))

    logger.info(f"XD卡多模型检测: item={item_id}, vote={merged.get('vote_detail')}, size={final_size}, reason={merged.get('reason', '')[:50]}")

    return {
        "item_id": item_id,
        "has_xd_card": merged.get("has_xd_card", False),
        "card_size": final_size,
        "confidence": merged.get("confidence", "low"),
        "reason": merged.get("reason", ""),
        "vote_detail": merged.get("vote_detail", {}),
    }


async def analyze_item_images(item_id: str, title: str, images: List[str], price: float = 0.0, base_price: float = 0.0) -> dict:
    """分析单个商品图片成色（单模型，快速），并检查成色差时价格是否合理"""
    if not images:
        return {"item_id": item_id, "image_score": None, "image_flags": [], "error": "无图片"}
    prompt = f"""你是二手相机成色鉴定专家。请仔细观察这些图片，对商品「{title}」进行成色评估。

请返回 JSON：
{{"condition_score": 0-100的整数（100=全新无痕，80=轻微使用痕迹，60=明显磨损，40=严重磨损）,
  "is_complete_unit": true或false（是否是整机而非配件/零件）,
  "visible_defects": ["缺陷描述1", "缺陷描述2"],
  "brief": "一句话总结"}}
只返回JSON，不要其他内容。"""

    # 单模型快速分析（Qwen VL）
    data = await call_qwen_vision(images, prompt)
    if isinstance(data, Exception) or not isinstance(data, dict) or data.get("error") or not data.get("condition_score"):
        return {"item_id": item_id, "image_score": None, "image_flags": [], "error": str(data.get("error", "Qwen VL无返回")) if isinstance(data, dict) else "异常"}

    valid = [float(data["condition_score"])]
    is_complete = data.get("is_complete_unit", True)
    all_defects = data.get("visible_defects", [])[:3]
    all_briefs = [data["brief"]] if data.get("brief") else []

    if not valid:
        return {"item_id": item_id, "image_score": None, "image_flags": [], "error": "模型未返回有效结果"}

    score = round(sum(valid) / len(valid), 1)
    flags = []
    if not is_complete:
        flags.append("图片判断:非整机")
    seen_defects = set()
    for d in all_defects:
        if d not in seen_defects:
            flags.append(f"图片缺陷:{d}")
            seen_defects.add(d)
    if all_briefs:
        flags.append(f"图片总结:{all_briefs[0]}")

    # 成色很差（<45分）且价格偏高（>400元）时标记降权
    price_penalty = False
    # 成色很差且价格虚高：商品价格高于基准价的80%才触发降权（说明卖家没有体现成色折扣）
    price_high_threshold = base_price * 0.8 if base_price > 0 else float('inf')
    if score < 45 and price > 0 and price > price_high_threshold:
        flags.append("图片警告:成色差但价格偏高，已降权")
        price_penalty = True

    return {
        "item_id": item_id,
        "image_score": score,
        "is_complete_unit": is_complete,
        "image_flags": flags,
        "price_penalty": price_penalty,
        "error": None,
    }


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

    prompt = f"""你是二手相机市场数据清洗助手。请识别并剔除不符合目标型号的商品，只保留目标型号的整机。

目标关键词：{keyword}

【强制排除规则】（满足任意一条立即排除）：
- 型号与目标关键词不一致（例如目标是"ixus700"，则"ixus130"、"ixus70"、"700D"、"A700"、"R700"等均需排除）
- 商品是单独的电池、充电器、数据线、屏幕/液晶屏、镜头盖、USB盖、外壳、背带、贴膜、读卡器、内存卡、滤镜等配件
- 商品是维修零件、拆机件、说明书
- 价格低于 200 元且标题不含"整机"/"相机"/"机身"等整机词

【保留规则】：
- 标题或描述中明确包含目标型号（允许空格变体，如"ixus 700"="ixus700"）
- 是该型号的整机（相机/机身/套机），功能正常或有轻微外观问题
- 有疑问时宁可排除，保证精准度

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
    is_xd_card_model: bool = False,
    xd_card_bundle_count: int = 0,
) -> list[LLMValuation]:
    """并发调用三个大模型，返回估价结果列表

    is_xd_card_model: 是否为XD卡机型（会自动在prompt中注入降权提示）
    xd_card_bundle_count: 检测到的带卡捆绑商品数量（prompt中告知模型降权处理）
    """
    prompt = _build_prompt(keyword, base_price, prices, sample_count,
                           is_xd_card_model=is_xd_card_model,
                           xd_card_bundle_count=xd_card_bundle_count)
    ds, qw, db = await asyncio.gather(
        call_deepseek(prompt),
        call_qwen(prompt),
        call_doubao(prompt),
    )

    results = [
        _to_valuation(ds, settings.deepseek_model),
        _to_valuation(qw, settings.qwen_model),
        _to_valuation(db, settings.doubao_model),
    ]

    if all(r.error for r in results):
        logger.warning("三个模型全部不可用，回退到算法估价")
        return [
            _fallback_by_algorithm(settings.deepseek_model, base_price),
            _fallback_by_algorithm(settings.qwen_model, base_price),
            _fallback_by_algorithm(settings.doubao_model, base_price),
        ]

    return results
