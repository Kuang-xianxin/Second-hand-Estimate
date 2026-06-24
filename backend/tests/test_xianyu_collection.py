from app.crawler.xianyu import XianyuCrawler


class _FakeSearchPage:
    def __init__(self, collected, wait_growth):
        self.collected = collected
        self.wait_growth = list(wait_growth)
        self.evaluate_calls = 0
        self.wait_calls = 0

    def evaluate(self, _script):
        self.evaluate_calls += 1

    def wait_for_timeout(self, _ms):
        self.wait_calls += 1
        if not self.wait_growth:
            return
        added = self.wait_growth.pop(0)
        start = len(self.collected)
        for idx in range(added):
            self.collected.append({"item_id": f"new-{start + idx}"})


def test_collect_more_search_results_waits_past_first_no_growth():
    collected = [{"item_id": f"old-{idx}"} for idx in range(30)]
    page = _FakeSearchPage(collected, wait_growth=[0, 10])

    stats = XianyuCrawler()._collect_more_search_results(page, collected, max_items=40)

    assert len(collected) == 40
    assert stats["attempts"] == 1
    assert stats["no_growth_streak"] == 0
    assert stats["reached_requested_count"] is True


def test_collect_more_search_results_stops_after_repeated_no_growth():
    collected = [{"item_id": f"old-{idx}"} for idx in range(30)]
    page = _FakeSearchPage(collected, wait_growth=[0, 0, 0])

    stats = XianyuCrawler()._collect_more_search_results(page, collected, max_items=40)

    # WHY: a single empty wait can be delayed lazy loading; repeated empty waits
    # mean the current page likely has no more useful search items.
    assert len(collected) == 30
    assert stats["attempts"] == 2
    assert stats["no_growth_streak"] == 2
    assert stats["reached_requested_count"] is False
