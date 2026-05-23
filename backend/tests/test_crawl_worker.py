"""
Tests for crawl_worker safety controls.
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
        self._last_debug_summary = {}
        return [FakeItem(f"{keyword}-1", keyword)]


def test_crawl_all_aborts_on_risk(monkeypatch):
    from app.services import crawl_worker

    async def run():
        seen = []

        async def record(result):
            seen.append((result.keyword, result.success, result.risk_detected))

        monkeypatch.setattr(crawl_worker, "get_crawler", lambda: FakeCrawler())
        report = await crawl_worker.crawl_all_ccd_models(
            ["ok1", "risk", "ok2"],
            concurrency=1,
            batch_size=3,
            keyword_result_callback=record,
            batch_id="test",
            started_at="",
        )
        return report, seen

    report, seen = asyncio.run(run())

    assert report.aborted is True
    assert report.abort_reason == "触发风控验证"
    assert report.success_count == 1
    assert report.fail_count == 1
    assert report.risk_detected_count == 1
    assert seen == [("ok1", True, False), ("risk", False, True)]
