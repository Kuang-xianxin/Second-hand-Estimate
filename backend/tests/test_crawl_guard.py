from unittest.mock import AsyncMock

import pytest

from app.services import crawl_guard


@pytest.mark.asyncio
async def test_global_cooldown_blocks_every_tier(monkeypatch):
    client = AsyncMock()
    client.ttl.return_value = 600
    client.get.return_value = "risk cooldown"
    monkeypatch.setattr(crawl_guard, "get_redis", AsyncMock(return_value=client))

    decision = await crawl_guard.claim_run_slot("t0")

    assert decision.allowed is False
    assert decision.remaining_seconds == 600
    client.ttl.assert_awaited_once_with("ccd:crawl:guard:all:cooldown")


@pytest.mark.asyncio
async def test_global_attempt_gate_blocks_rapid_second_worker(monkeypatch):
    client = AsyncMock()
    client.ttl.side_effect = [-2, 120]
    client.set.return_value = None
    monkeypatch.setattr(crawl_guard, "get_redis", AsyncMock(return_value=client))

    decision = await crawl_guard.claim_run_slot("t1")

    assert decision.allowed is False
    assert decision.remaining_seconds == 120
    client.set.assert_awaited_once()
    assert client.set.await_args.args[0] == "ccd:crawl:guard:all:attempt_gate"


@pytest.mark.asyncio
async def test_risk_result_sets_long_global_cooldown(monkeypatch):
    client = AsyncMock()
    client.incr.return_value = 1
    monkeypatch.setattr(crawl_guard, "get_redis", AsyncMock(return_value=client))
    monkeypatch.setattr(crawl_guard.settings, "crawl_risk_cooldown_seconds", 604800)
    monkeypatch.setattr(crawl_guard.settings, "crawl_max_cooldown_seconds", 2592000)

    cooldown = await crawl_guard.record_run_result(
        "sweep",
        "failed",
        "FAIL_SYS_USER_VALIDATE RGV587_ERROR",
    )

    assert cooldown == 604800
    assert client.setex.await_args_list[0].args[0] == "ccd:crawl:guard:all:cooldown"


@pytest.mark.asyncio
async def test_empty_result_does_not_create_global_cooldown(monkeypatch):
    client = AsyncMock()
    monkeypatch.setattr(crawl_guard, "get_redis", AsyncMock(return_value=client))

    cooldown = await crawl_guard.record_run_result(
        "sweep",
        "failed",
        "没有可写入缓存的有效估价结果",
    )

    assert cooldown == 0
    client.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_initial_cooldown_does_not_extend_existing_one(monkeypatch):
    client = AsyncMock()
    client.ttl.return_value = 3600
    monkeypatch.setattr(crawl_guard, "get_redis", AsyncMock(return_value=client))

    remaining = await crawl_guard.ensure_cooldown("all", 604800, "initial quiet period")

    assert remaining == 3600
    client.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_sweep_cursor_advances_only_when_requested(monkeypatch):
    client = AsyncMock()
    monkeypatch.setattr(crawl_guard, "get_redis", AsyncMock(return_value=client))

    await crawl_guard.advance_keyword_offset("sweep")

    client.incr.assert_awaited_once_with("ccd:crawl:guard:sweep:keyword_cursor")
