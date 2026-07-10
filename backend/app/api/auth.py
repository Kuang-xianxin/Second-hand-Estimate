import asyncio
from datetime import datetime
from email.message import EmailMessage
import hashlib
import hmac
import json
import logging
import re
import smtplib
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.auth import AppSession, AppUser
from app.models.database import get_db
from app.services.auth import (
    create_session,
    get_current_user,
    hash_password,
    revoke_session,
    verify_password,
)
from app.services.xianyu_auth import (
    binding_effective_status,
    bind_from_global_state,
    get_binding,
    start_local_auth_flow,
    upsert_binding,
    user_storage_state_path,
    verify_binding,
)

router = APIRouter(prefix="/api", tags=["账号"])
logger = logging.getLogger(__name__)


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class RegisterRequest(AuthRequest):
    password: str = Field(..., min_length=8, max_length=128)
    email: EmailStr
    display_name: Optional[str] = Field(default=None, max_length=128)

class XianyuAuthState(BaseModel):
    bound: bool
    status: str = "missing"
    provider: str = "playwright_storage_state"
    account_label: Optional[str] = None
    last_verified_at: Optional[str] = None
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None
    failure_reason: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    user: dict
    xianyu: XianyuAuthState


class BindCurrentStateRequest(BaseModel):
    label: Optional[str] = None


class ImportStorageStateRequest(BaseModel):
    storage_state: dict
    label: Optional[str] = None
    verify_now: bool = True


class StartXianyuAuthRequest(BaseModel):
    label: Optional[str] = None


def _dt(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _validate_username(username: str) -> str:
    value = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9_@.-]{3,64}", value):
        raise HTTPException(status_code=422, detail="用户名只能包含字母、数字、下划线、点、横线或 @")
    return value


async def _xianyu_state(user: AppUser, db: AsyncSession, verify_if_present: bool = False) -> XianyuAuthState:
    binding = await get_binding(user.id, db)
    if binding is None:
        return XianyuAuthState(bound=False, status="missing")
    if verify_if_present:
        await verify_binding(user, db, force=False)
        binding = await get_binding(user.id, db)
    return XianyuAuthState(
        bound=True,
        status=binding_effective_status(binding),
        provider=binding.provider,
        account_label=binding.xianyu_account_label,
        last_verified_at=_dt(binding.last_verified_at),
        last_used_at=_dt(binding.last_used_at),
        expires_at=_dt(binding.expires_at),
        failure_reason=binding.failure_reason,
    )


def _user_payload(user: AppUser) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
    }


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def _auth_rate_key(action: str, identifier: str) -> str:
    digest = hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()
    return f"auth:rate:{action}:{digest}"


async def _enforce_auth_rate_limit(
    action: str,
    identifier: str,
    limit: int,
    window_seconds: int,
) -> None:
    from app.models.redis_client import get_redis

    try:
        redis_client = await get_redis()
        if redis_client is None:
            if settings.is_production:
                raise HTTPException(status_code=503, detail="认证服务暂不可用")
            return

        key = _auth_rate_key(action, identifier)
        attempts = await redis_client.incr(key)
        if attempts == 1:
            await redis_client.expire(key, window_seconds)
        if attempts > limit:
            raise HTTPException(status_code=429, detail="尝试次数过多，请稍后再试")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Authentication rate limiter unavailable: %s", exc)
        if settings.is_production:
            raise HTTPException(status_code=503, detail="认证服务暂不可用") from exc


async def _clear_auth_rate_limit(action: str, identifier: str) -> None:
    from app.models.redis_client import get_redis

    try:
        redis_client = await get_redis()
        if redis_client is not None:
            await redis_client.delete(_auth_rate_key(action, identifier))
    except Exception:
        logger.warning("Failed to clear authentication rate limit", exc_info=True)


@router.post("/auth/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    username = _validate_username(req.username)
    email = str(req.email).strip().lower()
    await _enforce_auth_rate_limit("register", f"{username}:{email}", limit=5, window_seconds=3600)
    result = await db.execute(
        select(AppUser).where(
            (AppUser.username == username) | (AppUser.email == email)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名或邮箱已注册")

    user = AppUser(
        username=username,
        password_hash=hash_password(req.password),
        email=email,
        display_name=(req.display_name or username).strip(),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="用户名或邮箱已注册") from exc
    await db.refresh(user)
    token, _ = await create_session(user, db)
    return AuthResponse(token=token, user=_user_payload(user), xianyu=await _xianyu_state(user, db))


@router.post("/auth/login", response_model=AuthResponse)
async def login(req: AuthRequest, db: AsyncSession = Depends(get_db)):
    username = _validate_username(req.username)
    await _enforce_auth_rate_limit("login", username, limit=10, window_seconds=300)
    result = await db.execute(select(AppUser).where(AppUser.username == username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")

    await _clear_auth_rate_limit("login", username)
    token, _ = await create_session(user, db)
    xianyu = await _xianyu_state(user, db, verify_if_present=True)
    return AuthResponse(token=token, user=_user_payload(user), xianyu=xianyu)


@router.get("/auth/me")
async def me(user: AppUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"user": _user_payload(user), "xianyu": await _xianyu_state(user, db)}


@router.post("/auth/logout")
async def logout(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    token = _extract_token(authorization)
    if token:
        await revoke_session(token, db)
    return {"ok": True}


@router.get("/xianyu/status", response_model=XianyuAuthState)
async def xianyu_status(
    verify: bool = False,
    user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _xianyu_state(user, db, verify_if_present=verify)


@router.post("/xianyu/verify", response_model=XianyuAuthState)
async def xianyu_verify(
    user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_binding(user, db, force=True)
    return await _xianyu_state(user, db)


@router.post("/xianyu/bind-current-state", response_model=XianyuAuthState)
async def xianyu_bind_current_state(
    req: BindCurrentStateRequest,
    user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await bind_from_global_state(user, db, label=req.label or "")
    await verify_binding(user, db, force=True)
    return await _xianyu_state(user, db)


@router.post("/xianyu/import-storage-state", response_model=XianyuAuthState)
async def xianyu_import_storage_state(
    req: ImportStorageStateRequest,
    user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target = user_storage_state_path(user.id)
    target.write_text(json.dumps(req.storage_state, ensure_ascii=False, indent=2), encoding="utf-8")
    await upsert_binding(user, db, target, label=req.label or "", status="unverified")
    if req.verify_now:
        await verify_binding(user, db, force=True)
    return await _xianyu_state(user, db)


@router.post("/xianyu/auth/start", response_model=XianyuAuthState)
async def xianyu_auth_start(
    req: StartXianyuAuthRequest,
    user: AppUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target = user_storage_state_path(user.id)
    await upsert_binding(user, db, target, label=req.label or "", status="auth_in_progress")
    start_local_auth_flow(user.id, label=req.label or "")
    return await _xianyu_state(user, db)

# ============================================================
# 密码重置
# ============================================================

class ResetRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=256)

class ResetConfirm(BaseModel):
    email: str = Field(..., min_length=3, max_length=256)
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)


async def _send_password_reset_email(email: str, code: str) -> None:
    def send() -> None:
        message = EmailMessage()
        message["Subject"] = "估二手密码重置验证码"
        message["From"] = settings.smtp_from_email
        message["To"] = email
        message.set_content(f"你的密码重置验证码是：{code}\n\n验证码 10 分钟内有效。")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)

    await asyncio.to_thread(send)


def _password_reset_message() -> dict:
    return {"ok": True, "message": "如邮箱已注册，验证码将发送至该邮箱"}


async def _get_required_reset_redis():
    from app.models.redis_client import get_redis

    redis_client = await get_redis()
    if redis_client is None:
        raise HTTPException(status_code=503, detail="密码重置服务暂不可用")
    return redis_client


@router.post("/reset-password")
async def request_reset(req: ResetRequest, db: AsyncSession = Depends(get_db)):
    """发送密码重置验证码。"""
    import secrets

    if not settings.password_reset_enabled:
        raise HTTPException(status_code=503, detail="密码重置服务未启用")
    email = req.email.strip().lower()
    if not email:
        raise HTTPException(400, "邮箱不能为空")

    redis_client = await _get_required_reset_redis()
    rate_key = f"reset:request:{email}"
    if not await redis_client.set(rate_key, "1", nx=True, ex=60):
        return _password_reset_message()

    result = await db.execute(select(AppUser).where(AppUser.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return _password_reset_message()

    code = f"{secrets.randbelow(1_000_000):06d}"
    code_key = f"reset:code:{email}"
    await redis_client.setex(code_key, 600, code)
    try:
        await _send_password_reset_email(email, code)
    except Exception as exc:
        await redis_client.delete(code_key)
        logger.exception("Password reset email delivery failed for user_id=%s", user.id)
        raise HTTPException(status_code=503, detail="密码重置邮件发送失败，请稍后重试") from exc

    logger.info("Password reset email queued for user_id=%s", user.id)
    return _password_reset_message()


@router.post("/reset-password/confirm")
async def confirm_reset(req: ResetConfirm, db: AsyncSession = Depends(get_db)):
    """验证验证码并重置密码"""
    if not settings.password_reset_enabled:
        raise HTTPException(status_code=503, detail="密码重置服务未启用")
    email = req.email.strip().lower()
    code = (req.code or "").strip()
    new_pw = (req.new_password or "").strip()

    if not email or not code or not new_pw:
        raise HTTPException(400, "邮箱、验证码、新密码不能为空")

    redis_client = await _get_required_reset_redis()
    attempts_key = f"reset:attempts:{email}"
    attempts = await redis_client.incr(attempts_key)
    if attempts == 1:
        await redis_client.expire(attempts_key, 600)
    if attempts > 5:
        await redis_client.delete(f"reset:code:{email}")
        raise HTTPException(status_code=429, detail="验证码尝试次数过多，请重新申请")

    stored = await redis_client.get(f"reset:code:{email}")
    if not stored or not hmac.compare_digest(str(stored), code):
        raise HTTPException(400, "验证码错误或已过期")

    result = await db.execute(select(AppUser).where(AppUser.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(400, "验证码错误或已过期")

    user.password_hash = hash_password(new_pw)
    await db.execute(
        update(AppSession)
        .where(AppSession.user_id == user.id, AppSession.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow())
    )
    await db.commit()
    await redis_client.delete(f"reset:code:{email}", attempts_key)
    logger.info("Password reset completed for user_id=%s", user.id)
    return {"ok": True, "message": "密码已重置，请使用新密码登录"}
