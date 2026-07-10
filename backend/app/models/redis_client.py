import redis.asyncio as redis
from typing import Optional
import logging

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        from app.config import settings
        try:
            _redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await _redis_client.ping()
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.warning(f"Redis 连接失败，将使用降级策略: {e}")
            _redis_client = None
    return _redis_client


async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis 连接已关闭")


def redis_key(keyword: str) -> str:
    return f"ccd:val:{keyword}"


LIST_ALL_KEYWORDS = "ccd:val:list"
LOCK_CRAWL_KEY = "ccd:lock:crawl"
RATE_LIMIT_PREFIX = "ccd:rate:"
CRAWL_PROGRESS_KEY = "ccd:crawl:progress"
