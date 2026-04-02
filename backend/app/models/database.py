from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # 轻量迁移：为旧库补充 bargain_alerts.valuation_record_id
        # SQLite 不支持 IF NOT EXISTS 的 ADD COLUMN，这里先探测再执行。
        rows = await conn.execute(text("PRAGMA table_info('bargain_alerts')"))
        columns = {row[1] for row in rows.fetchall()} if rows is not None else set()
        if "valuation_record_id" not in columns:
            await conn.execute(text("ALTER TABLE bargain_alerts ADD COLUMN valuation_record_id INTEGER"))
