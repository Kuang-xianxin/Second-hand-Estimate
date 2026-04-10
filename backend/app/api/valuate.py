import asyncio
import json
import logging
import re
import uuid
import webbrowser
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict
from pathlib import Path

from app.models.database import get_db
from app.models.item import CrawledItem, ValuationRecord, BargainAlert
from app.crawler.xianyu import get_crawler
from app.services.pricing import calculate_price
from app.services.llm import multi_model_valuation, classify_camera_items_by_llm, call_deepseek as call_deepseek_fn, call_qwen as call_qwen_fn, call_doubao as call_kimi_fn, analyze_item_images, check_xd_card_from_images, _build_prompt as _build_prompt_for_stream, _to_valuation as _to_valuation_raw
from app.services.bargain import detect_bargains, filter_target_items, filter_target_items_with_reasons, detect_xd_card_model_from_items, strip_xd_card_prices, merge_xd_bundle_with_vision
from app.config import settings

router = APIRouter(prefix="/api", tags=["估价"])
logger = logging.getLogger(__name__)

# 内存中的流式任务控制器：支持并行估价 + 按任务停止
stream_task_controls: Dict[str, Dict[str, object]] = {}

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_STATE_FILE = BASE_DIR / "xianyu_storage_state.json"


class ValuateRequest(BaseModel):
    keyword: str
    cookies: Optional[str] = None


def _canonicalize_keyword(keyword: str) -> str:
    text = re.sub(r"\s+", " ", keyword.strip())
    text = re.sub(r"([A-Za-z]+)\s*([0-9]+)", r"\1 \2", text)
    text = text.replace("索尼", "Sony")
    text = re.sub(r"\bsony\b", "Sony", text, flags=re.IGNORECASE)

    if re.search(r"\bSony\s*T\s*700\b", text, flags=re.IGNORECASE):
        return "Sony T700"

    return text


def _debug_not_enough_items(crawler, keyword: str):
    summary = getattr(crawler, '_last_debug_summary', {}) or {}

    response_count = int(summary.get('response_count', 0) or 0)
    statuses = [s.get('status') for s in summary.get('response_statuses', []) if isinstance(s, dict)]
    ret_samples = [str(x) for x in summary.get('response_ret_samples', [])]

    login_hint = bool(summary.get('login_page_hint'))
    risk_hint = bool(summary.get('risk_page_hint'))

    ret_text = ' | '.join(ret_samples)

    if response_count == 0:
        if login_hint:
            detail = "未获取到搜索接口响应，疑似登录态失效。请重新登录闲鱼并同步 Cookie。"
            status_code = 401
        elif risk_hint:
            detail = "未获取到搜索接口响应，疑似触发风控验证。请稍后重试或先在闲鱼网页完成验证。"
            status_code = 429
        else:
            detail = "未命中闲鱼搜索接口，可能是网络波动或页面结构变化，请稍后重试。"
            status_code = 502
    elif any(code in (401, 403) for code in statuses):
        detail = "闲鱼接口返回未授权（401/403），请重新登录闲鱼并同步 Cookie。"
        status_code = 401
    elif any(code == 429 for code in statuses):
        detail = "闲鱼接口触发限流（429），请稍后再试。"
        status_code = 429
    elif any(k in ret_text for k in ["SESSION", "LOGIN", "FAIL_SYS_SESSION_EXPIRED", "FAIL_SYS_TOKEN_EXOIRED"]):
        detail = "闲鱼返回登录态过期，请重新登录闲鱼并同步 Cookie。"
        status_code = 401
    elif any(k in ret_text for k in ["FAIL_SYS_USER_VALIDATE", "RGV587", "验证码", "风控"]):
        detail = "闲鱼返回风控校验，请先在网页完成验证后重试。"
        status_code = 429
    else:
        raw_count = int(summary.get('raw_item_count', 0) or 0)
        normalized_count = int(summary.get('normalized_count', 0) or 0)
        final_count = int(summary.get('final_count', 0) or 0)

        if raw_count == 0:
            detail = f"关键词“{keyword}”未抓到可用商品数据，请换关键词再试。"
        elif normalized_count == 0:
            detail = f"关键词“{keyword}”抓到原始数据但解析失败，建议稍后重试。"
        elif final_count < 3:
            detail = f"关键词“{keyword}”有效样本不足（仅 {final_count} 条），请换更具体的关键词。"
        else:
            detail = "有效数据不足，请换个关键词或稍后再试。"
        status_code = 422

    return {
        "status_code": status_code,
        "detail": detail,
        "debug": {
            "keyword": keyword,
            **summary,
        },
    }


def _condition_bucket(condition: str) -> str:
    text = (condition or "").strip()
    if any(k in text for k in ["全新", "99新", "95新", "9.5", "9成新"]):
        return "高成色"
    if text in ["", "成色未标注"]:
        return "成色未知"
    return "普通成色"


def _price_bucket(price: float) -> str:
    if price < 550:
        return "低价"
    if price < 850:
        return "中价"
    return "高价"


def _to_valuation_for_stream(data: dict, model_name: str) -> dict:
    """把 LLM 返回的 dict 转成可 JSON 序列化的 dict（供 SSE 推送）"""
    v = _to_valuation_raw(data, model_name)
    return {
        "model": v.model_name,
        "suggested_price": v.suggested_price,
        "price_min": v.price_min,
        "price_max": v.price_max,
        "reasoning": v.reasoning,
        "confidence": v.confidence,
        "error": v.error,
    }


def _bucket_fill_items(base_items: list, candidates: list, target_count: int) -> list:
    """按成色/价格段分桶补样，尽量覆盖不同区间。"""
    if len(base_items) >= target_count or not candidates:
        return base_items

    buckets = {}
    for it in candidates:
        key = (_condition_bucket(getattr(it, "condition", "")), _price_bucket(float(getattr(it, "price", 0))))
        buckets.setdefault(key, []).append(it)

    result = list(base_items)
    used_ids = {x.item_id for x in result}
    keys = list(buckets.keys())

    while len(result) < target_count and keys:
        progressed = False
        for k in keys:
            arr = buckets.get(k, [])
            while arr and arr[0].item_id in used_ids:
                arr.pop(0)
            if arr:
                picked = arr.pop(0)
                result.append(picked)
                used_ids.add(picked.item_id)
                progressed = True
                if len(result) >= target_count:
                    break
        if not progressed:
            break

    return result


@router.post("/valuate")
async def valuate(req: ValuateRequest, db: AsyncSession = Depends(get_db)):
    original_keyword = req.keyword.strip()
    keyword = _canonicalize_keyword(original_keyword)
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")

    # 1. 爬取闲鱼数据（相机关键词使用多查询变体，提升召回）
    crawler = get_crawler()

    compact_keyword = re.sub(r"\s+", "", keyword)
    camera_like = bool(re.search(r"(canon|nikon|sony|佳能|索尼|尼康|富士|松下|奥林巴斯|sx\s*\d|rx\s*\d|a\s*\d)", keyword, flags=re.IGNORECASE))

    # 优先保留用户原始输入作为第一个搜索词，其次是规范化后的英文关键词
    query_variants = [original_keyword]
    if keyword != original_keyword:
        query_variants.append(keyword)
    if compact_keyword and compact_keyword not in query_variants:
        query_variants.append(compact_keyword)

    # 品牌前缀变体
    BRAND_PREFIX_MAP = {
        r"ixus\s*\d": [("canon ixus", "佳能 ixus")],
        r"powershot": [("canon powershot", "佳能")],
        r"ixy\s*\d": [("canon ixy", "佳能 ixy")],
        r"dsc-": [("sony", "索尼")],
        r"cyber.shot": [("sony", "索尼")],
        r"\brx\s*\d": [("sony rx", "索尼 rx")],
        r"coolpix": [("nikon coolpix", "尼康 coolpix")],
        r"finepix": [("fujifilm", "富士")],
        r"lumix": [("panasonic lumix", "松下 lumix")],
        r"\bsx\s*\d+\b": [("powershot sx", "佳能 sx")],
    }
    kw_lower = keyword.lower()
    for pattern, pairs in BRAND_PREFIX_MAP.items():
        if re.search(pattern, kw_lower):
            for en_prefix, cn_prefix in pairs:
                query_variants.append(f"{en_prefix} {compact_keyword}".strip())
                query_variants.append(f"{cn_prefix}{compact_keyword}".strip())
            break

    # SX系列补全：sx500 -> sx500 is / powershot sx500 is
    if camera_like and re.search(r"\bsx\s*\d+\b", keyword, flags=re.IGNORECASE):
        v1 = re.sub(r"\b(sx\s*\d+)\b", r"\1 is", keyword, flags=re.IGNORECASE)
        v2 = re.sub(r"\b(sx\s*\d+)\b", r"PowerShot \1 IS", keyword, flags=re.IGNORECASE)
        query_variants.extend([v1, v2])

    # 型号后缀扩展：j150 -> j150w/j150s；ixus130 -> ixus130hs；e620 -> e620s
    SUFFIX_RULES = [
        (r"(?:^|(?<=[^a-z]))([jzafsJZAFS]\d{3,4})$", ["w", "s", "f", "fd"]),
        (r"ixus\s*(\d{2,4})$", ["hs", " hs"]),
        (r"(?:^|(?<=[^a-z]))(e\d{3,4})$", ["s"]),
        (r"([a-z]{1,3}\d{3,4})$", ["w", "s"]),
    ]

    if camera_like and ('尼康' in keyword or 'nikon' in kw_lower):
        m_nikon = re.search(r'(\d{3,4})$', compact_keyword)
        if m_nikon and not re.search(r'[a-z]\d{3,4}$', compact_keyword, re.IGNORECASE):
            num = m_nikon.group(1)
            query_variants.extend([f'e{num}', f'尼康e{num}', f'nikon e{num}', f'coolpix e{num}'])

    # 富士 J/Z/A/F/S 系列：显式补齐字母后缀（j150 -> j150w）
    if camera_like and ('富士' in keyword or 'fuji' in kw_lower or 'fujifilm' in kw_lower):
        m_fuji = re.search(r'([jzafs]\d{3,4})$', compact_keyword, flags=re.IGNORECASE)
        if m_fuji:
            model = m_fuji.group(1).lower()
            query_variants.extend([
                model + 'w',
                f'finepix {model}w',
                f'富士{model}w',
            ])

    if camera_like:
        for pattern, suffixes in SUFFIX_RULES:
            m = re.search(pattern, compact_keyword, flags=re.IGNORECASE)
            if m:
                for suf in suffixes:
                    if not compact_keyword.lower().endswith(suf.lower().strip()):
                        new_v = compact_keyword + suf
                        query_variants.append(new_v)
                        for cn in ["富士", "尼康", "佳能", "索尼", "松下"]:
                            if cn in keyword:
                                query_variants.append(cn + new_v)
                                break
                break

    # 去重保序，适度放宽变体数量
    query_variants = list(dict.fromkeys([q.strip() for q in query_variants if q and q.strip()]))[:8]

    try:
        merged_items = []
        seen_ids = set()

        target_merged = max(settings.max_items_per_query, 60)
        per_query_max_items = min(settings.max_items_per_query * 2, 120)

        # 最多两轮，多 query 变体聚合
        for round_i in range(2):
            for q in query_variants:
                batch = await crawler.search(
                    q,
                    max_items=per_query_max_items,
                    cookie_override=req.cookies,
                    filter_keyword=keyword,
                )
                new_count = 0
                for it in batch:
                    if it.item_id in seen_ids:
                        continue
                    seen_ids.add(it.item_id)
                    merged_items.append(it)
                    new_count += 1
                logger.info(f"第{round_i+1}轮[{q}]：拿到 {len(batch)} 条，新增 {new_count} 条，累计 {len(merged_items)} 条")

                if len(merged_items) >= target_merged:
                    break

            if len(merged_items) >= target_merged:
                break

            import asyncio as _asyncio
            await _asyncio.sleep(2)

        raw_merged_count = len(merged_items)
        items = merged_items

        # 2. 规则先筛：仅保留目标型号/品牌且非高风险项
        rule_filtered_items = filter_target_items(items, keyword)
        rule_filtered_count = len(rule_filtered_items)

        # 3. LLM再筛：仅保留“同型号整机且功能正常”
        llm_input = [
            {
                "item_id": i.item_id,
                "title": i.title,
                "description": i.description,
                "price": i.price,
            }
            for i in rule_filtered_items
        ]
        llm_filtered = await classify_camera_items_by_llm(keyword, llm_input)
        llm_filtered_count = len(llm_filtered)
        keep_ids = {str(x.get("item_id", "")) for x in llm_filtered}
        if keep_ids:
            items = [i for i in rule_filtered_items if i.item_id in keep_ids]
        else:
            items = []

        # LLM 过严保护：若规则筛很多但 LLM 仅留极少，回退到规则筛里的高相关整机（价格阈值）
        min_keep = 10 if camera_like else 6
        if len(items) < min_keep and len(rule_filtered_items) >= min_keep:
            fallback_items = [i for i in rule_filtered_items if i.price >= (500 if camera_like else 100)]
            if len(fallback_items) > len(items):
                items = fallback_items

        # 分桶补样：相机场景尽量凑到 20~30，按成色/价格段轮询补齐
        if camera_like:
            fallback_pool = [i for i in rule_filtered_items if i.price >= 500]
            target_for_camera = min(24, len(fallback_pool))
            items = _bucket_fill_items(items, fallback_pool, target_count=target_for_camera)

            # 若分桶后仍不足20，再按原顺序补齐到20（不超过24）
            min_floor = min(20, len(fallback_pool))
            if len(items) < min_floor:
                used_ids = {x.item_id for x in items}
                for it in fallback_pool:
                    if it.item_id in used_ids:
                        continue
                    items.append(it)
                    used_ids.add(it.item_id)
                    if len(items) >= min_floor:
                        break
    except Exception as e:
        logger.exception("爬取失败")
        raise HTTPException(status_code=502, detail=f"爬取失败: {repr(e)}")

    if len(items) < 3:
        # 优先给出“被严格筛选掉”的明确原因
        if 'raw_merged_count' in locals() and raw_merged_count >= 3:
            raise HTTPException(
                status_code=422,
                detail={
                    "status_code": 422,
                    "detail": f"关键词“{keyword}”原始候选 {raw_merged_count} 条，但同型号整机且功能正常的有效样本仅 {len(items)} 条。",
                    "debug": {
                        "keyword": keyword,
                        "raw_merged_count": raw_merged_count,
                        "rule_filtered_count": locals().get("rule_filtered_count", 0),
                        "llm_filtered_count": locals().get("llm_filtered_count", 0),
                        "query_variants": query_variants,
                        "crawler": getattr(crawler, '_last_debug_summary', {}) or {},
                    },
                },
            )

        failure = _debug_not_enough_items(crawler, keyword)
        raise HTTPException(
            status_code=failure["status_code"],
            detail=failure,
        )

    # 2. 存入数据库（去重）
    for item in items:
        existing = await db.execute(
            select(CrawledItem).where(CrawledItem.item_id == item.item_id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(CrawledItem(
                item_id=item.item_id,
                title=item.title,
                price=item.price,
                condition=item.condition,
                description=item.description,
                sold=item.sold,
                query_keyword=keyword,
                sold_at=item.sold_at,
                images=json.dumps(item.images, ensure_ascii=False) if item.images else None,
            ))
    await db.commit()

    # 3. 详情页补图已禁用（耗时过长，使用列表页图片）

    # 4. 图片并发分析（融合图片质量分，限流控制：最多3并发+间隔）
    if settings.qwen_api_key:
        img_items = [i for i in items if i.images]  # 所有有图样本
        if img_items:
            sem = asyncio.Semaphore(3)  # 最多3并发，避免429
            async def _analyze_with_sem(item):
                async with sem:
                    await asyncio.sleep(0.5)  # 每次调用前等0.5s
                    return await analyze_item_images(item.item_id, item.title, item.images)
            img_results = await asyncio.gather(*[_analyze_with_sem(i) for i in img_items], return_exceptions=True)
            img_map = {}
            for r in img_results:
                if isinstance(r, dict) and r.get("item_id") and r.get("image_score") is not None:
                    img_map[r["item_id"]] = r
            for item in items:
                r = img_map.get(item.item_id)
                if not r:
                    continue
                img_score = r["image_score"]
                item.quality_score = round(item.quality_score * 0.7 + img_score * 0.3, 2)
                item.quality_flags = item.quality_flags + r.get("image_flags", [])
                if not r.get("is_complete_unit", True):
                    item.quality_score = max(20.0, item.quality_score - 20)
                    item.quality_flags.append("图片判断:疑似非整机")

    # 5. XD卡机型检测（爬取完成后，通过样本标题/描述中"自备xd卡"/"xd卡另购"等关键词判断）
    is_xd_model = False
    xd_card_bonus: dict = {}
    camera_like_for_xd = bool(re.search(
        r"(canon|nikon|sony|佳能|索尼|尼康|富士|松下|奥林巴斯|sx\s*\d|rx\s*\d|a\s*\d)",
        keyword, flags=re.IGNORECASE
    ))
    # camera_only_items：纯相机商品（不含XD卡捆绑），用于算法估价
    # bundle_infos：含卡捆绑商品详情，用于捡漏阶段叠加卡值
    camera_only_items: list = []
    bundle_infos: list = []
    xd_bundle_count = 0

    if camera_like_for_xd:
        is_xd_model = detect_xd_card_model_from_items(items)
        if is_xd_model:
            camera_only_items, bundle_infos = strip_xd_card_prices(items)
            xd_bundle_count = len(bundle_infos)
            for bi in bundle_infos:
                xd_card_bonus[bi.item_id] = (bi.card_size, bi.card_value)
            logger.info(f"XD卡机型确认：{xd_bundle_count} 件含卡捆绑，{len(camera_only_items)} 件纯相机已纳入算法估价")

            # 图片XD卡检测（并发，轻量，只分析前10个含图未识别样本）
            if settings.qwen_api_key and items:
                xd_analysis_items = [i for i in items if i.images and i.item_id not in xd_card_bonus][:10]
                if xd_analysis_items:
                    from app.services.bargain import _get_xd_card_value
                    sem_xd = asyncio.Semaphore(3)
                    async def _check_xd(item):
                        async with sem_xd:
                            await asyncio.sleep(0.2)
                            return await check_xd_card_from_images(item.item_id, item.title, item.images[:2])
                    xd_results = await asyncio.gather(*[_check_xd(i) for i in xd_analysis_items], return_exceptions=True)
                    for r in xd_results:
                        if isinstance(r, dict) and r.get("has_xd_card") and r.get("card_size"):
                            item_id = r["item_id"]
                            card_size = r["card_size"]
                            card_val = _get_xd_card_value(card_size)
                            xd_card_bonus[item_id] = (card_size, card_val)
                            logger.info(f"图片检测到XD卡: {item_id} {card_size} 价值约{card_val}元")

    # 6. 算法估价：XD卡机型只使用纯相机商品（排除含卡捆绑），避免虚高基准价
    # 无论是否XD卡机型，算法估价都用纯相机商品
    items_for_algo = camera_only_items if is_xd_model else items
    prices_for_algo = [i.price for i in items_for_algo]
    quality_scores_for_algo = [i.quality_score for i in items_for_algo]
    pricing = calculate_price(prices_for_algo, quality_scores=quality_scores_for_algo)

    # 7. 多模型并发分析（传入XD卡上下文，让模型降权处理带卡捆绑样本）
    # LLM prompt 始终用所有原始价格，让模型自己判断降权
    llm_results = await multi_model_valuation(
        keyword=keyword,
        base_price=pricing.base_price,
        prices=[i.price for i in items],
        sample_count=pricing.sample_count,
        is_xd_card_model=is_xd_model,
        xd_card_bundle_count=xd_bundle_count,
    )

    # 8. 捡漏检测（含XD卡文字检测，图片检测结果已合并到 xd_card_bonus）
    bargains = detect_bargains(items, pricing.base_price, query_keyword=keyword, xd_card_bonus=xd_card_bonus if xd_card_bonus else None)

    # 9. 存储估价记录
    record = ValuationRecord(
        keyword=keyword,
        base_price=pricing.base_price,
        price_min=pricing.price_min,
        price_max=pricing.price_max,
        sample_count=pricing.sample_count,
        raw_prices=json.dumps(pricing.raw_prices),
        deepseek_result=json.dumps(
            {"suggested_price": llm_results[0].suggested_price,
             "price_min": llm_results[0].price_min,
             "price_max": llm_results[0].price_max,
             "reasoning": llm_results[0].reasoning,
             "confidence": llm_results[0].confidence,
             "error": llm_results[0].error},
            ensure_ascii=False
        ),
        qwen_result=json.dumps(
            {"suggested_price": llm_results[1].suggested_price,
             "price_min": llm_results[1].price_min,
             "price_max": llm_results[1].price_max,
             "reasoning": llm_results[1].reasoning,
             "confidence": llm_results[1].confidence,
             "error": llm_results[1].error,
             "kimi": {
                 "suggested_price": llm_results[2].suggested_price,
                 "price_min": llm_results[2].price_min,
                 "price_max": llm_results[2].price_max,
                 "reasoning": llm_results[2].reasoning,
                 "confidence": llm_results[2].confidence,
                 "error": llm_results[2].error,
             }},
            ensure_ascii=False
        ),
    )
    db.add(record)
    await db.flush()

    for b in bargains:
        existing = await db.execute(
            select(BargainAlert).where(BargainAlert.item_id == b.item_id)
        )
        exists_alert = existing.scalar_one_or_none()
        if exists_alert is None:
            db.add(BargainAlert(
                valuation_record_id=record.id,
                item_id=b.item_id,
                title=b.title,
                price=b.price,
                estimated_price=b.estimated_price,
                profit_estimate=b.profit_estimate,
                url=b.url,
                xd_card_size=b.xd_card_size or "",
                xd_card_value=b.xd_card_value or 0.0,
            ))
        elif exists_alert.valuation_record_id is None:
            exists_alert.valuation_record_id = record.id
    await db.commit()

    return {
        "keyword": keyword,
        "input_keyword": original_keyword,
        "normalized_keyword": keyword,
        "debug_query_variants": query_variants,
        "debug_collected_count": len(items),
        "debug_filter_counts": {
            "raw_merged_count": locals().get("raw_merged_count", len(items)),
            "rule_filtered_count": locals().get("rule_filtered_count", len(items)),
            "llm_filtered_count": locals().get("llm_filtered_count", len(items)),
        },
        "sample_count": len(items),
        "algorithm": {
            "base_price": pricing.base_price,
            "price_min": pricing.price_min,
            "price_max": pricing.price_max,
            "low_outliers": pricing.low_outliers,
            "high_outliers": pricing.high_outliers,
        },
        "quality_summary": {
            "avg_score": round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0,
            "high_quality_count": len([s for s in quality_scores if s >= 75]),
            "mid_quality_count": len([s for s in quality_scores if 50 <= s < 75]),
            "low_quality_count": len([s for s in quality_scores if s < 50]),
        },
        "llm_results": [
            {
                "model": r.model_name,
                "suggested_price": r.suggested_price,
                "price_min": r.price_min,
                "price_max": r.price_max,
                "reasoning": r.reasoning,
                "confidence": r.confidence,
                "error": r.error,
            }
            for r in llm_results
        ],
        "samples": [
            {
                "item_id": i.item_id,
                "title": i.title,
                "price": i.price,
                "url": i.url,
                "sold": i.sold,
                "condition": i.condition,
                "quality_score": i.quality_score,
                "quality_flags": i.quality_flags,
                "images": i.images,
            }
            for i in items
        ],
        "bargains": [
            {
                "item_id": b.item_id,
                "title": b.title,
                "price": b.price,
                "estimated_price": b.estimated_price,
                "profit_estimate": b.profit_estimate,
                "url": b.url,
                "xd_card_size": b.xd_card_size,
                "xd_card_value": b.xd_card_value,
                "has_xd_bonus": bool(b.xd_card_size and b.xd_card_value > 0),
            }
            for b in bargains
        ],
        "xd_card_model": is_xd_model,
        "xd_card_bundle_count": xd_bundle_count,
    }


def _register_stream_task(task_id: str):
    stream_task_controls[task_id] = {
        "stop": asyncio.Event(),
        "finished": False,
    }


def _is_stream_task_stopped(task_id: str) -> bool:
    state = stream_task_controls.get(task_id)
    if not state:
        return False
    stop_event = state.get("stop")
    return bool(isinstance(stop_event, asyncio.Event) and stop_event.is_set())


def _mark_stream_task_finished(task_id: str):
    state = stream_task_controls.get(task_id)
    if state:
        state["finished"] = True


@router.post("/valuate/stop/{task_id}")
async def stop_valuate_task(task_id: str):
    state = stream_task_controls.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="估价任务不存在")
    stop_event = state.get("stop")
    if isinstance(stop_event, asyncio.Event):
        stop_event.set()
    return {"ok": True, "task_id": task_id, "message": "已请求停止任务"}


@router.get("/valuate/tasks")
async def get_valuate_tasks():
    return [
        {
            "task_id": task_id,
            "finished": bool(state.get("finished", False)),
            "stopped": bool(isinstance(state.get("stop"), asyncio.Event) and state["stop"].is_set()),
        }
        for task_id, state in stream_task_controls.items()
    ]


@router.post("/valuate/stream")
async def valuate_stream(req: ValuateRequest, db: AsyncSession = Depends(get_db), task_id: Optional[str] = Query(None)):
    """SSE 流式估价：爬取完立即推送基础数据，大模型结果谁先完成先推送谁。"""
    task_id = (task_id or str(uuid.uuid4())).strip()
    _register_stream_task(task_id)
    original_keyword = req.keyword.strip()
    keyword = _canonicalize_keyword(original_keyword)
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")

    async def event_stream():
        yield f"event: start\ndata: {json.dumps({'task_id': task_id}, ensure_ascii=False)}\n\n"
        if _is_stream_task_stopped(task_id):
            yield f"event: stopped\ndata: {json.dumps({'task_id': task_id, 'detail': '任务已停止'}, ensure_ascii=False)}\n\n"
            _mark_stream_task_finished(task_id)
            return
        # ---- 阶段1：爬取 + 算法估价 ----
        crawler = get_crawler()
        compact_keyword = re.sub(r"\s+", "", keyword)
        camera_like = bool(re.search(
            r"(canon|nikon|sony|佳能|索尼|尼康|富士|松下|奥林巴斯|sx\s*\d|rx\s*\d|a\s*\d)",
            keyword, flags=re.IGNORECASE
        ))
        # 流式场景同样保证第一个 query 就是用户原始输入，避免“索尼T300”被直接规范成 “Sony T300”
        query_variants = [original_keyword]
        if keyword != original_keyword:
            query_variants.append(keyword)
        if compact_keyword and compact_keyword not in query_variants:
            query_variants.append(compact_keyword)

        # 品牌前缀变体映射
        BRAND_PREFIX_MAP = {
            # ixus / powershot / ixy / kiss -> 佳能
            r"ixus\s*\d": [("canon ixus", "canon"), ("佳能 ixus", "佳能")],
            r"powershot": [("canon powershot", "canon"), ("佳能", "佳能")],
            r"ixy\s*\d": [("canon ixy", "canon"), ("佳能 ixy", "佳能")],
            # dsc / cyber.shot / rx -> 索尼
            r"dsc-": [("sony", "sony"), ("索尼", "索尼")],
            r"cyber.shot": [("sony", "sony"), ("索尼", "索尼")],
            r"\brx\s*\d": [("sony rx", "sony"), ("索尼 rx", "索尼")],
            r"\bzx\s*\d": [("sony", "sony")],
            # coolpix -> 尼康
            r"coolpix": [("nikon coolpix", "nikon"), ("尼康 coolpix", "尼康")],
            r"\bp\s*\d{3,4}\b": [("nikon", "nikon"), ("尼康", "尼康")],
            # finepix / x100 -> 富士
            r"finepix": [("fujifilm", "fuji"), ("富士", "富士")],
            r"x100": [("fujifilm x100", "fuji x100"), ("富士 x100", "富士")],
            r"\bxt\s*\d": [("fujifilm", "fuji"), ("富士", "富士")],
            # lumix -> 松下
            r"lumix": [("panasonic lumix", "panasonic"), ("松下 lumix", "松下")],
            # sx系列补全
            r"\bsx\s*\d+\b": [("powershot sx", "canon sx"), ("佳能 sx", "佳能")],
        }
        kw_lower = keyword.lower()
        for pattern, prefixes in BRAND_PREFIX_MAP.items():
            if re.search(pattern, kw_lower):
                for prefix_en, prefix_cn in prefixes:
                    # 如果关键词里没有品牌词，加前缀变体
                    if not kw_lower.startswith(prefix_en.split()[0]) and prefix_en.split()[0] not in kw_lower:
                        query_variants.append(f"{prefix_en} {compact_keyword}".strip())
                    if prefix_cn and prefix_cn not in kw_lower:
                        query_variants.append(f"{prefix_cn}{compact_keyword}".strip())
                break  # 只匹配第一个规则

        # SX系列特殊补全：sx500 -> sx500 is / powershot sx500 is
        if camera_like and re.search(r"\bsx\s*\d+\b", keyword, flags=re.IGNORECASE):
            v1 = re.sub(r"\b(sx\s*\d+)\b", r"\1 is", keyword, flags=re.IGNORECASE)
            v2 = re.sub(r"\b(sx\s*\d+)\b", r"PowerShot \1 IS", keyword, flags=re.IGNORECASE)
            query_variants.extend([v1, v2])
        # 型号后缀模糊扩展：用户常省略后缀字母，自动补全常见变体
        # 例：j150 -> j150w/j150s；ixus130 -> ixus130hs；e620 -> e620s
        # 型号后缀模糊扩展：用户常省略后缀字母，自动补全常见变体
        # 例：j150 -> j150w/j150s；ixus130 -> ixus130hs；尼庶620 -> 尼庶e620
        SUFFIX_RULES = [
            # 富士J/Z/A/F/S系列：数字结尾补 w/s/f/fd
            (r"(?:^|(?<=[^a-z]))([jzafsJZAFS]\d{3,4})$", ["w", "s", "f", "fd"]),
            # 佳能IXUS补HS
            (r"ixus\s*(\d{2,4})$", ["hs", " hs"]),
            # 尼庶E系列：e620补e620s
            (r"(?:^|(?<=[^a-z]))(e\d{3,4})$", ["s"]),
            # 通用：纯数字结尾型号补w/s
            (r"([a-z]{1,3}\d{3,4})$", ["w", "s"]),
        ]
        # 尼康纯数字变体：用户输入「尼康620」补全为「尼康e620」
        if camera_like and ('尼康' in keyword or 'nikon' in kw_lower):
            m_nikon = re.search(r'(\d{3,4})$', compact_keyword)
            if m_nikon and not re.search(r'[a-z]\d{3,4}$', compact_keyword, re.IGNORECASE):
                num = m_nikon.group(1)
                query_variants.append('e' + num)
                query_variants.append('尼康e' + num)
                query_variants.append('nikon e' + num)
                query_variants.append('coolpix e' + num)

        # 富士 J/Z/A/F/S 系列：显式补齐字母后缀（j150 -> j150w）
        if camera_like and ('富士' in keyword or 'fuji' in kw_lower or 'fujifilm' in kw_lower):
            m_fuji = re.search(r'([jzafs]\d{3,4})$', compact_keyword, flags=re.IGNORECASE)
            if m_fuji:
                model = m_fuji.group(1).lower()
                query_variants.append(model + 'w')
                query_variants.append(f'finepix {model}w')
                query_variants.append(f'富士{model}w')
        if camera_like:
            for pattern, suffixes in SUFFIX_RULES:
                m = re.search(pattern, compact_keyword, flags=re.IGNORECASE)
                if m:
                    for suf in suffixes:
                        if not compact_keyword.lower().endswith(suf.lower().strip()):
                            new_v = compact_keyword + suf
                            query_variants.append(new_v)
                            for cn in ["富士", "尼康", "佳能", "索尼", "松下"]:
                                if cn in keyword:
                                    query_variants.append(cn + new_v)
                                    break
                    break

        # 去重保序，放宽变体数量，提升召回
        query_variants = list(dict.fromkeys([q.strip() for q in query_variants if q and q.strip()]))[:8]

        merged_items = []
        seen_ids = set()
        target_merged = max(settings.max_items_per_query, 60)
        per_query_max_items = min(settings.max_items_per_query * 2, 120)

        try:
            for round_i in range(2):
                if _is_stream_task_stopped(task_id):
                    yield f"event: stopped\ndata: {json.dumps({'task_id': task_id, 'detail': '任务已停止'}, ensure_ascii=False)}\n\n"
                    _mark_stream_task_finished(task_id)
                    return
                for q in query_variants:
                    if _is_stream_task_stopped(task_id):
                        yield f"event: stopped\ndata: {json.dumps({'task_id': task_id, 'detail': '任务已停止'}, ensure_ascii=False)}\n\n"
                        _mark_stream_task_finished(task_id)
                        return
                    yield f"event: step\ndata: {json.dumps({'text': f'第{round_i+1}轮[{q}]：正在爬取...', 'status': 'pending'}, ensure_ascii=False)}\n\n"
                    batch = await crawler.search(
                        q, max_items=per_query_max_items,
                        cookie_override=req.cookies, filter_keyword=keyword,
                    )
                    for it in batch:
                        if it.item_id not in seen_ids:
                            seen_ids.add(it.item_id)
                            merged_items.append(it)
                    yield f"event: step\ndata: {json.dumps({'text': f'第{round_i+1}轮[{q}]：已收集 {len(merged_items)} 条原始样本', 'status': 'done'}, ensure_ascii=False)}\n\n"
                    if len(merged_items) >= target_merged:
                        break
                if len(merged_items) >= target_merged:
                    break
                await asyncio.sleep(2)

            yield f"event: step\ndata: {json.dumps({'text': f'规则筛选：{len(merged_items)} -> 规则筛中...', 'status': 'pending'}, ensure_ascii=False)}\n\n"
            rule_filtered, rule_filtered_out = filter_target_items_with_reasons(merged_items, keyword)
            yield f"event: step\ndata: {json.dumps({'text': f'规则筛选完成：保留 {len(rule_filtered)} 条', 'status': 'done', 'filtered_out': rule_filtered_out}, ensure_ascii=False)}\n\n"
            yield f"event: step\ndata: {json.dumps({'text': f'LLM精筛中（{len(rule_filtered)} 条）...', 'status': 'pending'}, ensure_ascii=False)}\n\n"
            llm_input = [{"item_id": i.item_id, "title": i.title, "description": i.description, "price": i.price} for i in rule_filtered]
            llm_filtered = await classify_camera_items_by_llm(keyword, llm_input)
            keep_ids = {str(x.get("item_id", "")) for x in llm_filtered}
            llm_kept = [i for i in rule_filtered if i.item_id in keep_ids] if keep_ids else []
            llm_filtered_out = [
                {"title": i.title, "price": i.price, "reason": "LLM判断不符"}
                for i in rule_filtered if i.item_id not in keep_ids
            ]
            items = llm_kept
            yield f"event: step\ndata: {json.dumps({'text': f'LLM精筛完成：保留 {len(items)} 条有效样本', 'status': 'done', 'filtered_out': llm_filtered_out}, ensure_ascii=False)}\n\n"

            min_keep = 10 if camera_like else 6
            if len(items) < min_keep and len(rule_filtered) >= min_keep:
                fb = [i for i in rule_filtered if i.price >= (300 if camera_like else 100)]
                if len(fb) > len(items):
                    items = fb

            if camera_like:
                pool = [i for i in rule_filtered if i.price >= 500]
                items = _bucket_fill_items(items, pool, target_count=min(24, len(pool)))
                floor = min(20, len(pool))
                if len(items) < floor:
                    used = {x.item_id for x in items}
                    for it in pool:
                        if it.item_id not in used:
                            items.append(it)
                            used.add(it.item_id)
                            if len(items) >= floor:
                                break
                yield f"event: step\ndata: {json.dumps({'text': f'样本补充完成：最终样本 {len(items)} 条（含规则筛通过的补充项）', 'status': 'done'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            _mark_stream_task_finished(task_id)
            yield f"event: error\ndata: {json.dumps({'detail': repr(e)}, ensure_ascii=False)}\n\n"
            return

        if len(items) < 3:
            _mark_stream_task_finished(task_id)
            yield f"event: error\ndata: {json.dumps({'detail': '有效样本不足，请换关键词重试'}, ensure_ascii=False)}\n\n"
            return

        # XD卡检测：爬取完成后，通过样本标题/描述判断机型
        is_xd_model = False
        xd_card_bonus: dict = {}
        # camera_only_items：纯相机商品（不含XD卡捆绑），用于算法估价
        # bundle_infos：含卡捆绑商品详情，用于捡漏阶段叠加卡值
        camera_only_items: list = []
        bundle_infos: list = []
        xd_bundle_count = 0

        if camera_like:
            is_xd_model = detect_xd_card_model_from_items(items)
            if is_xd_model:
                from app.services.bargain import strip_xd_card_prices, _get_xd_card_value
                camera_only_items, bundle_infos = strip_xd_card_prices(items)
                xd_bundle_count = len(bundle_infos)
                for bi in bundle_infos:
                    xd_card_bonus[bi.item_id] = (bi.card_size, bi.card_value)

                # XD卡确认提示推送给前端（替代原来的"爬前预判提示"）
                card_price_list = "\n".join([f"  {k}：约¥{v}" for k, v in {"16mb":"50","32mb":"60","64mb":"70","128mb":"108","256mb":"120","512mb":"134","1g":"148","2g":"162"}.items()])
                xd_confirm_text = (
                    f"📌【XD卡提示】您查询的相机为XD卡老机型！\n"
                    f"  ① 相机+内存卡总利润超过¥120即为捡漏\n"
                    f"  ② 带卡商品已排除在估价样本外，只用纯相机价格计算基准价\n"
                    f"  ③ 识别到 {xd_bundle_count} 件捆绑XD卡商品，已做降权处理\n"
                    f"参考XD卡价格：\n{card_price_list}"
                )
                yield f"event: xd_confirmed\ndata: {json.dumps({'text': xd_confirm_text, 'bundle_count': xd_bundle_count}, ensure_ascii=False)}\n\n"

                # 图片XD卡检测（并发，轻量，限制前10个节省开销）
                if settings.qwen_api_key:
                    xd_analysis_items = [i for i in items if i.images and i.item_id not in xd_card_bonus][:10]
                    if xd_analysis_items:
                        sem_xd = asyncio.Semaphore(3)
                        async def _check_xd(item):
                            async with sem_xd:
                                await asyncio.sleep(0.2)
                                return await check_xd_card_from_images(item.item_id, item.title, item.images[:2])
                        xd_results = await asyncio.gather(*[_check_xd(i) for i in xd_analysis_items], return_exceptions=True)
                        for r in xd_results:
                            if isinstance(r, dict) and r.get("has_xd_card") and r.get("card_size"):
                                item_id = r["item_id"]
                                card_size = r["card_size"]
                                card_val = _get_xd_card_value(card_size)
                                xd_card_bonus[item_id] = (card_size, card_val)
                                logger.info(f"图片检测到XD卡: {item_id} {card_size} 价值约{card_val}元")

        # 算法估价：XD卡机型只用纯相机商品，排除含卡捆绑样本
        items_for_algo = camera_only_items if is_xd_model else items
        prices_for_algo = [i.price for i in items_for_algo]
        quality_scores = [i.quality_score for i in items_for_algo]
        pricing = calculate_price(prices_for_algo, quality_scores=quality_scores)

        # 详情页补图已禁用（耗时过长，使用列表页图片）

        # 图片并发分析（限流控制：最多3并发+间隔）
        if settings.qwen_api_key:
            img_items = [i for i in items if i.images]
            yield f"event: step\ndata: {json.dumps({'text': f'图片核查中（{len(img_items)} 个有图样本）...', 'status': 'pending'}, ensure_ascii=False)}\n\n"
            if img_items:
                # 对成色可疑的样本做成色分析（质量分<70或标题含成色差词）
                POOR_COND_WORDS = ['磨损', '划痕', '刮花', '碰撞', '摔', '瑕疵', '故障', '维修', '零件机']
                def _needs_condition_check(item):
                    text = (item.title + " " + (item.description or "")).lower()
                    return item.quality_score < 70 or any(w in text for w in POOR_COND_WORDS)
                cond_items = [i for i in items if i.images and _needs_condition_check(i)]
                yield f"event: step\ndata: {json.dumps({'text': f'成色分析中（{len(cond_items)} 个可疑样本）...', 'status': 'pending'}, ensure_ascii=False)}\n\n"
                if cond_items:
                    sem_v = asyncio.Semaphore(3)
                    async def _analyze_with_sem_sse(item):
                        async with sem_v:
                            await asyncio.sleep(0.3)
                            return await analyze_item_images(item.item_id, item.title, item.images, price=item.price, base_price=pricing.base_price)
                    img_results = await asyncio.gather(*[_analyze_with_sem_sse(i) for i in cond_items], return_exceptions=True)
                    img_map = {}
                    for r in img_results:
                        if isinstance(r, dict) and r.get("item_id") and r.get("image_score") is not None:
                            img_map[r["item_id"]] = r
                    for item in items:
                        r = img_map.get(item.item_id)
                        if not r:
                            continue
                        item.quality_score = round(item.quality_score * 0.6 + r["image_score"] * 0.4, 2)
                        item.quality_flags = item.quality_flags + r.get("image_flags", [])
                        if not r.get("is_complete_unit", True):
                            item.quality_score = max(20.0, item.quality_score - 20)
                            item.quality_flags.append("图片判断:疑似非整机")
                        # 成色差+价格偏高：降权（质量分额外扣15）
                        if r.get("price_penalty"):
                            item.quality_score = max(10.0, item.quality_score - 15)
                    yield f"event: step\ndata: {json.dumps({'text': f'成色分析完成', 'status': 'done', 'filtered_out': [{'title': it.title, 'price': it.price, 'reason': '、'.join(img_map[it.item_id].get("image_flags", ["成色分析"])) if img_map.get(it.item_id) else '成色分析'} for it in cond_items if img_map.get(it.item_id)]}, ensure_ascii=False)}\n\n"

        # 捡漏检测（xd_card_bonus 已通过文字+图片检测填充完毕）
        bargains = detect_bargains(items, pricing.base_price, query_keyword=keyword, xd_card_bonus=xd_card_bonus if xd_card_bonus else None)

        base_payload = {
            "type": "base",
            "keyword": keyword,
            "sample_count": len(items),
            "xd_card_model": is_xd_model,
            "xd_card_bundle_count": xd_bundle_count,
            "algorithm": {
                "base_price": pricing.base_price,
                "price_min": pricing.price_min,
                "price_max": pricing.price_max,
                "low_outliers": pricing.low_outliers,
                "high_outliers": pricing.high_outliers,
            },
            "quality_summary": {
                "avg_score": round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0,
                "high_quality_count": len([s for s in quality_scores if s >= 75]),
                "mid_quality_count": len([s for s in quality_scores if 50 <= s < 75]),
                "low_quality_count": len([s for s in quality_scores if s < 50]),
            },
            "samples": [{"item_id": i.item_id, "title": i.title, "price": i.price, "url": i.url,
                         "sold": i.sold, "condition": i.condition, "quality_score": i.quality_score,
                         "quality_flags": i.quality_flags, "images": i.images} for i in items],
            "bargains": [{"item_id": b.item_id, "title": b.title, "price": b.price,
                          "estimated_price": b.estimated_price, "profit_estimate": b.profit_estimate,
                          "url": b.url,
                          "xd_card_size": b.xd_card_size, "xd_card_value": b.xd_card_value,
                          "has_xd_bonus": bool(b.xd_card_size and b.xd_card_value > 0)} for b in bargains],
        }
        yield f"event: base\ndata: {json.dumps(base_payload, ensure_ascii=False)}\n\n"

        # ---- 阶段2：三模型竞速，谁先完成先推送 ----
        # LLM prompt 始终用原始价格，让模型自己判断降权
        prompt = _build_prompt_for_stream(
            keyword, pricing.base_price, [i.price for i in items], pricing.sample_count,
            is_xd_card_model=is_xd_model,
            xd_card_bundle_count=xd_bundle_count,
        )

        async def run_model(call_fn, model_name):
            data = await call_fn(prompt)
            v = _to_valuation_for_stream(data, model_name)
            return v

        tasks = {
            asyncio.create_task(run_model(call_deepseek_fn, settings.deepseek_model)): settings.deepseek_model,
            asyncio.create_task(run_model(call_qwen_fn, settings.qwen_model)): settings.qwen_model,
            asyncio.create_task(run_model(call_kimi_fn, settings.doubao_model)): settings.doubao_model,
        }
        pending = set(tasks.keys())
        llm_results_collected = []
        while pending:
            if _is_stream_task_stopped(task_id):
                for p in pending:
                    p.cancel()
                yield f"event: stopped\ndata: {json.dumps({'task_id': task_id, 'detail': '任务已停止'}, ensure_ascii=False)}\n\n"
                _mark_stream_task_finished(task_id)
                return
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                v = t.result()
                llm_results_collected.append(v)
                payload = {
                    "type": "llm",
                    "model": v["model"],
                    "suggested_price": v["suggested_price"],
                    "price_min": v["price_min"],
                    "price_max": v["price_max"],
                    "reasoning": v["reasoning"],
                    "confidence": v["confidence"],
                    "error": v["error"],
                }
                yield f"event: llm\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

        _mark_stream_task_finished(task_id)
        yield "event: done\ndata: {}\n\n"

        # 存储记录
        try:
            for item in items:
                existing = await db.execute(select(CrawledItem).where(CrawledItem.item_id == item.item_id))
                if existing.scalar_one_or_none() is None:
                    db.add(CrawledItem(item_id=item.item_id, title=item.title, price=item.price,
                                       condition=item.condition, description=item.description,
                                       sold=item.sold, query_keyword=keyword, sold_at=item.sold_at,
                                       images=json.dumps(item.images, ensure_ascii=False) if item.images else None))
            r0 = next((x for x in llm_results_collected if x["model"] == settings.deepseek_model), {})
            r1 = next((x for x in llm_results_collected if x["model"] == settings.qwen_model), {})
            r2 = next((x for x in llm_results_collected if x["model"] == settings.doubao_model), {})
            record = ValuationRecord(
                keyword=keyword,
                base_price=pricing.base_price, price_min=pricing.price_min, price_max=pricing.price_max,
                sample_count=pricing.sample_count, raw_prices=json.dumps(pricing.raw_prices),
                deepseek_result=json.dumps(r0, ensure_ascii=False),
                qwen_result=json.dumps({**r1, "doubao": r2}, ensure_ascii=False),
            )
            db.add(record)
            await db.flush()
            for b in bargains:
                ex = await db.execute(select(BargainAlert).where(BargainAlert.item_id == b.item_id))
                ex_alert = ex.scalar_one_or_none()
                if ex_alert is None:
                    db.add(BargainAlert(
                        valuation_record_id=record.id,
                        item_id=b.item_id,
                        title=b.title,
                        price=b.price,
                        estimated_price=b.estimated_price,
                        profit_estimate=b.profit_estimate,
                        url=b.url,
                        xd_card_size=b.xd_card_size or "",
                        xd_card_value=b.xd_card_value or 0.0,
                    ))
                elif ex_alert.valuation_record_id is None:
                    ex_alert.valuation_record_id = record.id
            await db.commit()
        except Exception as e:
            logger.warning(f"SSE 存储记录失败: {e}")

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/history")
async def get_history(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ValuationRecord)
        .order_by(ValuationRecord.created_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "keyword": r.keyword,
            "base_price": r.base_price,
            "price_min": r.price_min,
            "price_max": r.price_max,
            "sample_count": r.sample_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]




@router.get("/history/{record_id}")
async def get_history_detail(
    record_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ValuationRecord).where(ValuationRecord.id == record_id))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    deepseek = {}
    qwen_data = {}
    doubao = {}
    try:
        deepseek = json.loads(r.deepseek_result) if r.deepseek_result else {}
    except Exception:
        pass
    try:
        qwen_raw = json.loads(r.qwen_result) if r.qwen_result else {}
        doubao = qwen_raw.pop("doubao", {})
        qwen_data = qwen_raw
    except Exception:
        pass
    raw_prices = []
    try:
        raw_prices = json.loads(r.raw_prices) if r.raw_prices else []
    except Exception:
        pass
    bargain_result = await db.execute(
        select(BargainAlert)
        .where(BargainAlert.valuation_record_id == r.id)
        .order_by(BargainAlert.created_at.asc())
        .limit(20)
    )
    bargains = bargain_result.scalars().all()
    return {
        "id": r.id,
        "keyword": r.keyword,
        "base_price": r.base_price,
        "price_min": r.price_min,
        "price_max": r.price_max,
        "sample_count": r.sample_count,
        "raw_prices": raw_prices,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "llm_results": [x for x in [deepseek, qwen_data, doubao] if x],
        "bargains": [
            {
                "item_id": b.item_id,
                "title": b.title,
                "price": b.price,
                "estimated_price": b.estimated_price,
                "profit_estimate": b.profit_estimate,
                "url": b.url,
            } for b in bargains
        ],
    }

@router.get("/bargains")
async def get_bargains(
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db)
):
    query = select(BargainAlert).order_by(BargainAlert.created_at.desc()).limit(50)
    if unread_only:
        query = query.where(BargainAlert.is_read == False)
    result = await db.execute(query)
    alerts = result.scalars().all()
    return [
        {
            "id": a.id,
            "item_id": a.item_id,
            "title": a.title,
            "price": a.price,
            "estimated_price": a.estimated_price,
            "profit_estimate": a.profit_estimate,
            "url": a.url,
            "is_read": a.is_read,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "xd_card_size": a.xd_card_size or "",
            "xd_card_value": a.xd_card_value or 0.0,
        }
        for a in alerts
    ]


@router.patch("/bargains/{alert_id}/read")
async def mark_read(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BargainAlert).where(BargainAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="记录不存在")
    alert.is_read = True
    await db.commit()
    return {"ok": True}


@router.get('/login-state')
async def get_login_state():
    logged_in = STORAGE_STATE_FILE.exists() and STORAGE_STATE_FILE.stat().st_size > 0
    return {
        'logged_in': logged_in,
        'storage_state_file': str(STORAGE_STATE_FILE),
    }


@router.post('/open-xianyu-login')
async def open_xianyu_login():
    ok = webbrowser.open('https://www.goofish.com/', new=2)
    if not ok:
        raise HTTPException(status_code=500, detail='打开闲鱼登录页失败，请手动访问 https://www.goofish.com/')
    return {'ok': True, 'message': '已尝试打开闲鱼登录页，请完成登录后返回。'}


class SyncCookieRequest(BaseModel):
    cookie: str


@router.post('/sync-cookie')
async def sync_cookie(req: SyncCookieRequest):
    crawler = get_crawler()
    crawler.save_cookie(req.cookie)
    return {'ok': True, 'message': 'Cookie已更新'}
