import asyncio
import json
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.valuate import _persist_valuation_snapshot, _update_valuation_llm_results
from app.models.cache import CCDPriceCache
from app.models.database import Base
from app.models.item import BargainAlert, CrawledItem, ValuationRecord, ValuationSample
from app.models.price_history import PriceHistory


def _item(item_id: str, price: float):
    return SimpleNamespace(
        item_id=item_id,
        title=f"Canon IXUS sample {item_id}",
        price=price,
        condition="成色未标注",
        description="功能正常",
        sold=False,
        sold_at=None,
        url=f"https://www.goofish.com/item?id={item_id}",
        images=["https://img.example.test/a.jpg"],
        quality_score=70,
        quality_flags=["rule"],
    )


def test_user_valuation_snapshot_persists_samples_cache_and_history(tmp_path):
    async def run():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as session:
            pricing = SimpleNamespace(
                base_price=350,
                price_min=300,
                price_max=420,
                sample_count=2,
                raw_prices=[320, 360],
            )
            bargain = SimpleNamespace(
                item_id="1001",
                title="Canon IXUS sample 1001",
                price=320,
                estimated_price=350,
                profit_estimate=30,
                url="https://www.goofish.com/item?id=1001",
                xd_card_size="",
                xd_card_value=0,
            )

            record = await _persist_valuation_snapshot(
                session,
                keyword="Canon IXUS 130",
                original_keyword="佳能ixus130",
                pricing=pricing,
                items=[_item("1001", 320), _item("1002", 360)],
                bargains=[bargain],
                llm_results=[],
                is_xd_model=False,
                xd_bundle_count=0,
            )

            assert record.id is not None
            assert await session.scalar(select(func.count()).select_from(ValuationRecord)) == 1
            assert await session.scalar(select(func.count()).select_from(ValuationSample)) == 2
            assert await session.scalar(select(func.count()).select_from(CrawledItem)) == 2
            assert await session.scalar(select(func.count()).select_from(BargainAlert)) == 1
            assert await session.scalar(select(func.count()).select_from(CCDPriceCache)) == 1
            assert await session.scalar(select(func.count()).select_from(PriceHistory)) == 1

            samples = (await session.execute(select(ValuationSample).order_by(ValuationSample.item_id))).scalars().all()
            assert [s.item_id for s in samples] == ["1001", "1002"]
            assert json.loads(samples[0].images) == ["https://img.example.test/a.jpg"]

            cache = (await session.execute(select(CCDPriceCache))).scalar_one()
            assert cache.keyword == "Canon IXUS 130"
            assert cache.display_name == "佳能ixus130"
            assert cache.base_price == 350
            assert cache.sample_count == 2

            await _update_valuation_llm_results(
                session,
                record,
                [{"model": "deepseek-chat", "suggested_price": 355, "confidence": "high"}],
            )
            refreshed = await session.get(ValuationRecord, record.id)
            assert json.loads(refreshed.deepseek_result)["suggested_price"] == 355

        await engine.dispose()

    asyncio.run(run())
