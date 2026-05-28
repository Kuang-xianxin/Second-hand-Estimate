from datetime import datetime
import json
import random
import re
import string
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import AppUser
from app.models.database import get_db
from app.models.redis_client import get_redis
from app.services.auth import (
    create_session,
    get_current_user,
    hash_password,
    revoke_session,
    verify_password,
)
from app.services.xianyu_auth import (
    bind_from_global_state,
    get_binding,
    start_local_auth_flow,
    upsert_binding,
    user_storage_state_path,
    verify_binding,
)

router = APIRouter(prefix="/api", tags=["账号"])

RESET_CODE_TTL = 600  # 10 minutes
ADMIN_EMAIL = "2764905233@qq.com"


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class RegisterRequest(AuthRequest):
    display_name: Optional[str] = Field(default=None, max_length=128)
    email: Optional[str] = Field(default=None, max_length=256)


class ResetPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=256)


class ResetPasswordConfirmRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=256)
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6, max_length=128)


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
    xianyu_bound: bool = False


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


def _validate_email(email: str) -> str:
    value = (email or "").strip().lower()
    if not value or "@" not in value or "." not in value.split("@")[-1]:
        raise HTTPException(status_code=422, detail="请提供有效的邮箱地址")
    return value


def _generate_code() -> str:
    return "".join(random.choices(string.digits, k=6))


async def _xianyu_state(user: AppUser, db: AsyncSession, verify_if_present: bool = False) -> XianyuAuthState:
    binding = await get_binding(user.id, db)
    if binding is None:
        return XianyuAuthState(bound=False, status="missing")
    if verify_if_present:
        await verify_binding(user, db, force=False)
        binding = await get_binding(user.id, db)
    return XianyuAuthState(
        bound=True,
        status=binding.status,
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
        "email": getattr(user, "email", ""),
    }


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


@router.post("/auth/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    username = _validate_username(req.username)
    email = _validate_email(req.email) if req.email else ""

    result = await db.execute(select(AppUser).where(AppUser.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = AppUser(
        username=username,
        password_hash=hash_password(req.password),
        display_name=(req.display_name or username).strip(),
    )
    if email:
        user.email = email
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token, _ = await create_session(user, db)
    xianyu = await _xianyu_state(user, db)
    return AuthResponse(
        token=token, user=_user_payload(user), xianyu=xianyu,
        xianyu_bound=xianyu.status == "valid",
    )


@router.post("/auth/login", response_model=AuthResponse)
async def login(req: AuthRequest, db: AsyncSession = Depends(get_db)):
    username = _validate_username(req.username)
    result = await db.execute(select(AppUser).where(AppUser.username == username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")

    token, _ = await create_session(user, db)
    xianyu = await _xianyu_state(user, db, verify_if_present=True)
    return AuthResponse(
        token=token, user=_user_payload(user), xianyu=xianyu,
        xianyu_bound=xianyu.status == "valid",
    )


@router.get("/auth/me")
async def me(user: AppUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    xianyu = await _xianyu_state(user, db)
    return {
        "user": _user_payload(user),
        "xianyu": xianyu.dict(),
        "xianyu_bound": xianyu.status == "valid",
    }


@router.post("/auth/logout")
async def logout(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    token = _extract_token(authorization)
    if token:
        await revoke_session(token, db)
    return {"ok": True}


# ---- Password Reset ----

@router.post("/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Send a 6-digit reset code to the admin email (logged for now)."""
    email = _validate_email(req.email)
    code = _generate_code()
    r = await get_redis()
    if r:
        await r.setex(f"reset:code:{email}", RESET_CODE_TTL, code)

    # TODO: send actual email via SMTP
    print(f"[PASSWORD RESET] email={email} code={code} admin={ADMIN_EMAIL}")
    return {"ok": True, "message": f"验证码已发送至管理员邮箱 {ADMIN_EMAIL}，请查收后输入"}


@router.post("/auth/reset-password/confirm")
async def reset_password_confirm(req: ResetPasswordConfirmRequest, db: AsyncSession = Depends(get_db)):
    email = _validate_email(req.email)
    if not req.code or len(req.code) != 6 or not req.code.isdigit():
        raise HTTPException(status_code=422, detail="验证码为 6 位数字")

    r = await get_redis()
    stored = None
    if r:
        stored = await r.get(f"reset:code:{email}")
        if stored:
            stored = stored.decode() if isinstance(stored, bytes) else stored

    if not stored or stored != req.code:
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    # Find user by email
    result = await db.execute(select(AppUser).where(AppUser.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="未找到该邮箱对应的账号")

    user.password_hash = hash_password(req.new_password)
    await db.commit()

    # Delete code
    if r:
        await r.delete(f"reset:code:{email}")

    return {"ok": True, "message": "密码已重置，请使用新密码登录"}


# ---- Xianyu ----

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
