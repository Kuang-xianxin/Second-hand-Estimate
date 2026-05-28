import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import settings

logger = logging.getLogger(__name__)

database_url = settings.database_url
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

_is_postgres = database_url.startswith("postgresql")

engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
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
    # Import models that may not be pulled in by API modules before metadata creation.
    from app.models import auth as _auth_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        if not _is_postgres:
            # SQLite migration: add missing columns (ignore errors if already exist)
            for table, cols, create_sql in [
                ("bargain_alerts", [
                    ("keyword", "VARCHAR(256)"),
                    ("current_price", "DOUBLE PRECISION"),
                    ("base_price", "DOUBLE PRECISION"),
                    ("discount_rate", "DOUBLE PRECISION"),
                    ("condition", "VARCHAR(64)"),
                    ("quality_score", "DOUBLE PRECISION"),
                    ("is_xd_card", "BOOLEAN DEFAULT 0"),
                    ("image_url", "VARCHAR(1024)"),
                    ("updated_at", "TIMESTAMP"),
                ], None),
                ("crawled_items", [
                    ("keyword", "VARCHAR(256)"),
                    ("query_keyword", "VARCHAR(256)"),
                    ("url", "VARCHAR(1024)"),
                    ("quality_score", "DOUBLE PRECISION DEFAULT 50.0"),
                    ("quality_flags", "TEXT"),
                    ("is_valid", "BOOLEAN DEFAULT 1"),
                ], None),
                ("valuation_records", [
                    ("openai_result", "TEXT"),
                ], None),
                ("crawl_status", [], """CREATE TABLE IF NOT EXISTS crawl_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id VARCHAR(64) UNIQUE NOT NULL,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    total_keywords INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    total_items INTEGER DEFAULT 0,
                    bargains_found INTEGER DEFAULT 0,
                    status VARCHAR(32) DEFAULT 'running',
                    error_message TEXT
                )"""),
                ("crawl_keyword_status", [], """CREATE TABLE IF NOT EXISTS crawl_keyword_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id VARCHAR(64) NOT NULL,
                    keyword VARCHAR(256) NOT NULL,
                    status VARCHAR(32) DEFAULT 'pending',
                    item_count INTEGER DEFAULT 0,
                    login_required BOOLEAN DEFAULT 0,
                    risk_detected BOOLEAN DEFAULT 0,
                    error_message TEXT,
                    debug_summary TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP,
                    UNIQUE(batch_id, keyword)
                )"""),
            ]:
                existing_tables = await _sqlite_get_tables(conn)
                if table not in existing_tables:
                    # Create missing table
                    if create_sql:
                        try:
                            await conn.execute(text(create_sql))
                            logger.info(f"SQLite: created table {table}")
                        except Exception as e:
                            logger.warning(f"SQLite: failed to create table {table}: {e}")
                    continue
                existing = await _sqlite_get_columns(conn, table)
                for col_name, col_def in cols:
                    if col_name not in existing:
                        try:
                            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))
                            logger.info(f"SQLite: added column {table}.{col_name}")
                        except Exception as e:
                            logger.warning(f"SQLite: failed to add {table}.{col_name}: {e}")
            return

        # PostgreSQL：补充 crawled_items 新增字段（幂等，IF NOT EXISTS 等效写法）
        existing_cols = await _pg_get_columns(conn, "crawled_items")
        new_cols = [
            ("quality_score", "DOUBLE PRECISION DEFAULT 50.0"),
            ("quality_flags", "TEXT"),
            ("is_valid", "BOOLEAN DEFAULT TRUE"),
            ("url", "VARCHAR(1024)"),
            ("query_keyword", "VARCHAR(256)"),
        ]
        for col_name, col_def in new_cols:
            if col_name not in existing_cols:
                await conn.execute(text(f"ALTER TABLE crawled_items ADD COLUMN IF NOT EXISTS {col_name} {col_def}"))

        # valuation_records 新增字段
        existing_vr_cols = await _pg_get_columns(conn, "valuation_records")
        vr_new_cols = [
            ("openai_result", "TEXT"),
        ]
        for col_name, col_def in vr_new_cols:
            if col_name not in existing_vr_cols:
                try:
                    await conn.execute(text(f"ALTER TABLE valuation_records ADD COLUMN {col_name} {col_def}"))
                except Exception:
                    pass

        # crawled_items 新增索引
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_crawled_items_keyword ON crawled_items(keyword)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_crawled_items_price ON crawled_items(price)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_crawled_items_crawled ON crawled_items(crawled_at DESC)"))

        # bargain_alerts 新增字段
        existing_bargain_cols = await _pg_get_columns(conn, "bargain_alerts")
        bargain_new_cols = [
            ("valuation_record_id", "BIGINT"),
            ("brand", "VARCHAR(64)"),
            ("current_price", "DOUBLE PRECISION"),
            ("base_price", "DOUBLE PRECISION"),
            ("discount_rate", "DOUBLE PRECISION"),
            ("condition", "VARCHAR(64)"),
            ("quality_score", "DOUBLE PRECISION"),
            ("is_xd_card", "BOOLEAN DEFAULT FALSE"),
            ("image_url", "VARCHAR(1024)"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ]
        for col_name, col_def in bargain_new_cols:
            if col_name not in existing_bargain_cols:
                try:
                    await conn.execute(text(f"ALTER TABLE bargain_alerts ADD COLUMN {col_name} {col_def}"))
                except Exception:
                    pass

        logger.info("数据库初始化完成（PostgreSQL 模式）")


async def _pg_get_columns(conn, table: str) -> set:
    rows = await conn.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
        {"t": table},
    )
    return {row[0] for row in rows.fetchall()}


async def _sqlite_get_columns(conn, table: str) -> set:
    rows = await conn.execute(
        text(f"PRAGMA table_info({table})"),
    )
    return {row[1] for row in rows.fetchall()}


async def _sqlite_get_tables(conn) -> set:
    rows = await conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'"),
    )
    return {row[0] for row in rows.fetchall()}
