import logging
import uuid
from typing import Optional

from app.models.redis_client import get_redis, LOCK_CRAWL_KEY
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_LOCK_TTL = 1800  # 2 小时，超时自动释放


class RedisLock:
    """基于 Redis SETNX 的分布式锁。"""

    def __init__(self, key: str, ttl: int = DEFAULT_LOCK_TTL):
        self.key = key
        self.ttl = ttl
        self.token = str(uuid.uuid4())
        self._held = False

    async def acquire(self) -> bool:
        """尝试获取锁，成功返回 True（获取失败或 Redis 不可用返回 False）。"""
        r = await get_redis()
        if r is None:
            logger.warning("Redis 不可用，生产环境拒绝无锁执行")
            return not settings.is_production
        try:
            ok = await r.set(self.key, self.token, nx=True, ex=self.ttl)
            self._held = bool(ok)
            if self._held:
                logger.info(f"获取分布式锁成功: {self.key}")
            return self._held
        except Exception as e:
            logger.warning(f"分布式锁获取失败: {e}")
            return not settings.is_production

    async def release(self) -> bool:
        """释放锁（仅释放自己持有的锁，防止误删他人锁）。"""
        if not self._held:
            return True
        r = await get_redis()
        if r is None:
            return True
        try:
            lua = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = await r.eval(lua, 1, self.key, self.token)
            self._held = False
            if result:
                logger.info(f"释放分布式锁成功: {self.key}")
            return bool(result)
        except Exception as e:
            logger.warning(f"分布式锁释放失败: {e}")
            self._held = False
            return False

    async def extend(self, extra_seconds: int = None) -> bool:
        """延长锁的 TTL。"""
        if not self._held:
            return False
        r = await get_redis()
        if r is None:
            return False
        ttl = extra_seconds or self.ttl
        try:
            lua = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            result = await r.eval(lua, 1, self.key, self.token, ttl)
            return bool(result)
        except Exception as e:
            logger.warning(f"分布式锁延长失败: {e}")
            return False


async def acquire_crawl_lock(worker_id: str = "default", ttl: int = 7200) -> RedisLock:
    """获取定时任务分布式锁，确保多 Worker 环境下只有一个人物运行。"""
    lock = RedisLock(f"{LOCK_CRAWL_KEY}:{worker_id}", ttl=ttl)
    if not await lock.acquire():
        raise RuntimeError(f"无法获取定时任务锁，任务可能正在其他节点运行: {worker_id}")
    return lock
