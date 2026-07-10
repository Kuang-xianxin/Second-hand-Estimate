import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.auth import AppSession, AppUser
from app.models.database import get_db

PBKDF2_ITERATIONS = 210_000


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, rounds, salt_hex, digest_hex = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(rounds),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


async def create_session(user: AppUser, db: AsyncSession) -> tuple[str, AppSession]:
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    session = AppSession(
        user_id=user.id,
        token_hash=_hash_token(token),
        created_at=now,
        expires_at=now + timedelta(seconds=settings.app_session_ttl_seconds),
        last_seen_at=now,
    )
    user.last_login_at = now
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return token, session


async def revoke_session(token: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(AppSession).where(AppSession.token_hash == _hash_token(token))
    )
    session = result.scalar_one_or_none()
    if not session or session.revoked_at:
        return False
    session.revoked_at = datetime.utcnow()
    await db.commit()
    return True


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


async def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Optional[AppUser]:
    token = _extract_bearer_token(authorization)
    if not token:
        return None

    now = datetime.utcnow()
    result = await db.execute(
        select(AppSession, AppUser)
        .join(AppUser, AppUser.id == AppSession.user_id)
        .where(AppSession.token_hash == _hash_token(token))
    )
    row = result.first()
    if not row:
        return None

    session, user = row
    if session.revoked_at or session.expires_at <= now or not user.is_active:
        return None

    session.last_seen_at = now
    await db.commit()
    return user


async def get_current_user(
    user: Optional[AppUser] = Depends(get_current_user_optional),
) -> AppUser:
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录站内账号")
    return user
