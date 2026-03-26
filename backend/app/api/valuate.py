import json
import logging
import re
import webbrowser
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from app.models.database import get_db
from app.models.item import CrawledItem, ValuationRecord, BargainAlert
from app.crawler.xianyu import get_crawler
from app.services.pricing import calculate_price
from app.services.llm import multi_model_valuation, classify_camera_items_by_llm
from app.services.bargain import detect_bargains, filter_target_items
from app.config import settings

router = APIRouter(prefix="/api", tags=["估价"])
logger = logging.getLogger(__name__)

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

    query_variants = [keyword]
    if compact_keyword and compact_keyword != keyword:
        query_variants.append(compact_keyword)

    # 型号词补全：例如 sx500 -> sx500 is / powershot sx500 is
    if camera_like and re.search(r"\bsx\s*\d+\b", keyword, flags=re.IGNORECASE):
        v1 = re.sub(r"\b(sx\s*\d+)\b", r"\1 is", keyword, flags=re.IGNORECASE)
        v2 = re.sub(r"\b(sx\s*\d+)\b", r"PowerShot \1 IS", keyword, flags=re.IGNORECASE)
        query_variants.extend([v1, v2])

    # 去重保序
    query_variants = list(dict.fromkeys([q.strip() for q in query_variants if q and q.strip()]))

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
            fallback_items = [i for i in rule_filtered_items if i.price >= (300 if camera_like else 100)]
            if len(fallback_items) > len(items):
                items = fallback_items
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
            ))
    await db.commit()

    # 3. 算法估价（功能优先质量分 + 鲁棒估价）
    prices = [i.price for i in items]
    quality_scores = [i.quality_score for i in items]
    pricing = calculate_price(prices, quality_scores=quality_scores)

    # 4. 多模型并发分析
    llm_results = await multi_model_valuation(
        keyword=keyword,
        base_price=pricing.base_price,
        prices=pricing.raw_prices,
        sample_count=pricing.sample_count,
    )

    # 5. 捡漏检测
    bargains = detect_bargains(items, pricing.base_price, query_keyword=keyword)

    # 6. 存储估价记录
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

    for b in bargains:
        existing = await db.execute(
            select(BargainAlert).where(BargainAlert.item_id == b.item_id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(BargainAlert(
                item_id=b.item_id,
                title=b.title,
                price=b.price,
                estimated_price=b.estimated_price,
                profit_estimate=b.profit_estimate,
                url=b.url,
            ))
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
            }
            for b in bargains
        ],
    }


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
