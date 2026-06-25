import sys
import types
from inspect import signature


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class _DummyModel:
    pass


_stub_module("app.models.redis_client", get_redis=lambda: None, CRAWL_PROGRESS_KEY="crawl_progress")
_stub_module("app.models.cache", CCDPriceCache=_DummyModel)
_stub_module("app.models.global_bargain", GlobalBargain=_DummyModel)
_stub_module("app.models.crawl_status", CrawlStatus=_DummyModel)
_stub_module("app.models.price_history", PriceHistory=_DummyModel)
_stub_module("app.models.auth", AppUser=_DummyModel)
_stub_module("app.services.auth", get_current_user=lambda: None)
_stub_module(
    "app.services.cache",
    get_cache_l1=lambda *_args, **_kwargs: None,
    get_cache_l2=lambda *_args, **_kwargs: None,
    get_cache_l3=lambda *_args, **_kwargs: None,
    get_cache_status=lambda *_args, **_kwargs: {},
)
_stub_module(
    "app.api.valuate",
    require_admin_token=lambda: None,
    _canonicalize_keyword=lambda keyword: keyword,
)

from app.api.stats_api import _normalize_crawl_progress, get_crawl_progress, get_stats_overview, stream_crawl_progress
from app.api.cache_api import (
    _has_implausible_global_bargain_price,
    cache_status,
    get_global_bargains,
    get_global_bargains_count,
)


def test_stats_endpoints_do_not_require_app_user_auth():
    # WHY: 前端没有站内账号登录入口；只读数据库状态不能因为缺 token 变成空白面板。
    assert "_current_user" not in signature(get_crawl_progress).parameters
    assert "_current_user" not in signature(stream_crawl_progress).parameters
    assert "_current_user" not in signature(get_stats_overview).parameters


def test_global_bargain_read_endpoints_do_not_require_app_user_auth():
    # WHY: bargain plaza uses these read-only endpoints anonymously; auth turns
    # the whole page into an empty state even when global bargain rows exist.
    assert "_current_user" not in signature(cache_status).parameters
    assert "_current_user" not in signature(get_global_bargains).parameters
    assert "_current_user" not in signature(get_global_bargains_count).parameters


def test_global_bargain_display_hides_implausible_polluted_prices():
    item = types.SimpleNamespace(current_price=299, base_price=5399, profit_estimate=5100)
    normal = types.SimpleNamespace(current_price=620, base_price=1399, profit_estimate=779)

    assert _has_implausible_global_bargain_price(item) is True
    assert _has_implausible_global_bargain_price(normal) is False


def test_crawl_progress_maps_item_progress_into_task_phase():
    progress = _normalize_crawl_progress({
        "stage": "crawling",
        "done": 1,
        "total": 1,
        "success_count": 0,
        "fail_count": 0,
        "total_items": 33,
        "max_items_per_kw": 40,
        "current_keyword": "canon A3300is",
    })

    assert progress["raw_done"] == 1
    assert progress["raw_total"] == 1
    assert progress["progress_percent"] == 57
    assert progress["display_done"] == 57
    assert progress["display_total"] == 100
    assert "33/40" in progress["current_keyword"]


def test_crawl_progress_later_phases_do_not_jump_behind_task_phase():
    progress = _normalize_crawl_progress({
        "stage": "pricing",
        "done": 1,
        "total": 1,
        "success_count": 1,
        "fail_count": 0,
        "total_items": 33,
        "max_items_per_kw": 40,
    })

    assert progress["progress_percent"] == 70


def test_crawl_progress_completed_is_exactly_100_percent():
    progress = _normalize_crawl_progress({
        "stage": "completed",
        "done": 1,
        "total": 1,
        "success_count": 1,
        "fail_count": 0,
        "total_items": 33,
        "max_items_per_kw": 40,
    })

    assert progress["progress_percent"] == 100
    assert progress["display_done"] == 100
    assert progress["display_total"] == 100
