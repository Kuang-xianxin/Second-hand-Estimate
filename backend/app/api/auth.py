from datetime import datetime
import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import AppUser
from app.models.database import get_db
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


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class RegisterRequest(AuthRequest):
    email: str = Field(default="", max_length=256)
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
    result = await db.execute(select(AppUser).where(AppUser.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = AppUser(
        username=username,
        password_hash=hash_password(req.password),
        email=req.email.strip().lower() or None,
        display_name=(req.display_name or username).strip(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token, _ = await create_session(user, db)
    return AuthResponse(token=token, user=_user_payload(user), xianyu=await _xianyu_state(user, db))


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
    email: str

class ResetConfirm(BaseModel):
    email: str
    code: str
    new_password: str


@router.post("/reset-password")
async def request_reset(req: ResetRequest, db: AsyncSession = Depends(get_db)):
    """发送密码重置验证码。验证码通过 print 日志输出（后续配 SMTP 发送邮件）。"""
    import secrets, time
    from app.models.redis_client import get_redis as _get_redis

    email = req.email.strip().lower()
    if not email:
        raise HTTPException(400, "邮箱不能为空")

    # 检查邮箱是否存在
    result = await db.execute(select(AppUser).where(AppUser.email == email))
    user = result.scalar_one_or_none()
    if not user:
        # 不泄露用户是否存在，统一返回成功
        return {"ok": True, "message": "如邮箱已注册，验证码将发送至管理员邮箱 2764905233@qq.com"}

    code = secrets.token_hex(3)[:6]
    r = await _get_redis()
    if r:
        await r.setex(f"reset:code:{email}", 600, code)

    # 日志代替发邮件
    logger.info(f"[密码重置] 用户={user.username} email={email} code={code}")
    sep = chr(61) * 50; print(f"\n{sep}\n密码重置验证码\n邮箱: {email}\n验证码: {code}\n有效期: 10分钟\n管理员: 2764905233@qq.com\n{sep}\n")

    return {"ok": True, "message": "如邮箱已注册，验证码将发送至管理员邮箱 2764905233@qq.com"}


@router.post("/reset-password/confirm")
async def confirm_reset(req: ResetConfirm, db: AsyncSession = Depends(get_db)):
    """验证验证码并重置密码"""
    from app.models.redis_client import get_redis as _get_redis

    email = req.email.strip().lower()
    code = (req.code or "").strip().lower()
    new_pw = (req.new_password or "").strip()

    if not email or not code or not new_pw:
        raise HTTPException(400, "邮箱、验证码、新密码不能为空")
    if len(new_pw) < 4:
        raise HTTPException(400, "新密码至少4位")

    r = await _get_redis()
    if r:
        stored = await r.get(f"reset:code:{email}")
        if not stored or stored.decode().lower() != code:
            raise HTTPException(400, "验证码错误或已过期")

    result = await db.execute(select(AppUser).where(AppUser.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")

    from app.services.auth import hash_password
    user.hashed_password = hash_password(new_pw)
    await db.commit()

    if r:
        await r.delete(f"reset:code:{email}")

    logger.info(f"[密码重置] 密码已重置 user={user.username}")
    return {"ok": True, "message": "密码已重置，请使用新密码登录"}

