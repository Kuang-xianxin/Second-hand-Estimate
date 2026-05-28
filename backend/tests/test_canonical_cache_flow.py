import sys
from pathlib import Path

backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))


class FakeBargainItem:
    item_id = "item-1"
    query_keyword = "索尼t700"
    keyword = "索尼t700"
    title = "索尼t700 CCD相机 功能正常"
    price = 100.0
    sold = False
    is_valid = True
    condition = "成色未标注"
    quality_score = 80.0
    url = "https://www.goofish.com/item?id=item-1"
    images = []


class FakeAccessoryItem:
    item_id = "item-2"
    query_keyword = "索尼t700"
    keyword = "索尼t700"
    title = "米家T700电动牙刷充电底座 原装正品"
    price = 25.0
    sold = False
    is_valid = True
    condition = "成色未标注"
    quality_score = 50.0
    url = "https://www.goofish.com/item?id=item-2"
    images = []


def test_cache_lookup_keys_include_tier_canonical():
    from app.api.cache_api import _cache_lookup_keys

    keys = _cache_lookup_keys("索尼T700")
    assert "sony-t700" in keys


def test_global_bargain_detector_uses_tier_canonical_price():
    from app.services.bargain_detector import detect_global_bargains

    records = detect_global_bargains([FakeBargainItem()], {"sony-t700": 500.0})
    assert len(records) == 1
    assert records[0].base_price == 500.0


def test_cache_pricing_uses_stream_filtering_before_price():
    from app.services.cache_updater import compute_price_for_keyword

    result = compute_price_for_keyword("sony-t700", [FakeBargainItem(), FakeAccessoryItem()])

    assert result["sample_count"] == 1
    assert result["base_price"] == 100.0


def test_global_bargain_display_rejects_phone_keywords():
    from app.api.cache_api import _is_global_bargain_displayable

    class PhoneGlobalBargain:
        item_id = "phone-1"
        keyword = "iphone"
        title = "iphonex 相机等所有功能正常"
        current_price = 585.0
        condition = "成色未标注"
        quality_score = 50.0
        url = ""
        image_url = ""

    assert _is_global_bargain_displayable(PhoneGlobalBargain()) is False


def test_global_bargain_display_rejects_camera_utility_titles():
    from app.api.cache_api import _is_global_bargain_displayable

    class UtilityGlobalBargain:
        item_id = "utility-1"
        keyword = "?? T 700"
        title = "Eosmsg 4.5 佳能相机 测试相机快门次数"
        current_price = 1.0
        condition = "成色未标注"
        quality_score = 50.0
        url = ""
        image_url = ""

    assert _is_global_bargain_displayable(UtilityGlobalBargain()) is False
