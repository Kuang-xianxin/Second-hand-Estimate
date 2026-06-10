"""Fail-closed rate guard for the production Xianyu crawler."""

import logging
import time
from dataclasses import dataclass

from app.config import settings
from app.models.redis_client import get_redis

logger = logging.getLogger(__name__)

GUARD_PREFIX = "ccd:crawl:guard"
REQUEST_GUARD_SCOPE = "all"


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str = ""
    remaining_seconds: int = 0


def _key(tier: str, suffix: str) -> str:
    return f"{GUARD_PREFIX}:{tier}:{suffix}"


def classify_failure(error_message: str) -> str:
    text = (error_message or "").lower()
    risk_markers = (
        "risk",
        "风控",
        "rgv587",
        "fail_sys_user_validate",
        "被挤爆",
        "验证",
    )
    login_markers = (
        "login",
        "登录",
        "cookie",
        "session",
        "token",
        "授权",
    )
    empty_markers = (
        "没有爬到任何商品",
        "没有可写入缓存的有效估价结果",
        "未解析到有效商品",
    )
    if any(marker in text for marker in risk_markers):
        return "risk"
    if any(marker in text for marker in login_markers):
        return "login"
    if any(marker in text for marker in empty_markers):
        return "empty"
    return "failure"


async def claim_run_slot(tier: str) -> GuardDecision:
    """Atomically reserve one production crawl slot before any Xianyu request."""
    client = await get_redis()
    if client is None:
        if settings.is_production:
            return GuardDecision(False, "Redis unavailable; crawl guard fails closed")
        return GuardDecision(True, "Redis unavailable in development")

    cooldown_ttl = int(await client.ttl(_key(REQUEST_GUARD_SCOPE, "cooldown")))
    if cooldown_ttl > 0:
        reason = (
            await client.get(_key(REQUEST_GUARD_SCOPE, "cooldown_reason"))
            or "cooldown active"
        )
        return GuardDecision(False, reason, cooldown_ttl)

    interval = max(1, int(settings.crawl_min_interval_seconds))
    claimed = await client.set(
        _key(REQUEST_GUARD_SCOPE, "attempt_gate"),
        str(int(time.time())),
        nx=True,
        ex=interval,
    )
    if not claimed:
        remaining = max(
            0,
            int(await client.ttl(_key(REQUEST_GUARD_SCOPE, "attempt_gate"))),
        )
        return GuardDecision(False, "minimum crawl interval has not elapsed", remaining)

    return GuardDecision(True)


async def current_keyword_offset(tier: str, keyword_count: int) -> int:
    """Read the durable sweep cursor without advancing it."""
    if keyword_count <= 0:
        return 0
    client = await get_redis()
    if client is None:
        return 0
    cursor = int(await client.get(_key(tier, "keyword_cursor")) or 0)
    return cursor % keyword_count


async def advance_keyword_offset(tier: str) -> None:
    """Advance only after success or a confirmed empty result."""
    client = await get_redis()
    if client is None:
        if settings.is_production:
            raise RuntimeError("Redis unavailable; cannot advance crawl cursor")
        return
    await client.incr(_key(tier, "keyword_cursor"))


async def set_cooldown(tier: str, seconds: int, reason: str) -> None:
    client = await get_redis()
    if client is None:
        if settings.is_production:
            raise RuntimeError("Redis unavailable; cannot persist crawl cooldown")
        return
    ttl = max(1, int(seconds))
    await client.setex(_key(tier, "cooldown"), ttl, str(int(time.time())))
    await client.setex(_key(tier, "cooldown_reason"), ttl, reason[:500])


async def ensure_cooldown(tier: str, seconds: int, reason: str) -> int:
    """Set an initial cooldown without extending one that is already active."""
    client = await get_redis()
    if client is None:
        if settings.is_production:
            raise RuntimeError("Redis unavailable; cannot persist crawl cooldown")
        return 0

    current_ttl = int(await client.ttl(_key(tier, "cooldown")))
    if current_ttl > 0:
        return current_ttl

    ttl = max(1, int(seconds))
    created = await client.set(
        _key(tier, "cooldown"),
        str(int(time.time())),
        nx=True,
        ex=ttl,
    )
    if created:
        await client.setex(_key(tier, "cooldown_reason"), ttl, reason[:500])
        return ttl
    return max(0, int(await client.ttl(_key(tier, "cooldown"))))


async def record_run_result(tier: str, status: str | None, error_message: str = "") -> int:
    """Persist success or an exponentially increasing failure cooldown."""
    client = await get_redis()
    if client is None:
        if settings.is_production:
            raise RuntimeError("Redis unavailable; cannot persist crawl result")
        return 0

    if status == "completed":
        await client.delete(_key(REQUEST_GUARD_SCOPE, "failure_streak"))
        await client.set(_key(REQUEST_GUARD_SCOPE, "last_success_at"), str(int(time.time())))
        return 0

    failure_kind = classify_failure(error_message)
    if failure_kind == "empty":
        await client.delete(_key(REQUEST_GUARD_SCOPE, "failure_streak"))
        return 0
    streak = int(await client.incr(_key(REQUEST_GUARD_SCOPE, "failure_streak")))
    base = (
        settings.crawl_risk_cooldown_seconds
        if failure_kind in {"risk", "login"}
        else settings.crawl_failure_cooldown_seconds
    )
    cooldown = min(
        int(base) * (2 ** min(streak - 1, 4)),
        int(settings.crawl_max_cooldown_seconds),
    )
    reason = f"{failure_kind} failure streak={streak}: {error_message or status or 'unknown'}"
    await set_cooldown(REQUEST_GUARD_SCOPE, cooldown, reason)
    logger.warning("Crawl guard activated tier=%s cooldown=%ss reason=%s", tier, cooldown, reason)
    return cooldown
