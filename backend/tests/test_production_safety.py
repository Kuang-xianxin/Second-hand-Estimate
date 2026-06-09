from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api import auth as auth_api
from app.api import cache_api
from app.api import valuate as valuate_api
from app.api.valuate import require_admin_token
from app.config import Settings, settings
from app.models.auth import AppUser
from app.services import redis_lock
from app.services.auth import verify_password


def _production_settings(**overrides):
    values = {
        "environment": "production",
        "database_url": "postgresql+asyncpg://user:password@db/guessr",
        "redis_url": "redis://redis:6379/0",
        "admin_token": "a" * 32,
        "site_auth_required": True,
        "cors_origins": "https://example.com",
        "trusted_hosts": "example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_production_settings_pass_validation():
    _production_settings().validate_production()


def test_production_crawl_requires_external_safe_worker():
    _production_settings(
        crawl_enabled=True,
        crawl_scheduler_mode="external",
        crawl_canary_enabled=True,
        crawl_stop_on_risk=True,
        crawl_concurrency=1,
        crawl_concurrency_max=1,
    ).validate_production()


@pytest.mark.parametrize(
    "override",
    [
        {"database_url": "sqlite+aiosqlite:///./guessr.db"},
        {"admin_token": "short"},
        {"site_auth_required": False},
        {"cors_origins": "*"},
        {"trusted_hosts": "*"},
        {"crawl_scheduler_mode": "unknown"},
        {"crawl_enabled": True, "crawl_scheduler_mode": "embedded"},
        {"crawl_enabled": True, "crawl_scheduler_mode": "external", "crawl_canary_enabled": False},
        {"crawl_enabled": True, "crawl_scheduler_mode": "external", "crawl_stop_on_risk": False},
        {
            "crawl_enabled": True,
            "crawl_scheduler_mode": "external",
            "crawl_concurrency": 2,
            "crawl_concurrency_max": 1,
        },
        {
            "crawl_enabled": True,
            "crawl_scheduler_mode": "external",
            "crawl_concurrency": 1,
            "crawl_concurrency_max": 2,
        },
    ],
)
def test_invalid_production_settings_fail_validation(override):
    with pytest.raises(RuntimeError):
        _production_settings(**override).validate_production()


def test_admin_endpoint_fails_closed_without_token(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", None)
    with pytest.raises(HTTPException) as exc:
        require_admin_token()
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_password_reset_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "password_reset_enabled", False)
    with pytest.raises(HTTPException) as exc:
        await auth_api.request_reset(auth_api.ResetRequest(email="user@example.com"), AsyncMock())
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_confirm_reset_updates_password_hash_and_revokes_sessions(monkeypatch):
    monkeypatch.setattr(settings, "password_reset_enabled", True)
    redis_client = AsyncMock()
    redis_client.incr.return_value = 1
    redis_client.get.return_value = "123456"
    monkeypatch.setattr(
        auth_api,
        "_get_required_reset_redis",
        AsyncMock(return_value=redis_client),
    )

    user = AppUser(id=7, username="alice", email="alice@example.com", password_hash="old")
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.side_effect = [user_result, MagicMock()]

    response = await auth_api.confirm_reset(
        auth_api.ResetConfirm(
            email="alice@example.com",
            code="123456",
            new_password="new-secure-password",
        ),
        db,
    )

    assert response["ok"] is True
    assert verify_password("new-secure-password", user.password_hash)
    assert db.execute.await_count == 2
    db.commit.assert_awaited_once()
    redis_client.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_production_redis_lock_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(redis_lock, "get_redis", AsyncMock(return_value=None))

    lock = redis_lock.RedisLock("test-lock")

    assert await lock.acquire() is False


@pytest.mark.asyncio
async def test_stream_task_cannot_be_stopped_by_another_user():
    task_id = "test-owned-task"
    valuate_api.stream_task_controls.pop(task_id, None)
    valuate_api._register_stream_task(task_id, user_id=1)
    try:
        with pytest.raises(HTTPException) as exc:
            await valuate_api.stop_valuate_task(
                task_id,
                current_user=AppUser(id=2, username="bob", password_hash="hash"),
            )
        assert exc.value.status_code == 404
    finally:
        valuate_api.stream_task_controls.pop(task_id, None)


@pytest.mark.asyncio
async def test_auth_rate_limiter_fails_closed_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(
        "app.models.redis_client.get_redis",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc:
        await auth_api._enforce_auth_rate_limit("login", "alice", 10, 300)

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_external_scheduler_mode_rejects_in_process_admin_crawl(monkeypatch):
    monkeypatch.setattr(settings, "crawl_scheduler_mode", "external")

    with pytest.raises(HTTPException) as exc:
        await cache_api.trigger_crawl(cache_api.TriggerCrawlRequest(), _admin=None)

    assert exc.value.status_code == 409


def test_external_scheduler_mode_skips_embedded_scheduler(monkeypatch):
    import main

    embedded_setup = MagicMock()
    monkeypatch.setattr(settings, "crawl_scheduler_mode", "external")
    monkeypatch.setattr(settings, "crawl_enabled", True)
    monkeypatch.setattr("app.scheduler.setup_scheduler", embedded_setup)

    main.setup_scheduler()

    embedded_setup.assert_not_called()
