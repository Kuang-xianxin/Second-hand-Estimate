from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import crawl_runner


def test_status_exit_codes():
    assert crawl_runner.status_exit_code("completed") == crawl_runner.EXIT_OK
    assert crawl_runner.status_exit_code("failed") == crawl_runner.EXIT_FAILED
    assert crawl_runner.status_exit_code("aborted") == crawl_runner.EXIT_FAILED
    assert crawl_runner.status_exit_code("running") == crawl_runner.EXIT_TEMPORARY
    assert crawl_runner.status_exit_code(None) == crawl_runner.EXIT_TEMPORARY


def test_batch_id_is_unique_enough_for_external_process():
    batch_id = crawl_runner.build_batch_id("t0")
    assert batch_id.startswith("t0_")
    assert batch_id.endswith(f"_{crawl_runner.os.getpid()}")
    assert len(batch_id) <= 64


@pytest.mark.asyncio
async def test_run_once_uses_exact_batch_and_returns_database_status(monkeypatch):
    run_tier = AsyncMock()
    monkeypatch.setattr("app.scheduler._run_tier_crawl", run_tier)
    monkeypatch.setattr(crawl_runner.settings, "crawl_enabled", True)
    monkeypatch.setattr(crawl_runner.settings, "crawl_t0_enabled", True)
    monkeypatch.setattr(crawl_runner.settings, "environment", "development")
    monkeypatch.setattr(crawl_runner, "init_db", AsyncMock())
    monkeypatch.setattr(crawl_runner, "claim_run_slot", AsyncMock(return_value=SimpleNamespace(allowed=True)))
    monkeypatch.setattr(crawl_runner, "record_run_result", AsyncMock())
    monkeypatch.setattr(crawl_runner, "build_batch_id", lambda _tier: "t0_test_batch")
    monkeypatch.setattr(
        crawl_runner,
        "read_batch_status",
        AsyncMock(
            return_value=SimpleNamespace(
                status="completed",
                success_count=1,
                fail_count=0,
                total_items=3,
                error_message=None,
            )
        ),
    )

    result = await crawl_runner.run_once("t0", keyword_limit=1)

    assert result == crawl_runner.EXIT_OK
    run_tier.assert_awaited_once()
    assert run_tier.await_args.kwargs["batch_id_override"] == "t0_test_batch"
    assert run_tier.await_args.kwargs["keyword_limit"] == 1


@pytest.mark.asyncio
async def test_run_once_fails_when_worker_produces_no_status(monkeypatch):
    monkeypatch.setattr("app.scheduler._run_tier_crawl", AsyncMock())
    monkeypatch.setattr(crawl_runner.settings, "crawl_enabled", True)
    monkeypatch.setattr(crawl_runner.settings, "crawl_t0_enabled", True)
    monkeypatch.setattr(crawl_runner.settings, "environment", "development")
    monkeypatch.setattr(crawl_runner, "init_db", AsyncMock())
    monkeypatch.setattr(crawl_runner, "claim_run_slot", AsyncMock(return_value=SimpleNamespace(allowed=True)))
    monkeypatch.setattr(crawl_runner, "current_keyword_offset", AsyncMock(return_value=0))
    advance = AsyncMock()
    monkeypatch.setattr(crawl_runner, "advance_keyword_offset", advance)
    monkeypatch.setattr(crawl_runner, "read_batch_status", AsyncMock(return_value=None))

    result = await crawl_runner.run_once("sweep", keyword_limit=1)

    assert result == crawl_runner.EXIT_TEMPORARY
    advance.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_sweep_advances_durable_cursor(monkeypatch):
    monkeypatch.setattr("app.scheduler._run_tier_crawl", AsyncMock())
    monkeypatch.setattr(crawl_runner.settings, "crawl_enabled", True)
    monkeypatch.setattr(crawl_runner.settings, "crawl_t0_enabled", True)
    monkeypatch.setattr(crawl_runner.settings, "environment", "development")
    monkeypatch.setattr(crawl_runner, "init_db", AsyncMock())
    monkeypatch.setattr(crawl_runner, "claim_run_slot", AsyncMock(return_value=SimpleNamespace(allowed=True)))
    monkeypatch.setattr(crawl_runner, "current_keyword_offset", AsyncMock(return_value=0))
    monkeypatch.setattr(crawl_runner, "record_run_result", AsyncMock())
    advance = AsyncMock()
    monkeypatch.setattr(crawl_runner, "advance_keyword_offset", advance)
    monkeypatch.setattr(
        crawl_runner,
        "read_batch_status",
        AsyncMock(
            return_value=SimpleNamespace(
                status="completed",
                success_count=1,
                fail_count=0,
                total_items=3,
                error_message=None,
            )
        ),
    )

    result = await crawl_runner.run_once("sweep")

    assert result == crawl_runner.EXIT_OK
    advance.assert_awaited_once_with("sweep")


@pytest.mark.asyncio
async def test_run_once_refuses_when_crawling_is_disabled(monkeypatch):
    monkeypatch.setattr(crawl_runner.settings, "crawl_enabled", False)
    monkeypatch.setattr(crawl_runner.settings, "environment", "development")

    assert await crawl_runner.run_once("t0") == crawl_runner.EXIT_CONFIG


def test_sweep_schedule_covers_every_model_once():
    schedule = crawl_runner.build_sweep_schedule()
    from app.services.ccd_keywords import get_model_keyword_groups

    assert len(schedule) == len(get_model_keyword_groups()) == 673
    assert len(set(schedule)) == len(schedule)
