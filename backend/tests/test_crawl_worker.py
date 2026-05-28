"""
Tests for crawl_worker safety controls, canary, and dynamic concurrency.
"""
import asyncio
import sys
from pathlib import Path

backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))


class FakeItem:
    def __init__(self, item_id: str, keyword: str):
        self.item_id = item_id
        self.query_keyword = keyword


class FakeCrawler:
    def __init__(self):
        self._last_debug_summary = {}

    async def search(self, keyword, max_items, cookie_override=None, filter_keyword=None):
        if keyword == "risk":
            self._last_debug_summary = {"risk_page_hint": True}
            return []
        if keyword == "login":
            self._last_debug_summary = {"login_page_hint": True}
            return []
        if keyword == "empty":
            self._last_debug_summary = {"response_count": 0}
            return []
        if keyword == "error":
            raise RuntimeError("simulated network error")
        self._last_debug_summary = {"response_count": 1, "raw_item_count": 3, "final_count": 3}
        return [FakeItem(f"{keyword}-{i}", keyword) for i in range(3)]


def test_crawl_all_aborts_on_risk(monkeypatch):
    from app.services import crawl_worker

    async def run():
        seen = []
        async def record(result):
            seen.append((result.keyword, result.success, result.risk_detected))
        monkeypatch.setattr(crawl_worker, "get_crawler", lambda: FakeCrawler())
        monkeypatch.setattr(crawl_worker.settings, "crawl_canary_enabled", False)
        report = await crawl_worker.crawl_all_ccd_models(
            ["ok1", "risk", "ok2"], concurrency=1, batch_size=3,
            keyword_result_callback=record, batch_id="test", started_at="",
            skip_canary=True,
        )
        return report, seen

    report, seen = asyncio.run(run())
    assert report.aborted is True
    assert "触发风控验证" in report.abort_reason
    assert report.success_count == 1
    assert report.fail_count == 1
    assert report.risk_detected_count == 1
    assert seen == [("ok1", True, False), ("risk", False, True)]


def test_crawl_all_aborts_on_login(monkeypatch):
    from app.services import crawl_worker

    async def run():
        monkeypatch.setattr(crawl_worker, "get_crawler", lambda: FakeCrawler())
        monkeypatch.setattr(crawl_worker.settings, "crawl_canary_enabled", False)
        report = await crawl_worker.crawl_all_ccd_models(
            ["login"], concurrency=1, batch_size=3, skip_canary=True,
        )
        return report

    report = asyncio.run(run())
    assert report.aborted is True
    assert report.login_required_count == 1
    assert "登录态失效" in report.abort_reason


def test_crawl_all_tier_and_max_items(monkeypatch):
    from app.services import crawl_worker

    async def run():
        monkeypatch.setattr(crawl_worker, "get_crawler", lambda: FakeCrawler())
        monkeypatch.setattr(crawl_worker.settings, "crawl_canary_enabled", False)
        report = await crawl_worker.crawl_all_ccd_models(
            ["ok1", "ok2"], concurrency=1, batch_size=2, tier="t0",
            max_items_per_kw=10, skip_canary=True,
        )
        return report

    report = asyncio.run(run())
    assert report.tier == "t0"
    assert report.success_count == 2
    assert report.fail_count == 0
    assert len(report.all_items) == 6


def test_tier_in_report(monkeypatch):
    from app.services import crawl_worker

    async def run():
        monkeypatch.setattr(crawl_worker, "get_crawler", lambda: FakeCrawler())
        monkeypatch.setattr(crawl_worker.settings, "crawl_canary_enabled", False)
        report = await crawl_worker.crawl_all_ccd_models(
            ["ok1"], concurrency=1, batch_size=1, tier="t0", skip_canary=True,
        )
        return report

    report = asyncio.run(run())
    assert report.tier == "t0"
    assert report.final_concurrency >= 1


def test_canary_failure_aborts_batch(monkeypatch):
    from app.services import crawl_worker

    async def fake_canary():
        return False, "mock canary failure", {"risk_page_hint": True}

    async def run():
        monkeypatch.setattr(crawl_worker, "crawl_canary", fake_canary)
        monkeypatch.setattr(crawl_worker, "get_crawler", lambda: FakeCrawler())
        monkeypatch.setattr(crawl_worker.settings, "crawl_canary_enabled", True)
        report = await crawl_worker.crawl_all_ccd_models(
            ["ok1", "ok2"], concurrency=1, batch_size=2,
        )
        return report

    report = asyncio.run(run())
    assert report.aborted is True
    assert report.canary_ok is False
    assert "canary" in report.abort_reason
    assert report.success_count == 0


def test_skip_canary(monkeypatch):
    from app.services import crawl_worker

    async def run():
        monkeypatch.setattr(crawl_worker, "get_crawler", lambda: FakeCrawler())
        monkeypatch.setattr(crawl_worker.settings, "crawl_canary_enabled", True)
        report = await crawl_worker.crawl_all_ccd_models(
            ["ok1"], concurrency=1, batch_size=1, skip_canary=True,
        )
        return report

    report = asyncio.run(run())
    assert report.aborted is False
    assert report.success_count == 1


class TestDynamicConcurrency:
    def test_initial_value(self):
        from app.services.crawl_worker import DynamicConcurrency
        dc = DynamicConcurrency(initial=2, max_concurrency=5)
        assert dc.current == 2
        assert dc.failure_rate == 0.0

    def test_all_success_recovery(self):
        from app.services.crawl_worker import DynamicConcurrency
        dc = DynamicConcurrency(initial=1, max_concurrency=3)
        for _ in range(10):
            dc.record(True)
        dc.adjust()
        assert dc.current >= 1

    def test_no_cold_start_increase(self):
        from app.services.crawl_worker import DynamicConcurrency
        dc = DynamicConcurrency(initial=1, max_concurrency=3)
        dc.adjust()
        assert dc.current == 1

    def test_high_failure_drops(self):
        from app.services.crawl_worker import DynamicConcurrency
        dc = DynamicConcurrency(initial=3, max_concurrency=5)
        for _ in range(5):
            dc.record(True)
        for _ in range(5):
            dc.record(False)
        assert dc.failure_rate >= 0.3
        dc.adjust()
        assert dc.current <= 2

    def test_never_below_one(self):
        from app.services.crawl_worker import DynamicConcurrency
        dc = DynamicConcurrency(initial=1, max_concurrency=3)
        for _ in range(10):
            dc.record(False)
        dc.adjust()
        assert dc.current >= 1


class TestCanaryFunction:
    def test_canary_disabled(self, monkeypatch):
        from app.services import crawl_worker

        async def run():
            monkeypatch.setattr(crawl_worker.settings, "crawl_canary_enabled", False)
            return await crawl_worker.crawl_canary()

        ok, reason, _ = asyncio.run(run())
        assert ok is True
        assert "disabled" in reason

    def test_no_keywords_configured(self, monkeypatch):
        from app.services import crawl_worker

        async def run():
            monkeypatch.setattr(crawl_worker.settings, "crawl_canary_enabled", True)
            monkeypatch.setattr(crawl_worker.settings, "crawl_canary_keywords", "")
            return await crawl_worker.crawl_canary()

        ok, reason, _ = asyncio.run(run())
        assert ok is True

    def test_canary_risk_detected(self, monkeypatch):
        from app.services import crawl_worker

        async def run():
            monkeypatch.setattr(crawl_worker, "get_crawler", lambda: FakeCrawler())
            monkeypatch.setattr(crawl_worker.settings, "crawl_canary_enabled", True)
            monkeypatch.setattr(crawl_worker.settings, "crawl_canary_keywords", "risk")
            return await crawl_worker.crawl_canary()

        ok, reason, _ = asyncio.run(run())
        assert ok is False

    def test_canary_login_required(self, monkeypatch):
        from app.services import crawl_worker

        async def run():
            monkeypatch.setattr(crawl_worker, "get_crawler", lambda: FakeCrawler())
            monkeypatch.setattr(crawl_worker.settings, "crawl_canary_enabled", True)
            monkeypatch.setattr(crawl_worker.settings, "crawl_canary_keywords", "login")
            return await crawl_worker.crawl_canary()

        ok, reason, _ = asyncio.run(run())
        assert ok is False

    def test_canary_empty_items_fails(self, monkeypatch):
        from app.services import crawl_worker

        async def run():
            monkeypatch.setattr(crawl_worker, "get_crawler", lambda: FakeCrawler())
            monkeypatch.setattr(crawl_worker.settings, "crawl_canary_enabled", True)
            monkeypatch.setattr(crawl_worker.settings, "crawl_canary_keywords", "empty")
            return await crawl_worker.crawl_canary()

        ok, reason, _ = asyncio.run(run())
        assert ok is False
        assert "无响应数据" in reason
