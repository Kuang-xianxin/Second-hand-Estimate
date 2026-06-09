from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.auth import XianyuAuthBinding
from app.models.auth import AppUser
from app.services import xianyu_auth


def test_binding_effective_status_rejects_expired_state(monkeypatch):
    binding = XianyuAuthBinding(
        user_id=1,
        storage_state_path="/tmp/state.json",
        status="valid",
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )
    monkeypatch.setattr(xianyu_auth, "_state_has_cookies", lambda _path: True)

    assert xianyu_auth.binding_effective_status(binding) == "expired"
    assert not xianyu_auth.binding_is_usable(binding)


@pytest.mark.asyncio
async def test_require_user_state_does_not_use_expired_binding(monkeypatch):
    binding = XianyuAuthBinding(
        user_id=1,
        storage_state_path="/tmp/expired.json",
        status="valid",
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = binding
    db = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(xianyu_auth, "_state_has_cookies", lambda path: path == Path("/global.json"))
    monkeypatch.setattr(xianyu_auth, "STORAGE_STATE_FILE", Path("/global.json"))

    selected = await xianyu_auth.require_user_xianyu_state(
        AppUser(id=1, username="alice", password_hash="hash"),
        db,
    )

    assert selected == str(Path("/global.json"))
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduler_selection_requires_unexpired_binding(monkeypatch):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute.return_value = result
    monkeypatch.setattr(xianyu_auth, "_state_has_cookies", lambda _path: False)

    selected = await xianyu_auth.choose_scheduler_storage_state(db)

    assert selected is None
    statement = str(db.execute.await_args.args[0])
    assert "xianyu_auth_bindings.status" in statement
    assert "xianyu_auth_bindings.expires_at IS NOT NULL" in statement
    assert "xianyu_auth_bindings.expires_at >" in statement


@pytest.mark.asyncio
async def test_scheduler_risk_marks_binding_limited():
    binding = XianyuAuthBinding(
        user_id=1,
        storage_state_path="/tmp/state.json",
        status="valid",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = binding
    db = AsyncMock()
    db.execute.return_value = result

    before = datetime.utcnow()
    await xianyu_auth.update_scheduler_storage_state_health(
        db,
        "/tmp/state.json",
        ok=False,
        reason="risk detected",
        risk_limited=True,
    )

    assert binding.status == "risk_limited"
    assert binding.failure_reason == "risk detected"
    assert binding.expires_at >= before
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_scheduler_success_refreshes_binding():
    binding = XianyuAuthBinding(
        user_id=1,
        storage_state_path="/tmp/state.json",
        status="invalid",
        failure_reason="old failure",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = binding
    db = AsyncMock()
    db.execute.return_value = result

    before = datetime.utcnow()
    await xianyu_auth.update_scheduler_storage_state_health(
        db,
        "/tmp/state.json",
        ok=True,
    )

    assert binding.status == "valid"
    assert binding.failure_reason == ""
    assert binding.expires_at > before
    db.commit.assert_awaited_once()
