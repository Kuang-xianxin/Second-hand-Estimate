"""Helpers for classifying Xianyu access failures."""

from __future__ import annotations

from typing import Mapping, Any


RISK_RET_MARKERS = (
    "FAIL_SYS_USER_VALIDATE",
    "RGV587",
    "USER_VALIDATE",
    "验证码",
    "风控",
    "安全验证",
    "被挤爆",
)

LOGIN_RET_MARKERS = (
    "FAIL_SYS_SESSION_EXPIRED",
    "FAIL_SYS_TOKEN_EXPIRED",
    "FAIL_SYS_TOKEN_EXOIRED",
    "SESSION_EXPIRED",
    "NEED_LOGIN",
    "LOGIN_REQUIRED",
    "USER_NOT_LOGIN",
    "请先登录",
    "登录态失效",
    "登录失效",
)

RISK_PAGE_MARKERS = (
    "验证码",
    "verify",
    "安全验证",
    "风控",
)

LOGIN_PAGE_MARKERS = (
    "请先登录",
    "登录",
    "login",
)


def _has_marker(text: str | None, markers: tuple[str, ...]) -> bool:
    if not text:
        return False
    upper_text = text.upper()
    return any(marker in text or marker.upper() in upper_text for marker in markers)


def normalize_xianyu_access_hints(
    login_hint: bool,
    risk_hint: bool,
) -> tuple[bool, bool]:
    """Return normalized login/risk hints, with explicit risk taking priority."""
    # WHY: Xianyu risk pages can contain SESSION/LOGIN text in their payload, so
    # a risk marker must suppress generic login hints from the same response.
    if risk_hint:
        return False, True
    return bool(login_hint), False


def classify_xianyu_access_hints(
    *,
    ret_text: str | None = None,
    page_text: str | None = None,
) -> tuple[bool, bool]:
    """Classify Xianyu response/page text as (login_required, risk_detected)."""
    # WHY: Playwright may expose the same anti-bot JSON as page/body text
    # instead of response_ret_samples, so body text must honor ret markers too.
    risk_hint = _has_marker(ret_text, RISK_RET_MARKERS) or _has_marker(
        page_text,
        RISK_RET_MARKERS + RISK_PAGE_MARKERS,
    )
    login_hint = _has_marker(ret_text, LOGIN_RET_MARKERS) or _has_marker(
        page_text,
        LOGIN_RET_MARKERS + LOGIN_PAGE_MARKERS,
    )
    return normalize_xianyu_access_hints(login_hint, risk_hint)


def normalize_xianyu_debug_summary(
    summary: Mapping[str, Any] | None,
) -> tuple[bool, bool]:
    summary = summary or {}
    ret_samples = summary.get("response_ret_samples") or []
    ret_text = " | ".join(str(sample) for sample in ret_samples)
    ret_login_hint, ret_risk_hint = classify_xianyu_access_hints(ret_text=ret_text)
    return normalize_xianyu_access_hints(
        bool(summary.get("login_page_hint")) or ret_login_hint,
        bool(summary.get("risk_page_hint")) or ret_risk_hint,
    )
