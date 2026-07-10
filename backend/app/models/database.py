from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
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


async def _run_alembic_upgrade(conn):
    """Run alembic migrations inside an active connection."""
    from alembic.config import Config
    from alembic import command
    from pathlib import Path

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    # Override to use our existing connection
    alembic_cfg.attributes["connection"] = conn
    command.upgrade(alembic_cfg, "head")


async def init_db():
    """Initialize database schema.

    Uses Alembic migrations when available; falls back to create_all
    for fresh dev environments without migration history.
    """
    from sqlalchemy import inspect, text

    async with engine.begin() as conn:
        # Check if alembic_version table exists (migration already applied)
        try:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
            )
            has_alembic = result.fetchone() is not None
        except Exception:
            has_alembic = False

        if has_alembic:
            # Already managed by Alembic — run any pending migrations
            await _run_alembic_upgrade(conn)
        else:
            # Fresh DB: use Alembic to create everything from scratch
            try:
                await _run_alembic_upgrade(conn)
            except Exception:
                # Fallback: create_all for environments where Alembic can't run
                await conn.run_sync(Base.metadata.create_all)
