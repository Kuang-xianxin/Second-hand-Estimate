from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.auth import AppSession, AppUser
from app.services import auth as auth_service


def test_password_hash_roundtrip():
    password_hash = auth_service.hash_password("secret-password")

    assert password_hash != "secret-password"
    assert auth_service.verify_password("secret-password", password_hash)
    assert not auth_service.verify_password("wrong-password", password_hash)
    assert not auth_service.verify_password("secret-password", "not-a-valid-hash")


@pytest.mark.asyncio
async def test_create_session_hashes_token_and_sets_expiry():
    db = AsyncMock()
    db.add = MagicMock()
    user = AppUser(id=7, username="alice", password_hash="hash")

    token, session = await auth_service.create_session(user, db)

    assert token
    assert session.user_id == 7
    assert session.token_hash == auth_service._hash_token(token)
    assert session.token_hash != token
    assert session.expires_at > datetime.utcnow()
    assert user.last_login_at is not None
    db.add.assert_called_once_with(session)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_get_current_user_optional_accepts_valid_bearer_token():
    token = "valid-token"
    user = AppUser(id=3, username="bob", password_hash="hash", is_active=True)
    session = AppSession(
        user_id=3,
        token_hash=auth_service._hash_token(token),
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    result = MagicMock()
    result.first.return_value = (session, user)
    db = AsyncMock()
    db.execute.return_value = result

    current_user = await auth_service.get_current_user_optional(
        authorization=f"Bearer {token}",
        db=db,
    )

    assert current_user is user
    assert session.last_seen_at is not None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_current_user_optional_rejects_expired_session():
    token = "expired-token"
    user = AppUser(id=4, username="carol", password_hash="hash", is_active=True)
    session = AppSession(
        user_id=4,
        token_hash=auth_service._hash_token(token),
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    )
    result = MagicMock()
    result.first.return_value = (session, user)
    db = AsyncMock()
    db.execute.return_value = result

    current_user = await auth_service.get_current_user_optional(
        authorization=f"Bearer {token}",
        db=db,
    )

    assert current_user is None
    db.commit.assert_not_awaited()
