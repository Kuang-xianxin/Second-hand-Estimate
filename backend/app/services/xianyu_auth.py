import json
import logging
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crawler.xianyu import STORAGE_STATE_FILE, get_crawler
from app.models.auth import AppUser, XianyuAuthBinding

BASE_DIR = Path(__file__).resolve().parents[2]
USER_STATE_DIR = BASE_DIR / "data" / "xianyu_states"
logger = logging.getLogger(__name__)


def _ensure_state_dir() -> None:
    USER_STATE_DIR.mkdir(parents=True, exist_ok=True)


def user_storage_state_path(user_id: int) -> Path:
    _ensure_state_dir()
    return USER_STATE_DIR / f"user_{user_id}.json"


def _state_has_cookies(path: Path) -> bool:
    try:
        if not path.exists() or path.stat().st_size <= 0:
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        return bool(data.get("cookies"))
    except Exception:
        return False


async def get_binding(user_id: int, db: AsyncSession) -> Optional[XianyuAuthBinding]:
    result = await db.execute(
        select(XianyuAuthBinding).where(XianyuAuthBinding.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert_binding(
    user: AppUser,
    db: AsyncSession,
    storage_state_path: Path,
    label: str = "",
    status: str = "unverified",
    failure_reason: str = "",
) -> XianyuAuthBinding:
    binding = await get_binding(user.id, db)
    now = datetime.utcnow()
    if binding is None:
        binding = XianyuAuthBinding(user_id=user.id, storage_state_path=str(storage_state_path))
        db.add(binding)

    binding.provider = "playwright_storage_state"
    binding.storage_state_path = str(storage_state_path)
    binding.xianyu_account_label = label or binding.xianyu_account_label
    binding.status = status
    binding.failure_reason = failure_reason
    binding.updated_at = now
    await db.commit()
    await db.refresh(binding)
    return binding


async def bind_from_global_state(
    user: AppUser,
    db: AsyncSession,
    label: str = "",
) -> XianyuAuthBinding:
    """把旧的全局 storage_state 复制到当前站内账号的独立授权文件。"""
    if not _state_has_cookies(STORAGE_STATE_FILE):
        raise HTTPException(status_code=400, detail="当前没有可导入的全局闲鱼登录态，请先完成闲鱼登录")

    target = user_storage_state_path(user.id)
    shutil.copyfile(STORAGE_STATE_FILE, target)
    return await upsert_binding(user, db, target, label=label, status="unverified")


async def verify_binding(
    user: AppUser,
    db: AsyncSession,
    force: bool = False,
) -> tuple[bool, str, dict]:
    """使用当前用户绑定的闲鱼 storage_state 做轻量 canary 校验。"""
    binding = await get_binding(user.id, db)
    if binding is None:
        return False, "当前站内账号尚未绑定闲鱼授权", {}

    path = Path(binding.storage_state_path)
    if not _state_has_cookies(path):
        binding.status = "missing"
        binding.failure_reason = "闲鱼授权文件不存在或为空"
        await db.commit()
        return False, binding.failure_reason, {}

    now = datetime.utcnow()
    if (
        not force
        and binding.status == "valid"
        and binding.last_verified_at
        and (now - binding.last_verified_at).total_seconds() < settings.xianyu_auth_verify_ttl_seconds
    ):
        return True, "cached valid", {}

    from app.services.crawl_worker import crawl_canary

    ok, reason, debug = await crawl_canary(storage_state_override=str(path))
    binding.last_verified_at = now
    binding.status = "valid" if ok else "invalid"
    binding.failure_reason = "" if ok else reason
    if ok:
        binding.expires_at = now + timedelta(hours=settings.xianyu_auth_soft_expire_hours)
    await db.commit()
    return ok, reason, debug


async def require_user_xianyu_state(
    user: Optional[AppUser],
    db: AsyncSession,
) -> Optional[str]:
    """
    返回当前站内用户可用的闲鱼 storage_state。
    若没有站内登录且未开启强制站内登录，则回退到旧全局登录态。
    """
    if user is None:
        if settings.site_auth_required:
            raise HTTPException(status_code=401, detail="请先登录站内账号")
        return str(STORAGE_STATE_FILE) if _state_has_cookies(STORAGE_STATE_FILE) else None

    # 先检查用户是否有个人绑定
    binding = await get_binding(user.id, db)
    if binding and _state_has_cookies(Path(binding.storage_state_path)):
        binding.last_used_at = datetime.utcnow()
        await db.commit()
        return binding.storage_state_path

    # 没有个人绑定时回退到全局登录态
    if _state_has_cookies(STORAGE_STATE_FILE):
        return str(STORAGE_STATE_FILE)

    raise HTTPException(status_code=428, detail="闲鱼授权不可用：请先绑定闲鱼账号或导入全局登录态")


async def choose_scheduler_storage_state(db: AsyncSession) -> Optional[str]:
    """
    后台爬取选择一个最近验证过的用户闲鱼授权。
    没有用户绑定时回退到旧全局登录态，便于平滑迁移。
    """
    now = datetime.utcnow()
    result = await db.execute(
        select(XianyuAuthBinding)
        .where(XianyuAuthBinding.status == "valid")
        .order_by(XianyuAuthBinding.last_used_at.asc())
        .limit(1)
    )
    binding = result.scalar_one_or_none()
    if binding and _state_has_cookies(Path(binding.storage_state_path)):
        binding.last_used_at = now
        await db.commit()
        return binding.storage_state_path
    return str(STORAGE_STATE_FILE) if _state_has_cookies(STORAGE_STATE_FILE) else None


def start_local_auth_flow(user_id: int, label: str = "") -> bool:
    """
    本机可视化绑定流程：打开 Playwright 浏览器，登录完成后保存到当前用户文件。
    云端环境没有桌面，使用导入 storage_state 的方式更可靠。
    """
    if os.getenv("RENDER") or (os.name != "nt" and not os.getenv("DISPLAY")):
        raise HTTPException(status_code=400, detail="当前环境无法弹出可见浏览器，请使用导入登录态方式绑定闲鱼授权")

    target = user_storage_state_path(user_id)

    def _run():
        from playwright.sync_api import sync_playwright

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=["--no-first-run", "--disable-blink-features=AutomationControlled"],
                )
                context_kwargs = {
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "viewport": {"width": 1280, "height": 800},
                }
                if target.exists() and target.stat().st_size > 0:
                    context_kwargs["storage_state"] = str(target)
                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(120000)
                context.storage_state(path=str(target))
                context.close()
                browser.close()
        except Exception:
            logger.exception("本地闲鱼授权浏览器流程失败")

    threading.Thread(target=_run, daemon=True).start()
    return True
