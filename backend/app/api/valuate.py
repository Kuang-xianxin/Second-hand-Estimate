import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.models.database import get_db
from app.models.item import CrawledItem, ValuationRecord, BargainAlert
from app.crawler.xianyu import get_crawler
from app.services.pricing import calculate_price
from app.services.llm import multi_model_valuation
from app.services.bargain import detect_bargains
from app.config import settings

router = APIRouter(prefix="/api", tags=["估价"])
logger = logging.getLogger(__name__)


class ValuateRequest(BaseModel):
    keyword: str
    cookies: Optional[str] = None


def _debug_not_enough_items(crawler, keyword: str):
    summary = getattr(crawler, '_last_debug_summary', {}) or {}
    return {
        "detail": "有效数据不足，请换个关键词或稍后再试",
        "debug": {
            "keyword": keyword,
            **summary,
        },
    }


@router.post("/valuate")
async def valuate(req: ValuateRequest, db: AsyncSession = Depends(get_db)):
    keyword = req.keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")

    # 1. 爬取闲鱼数据
    crawler = get_crawler()
    try:
        items = await crawler.search(keyword, max_items=settings.max_items_per_query, cookie_override=req.cookies)
    except Exception as e:
        logger.exception("爬取失败")
        raise HTTPException(status_code=502, detail=f"爬取失败: {repr(e)}")

    if len(items) < 3:
        raise HTTPException(
            status_code=404,
            detail=_debug_not_enough_items(crawler, keyword),
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

    # 3. 算法估价
    prices = [i.price for i in items]
    pricing = calculate_price(prices)

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
             "secondary": {
                 "suggested_price": llm_results[2].suggested_price,
                 "price_min": llm_results[2].price_min,
                 "price_max": llm_results[2].price_max,
                 "reasoning": llm_results[2].reasoning,
                 "confidence": llm_results[2].confidence,
                 "error": llm_results[2].error,
             }},
            ensure_ascii=False
        ),
        openai_result=json.dumps(
            {"suggested_price": llm_results[3].suggested_price,
             "price_min": llm_results[3].price_min,
             "price_max": llm_results[3].price_max,
             "reasoning": llm_results[3].reasoning,
             "confidence": llm_results[3].confidence,
             "error": llm_results[3].error},
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
        "sample_count": pricing.sample_count,
        "algorithm": {
            "base_price": pricing.base_price,
            "price_min": pricing.price_min,
            "price_max": pricing.price_max,
            "low_outliers": pricing.low_outliers,
            "high_outliers": pricing.high_outliers,
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


class SyncCookieRequest(BaseModel):
    cookie: str


@router.post('/sync-cookie')
async def sync_cookie(req: SyncCookieRequest):
    crawler = get_crawler()
    crawler.save_cookie(req.cookie)
    return {'ok': True, 'message': 'Cookie已更新'}
