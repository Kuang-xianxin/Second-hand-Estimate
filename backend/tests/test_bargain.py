"""
Tests for bargain detection logic.
"""
import pytest
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List
from unittest.mock import AsyncMock, MagicMock

backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))


@dataclass
class MockBargainItem:
    item_id: str
    title: str
    price: float
    url: str = ""
    estimated_price: float = 0.0
    profit_estimate: float = 0.0
    xd_card_size: Optional[str] = None
    xd_card_value: float = 0.0


class TestBargainDetection:
    def test_bargain_profit_calculation(self):
        base_price = 500.0
        item_price = 300.0
        profit = base_price - item_price
        assert profit == 200.0
        assert profit > 0

    def test_bargain_threshold(self):
        from app.config import settings
        threshold = settings.bargain_threshold
        assert threshold > 0

    def test_bargain_above_threshold(self):
        base_price = 500.0
        threshold = 120.0
        item_price = 350.0
        profit = base_price - item_price
        assert profit > threshold

    def test_not_bargain_below_threshold(self):
        base_price = 500.0
        threshold = 120.0
        item_price = 400.0
        profit = base_price - item_price
        assert profit < threshold

    def test_xd_card_bonus(self):
        xd_card_values = {
            "16mb": 50,
            "32mb": 60,
            "64mb": 70,
            "128mb": 108,
            "256mb": 120,
            "512mb": 134,
            "1g": 148,
            "2g": 162,
        }
        for size, value in xd_card_values.items():
            assert value > 0
            assert size in ["16mb", "32mb", "64mb", "128mb", "256mb", "512mb", "1g", "2g"]


class TestXDCardDetection:
    def test_xd_card_models_list(self):
        from app.services.xd_card_models import ALL_XD_MODELS
        assert len(ALL_XD_MODELS) > 0

    def test_masd1_compatible_is_function(self):
        from app.services.xd_card_models import is_masd1_compatible_model
        assert callable(is_masd1_compatible_model)
        result = is_masd1_compatible_model("奥林巴斯 mu 1030sw")
        assert isinstance(result, tuple)
        assert len(result) == 2


@dataclass
class MockCcdItem:
    item_id: str
    title: str
    price: float
    description: str = ""
    sold: bool = False
    quality_score: float = 50.0
    quality_flags: List[str] = field(default_factory=list)
    url: str = ""


class TestCcdSampleFiltering:
    def test_sony_t700_filters_accessories_and_non_camera_items(self):
        from app.services.bargain import filter_target_items_with_reasons

        items = [
            MockCcdItem("1", "索尼T700 CCD相机 功能正常 成色很好", 520),
            MockCcdItem("2", "米家T700电动牙刷维修 不管啥故障都能修", 40),
            MockCcdItem("3", "众泰T700维修手册电路图资料 自动发货", 1),
            MockCcdItem("4", "适用 索尼DSC-T500 T700 T900 相机电池充电器", 12.8),
            MockCcdItem("5", "T700高强度碳板 穿越机机臂 一套4支", 21.98),
            MockCcdItem("6", "三洋VPC-T700相机 功能全好", 168),
        ]

        kept, filtered_out = filter_target_items_with_reasons(items, "索尼t700")

        assert [item.item_id for item in kept] == ["1"]
        reasons = {row["title"]: row["reason"] for row in filtered_out}
        assert "米家T700电动牙刷维修 不管啥故障都能修" in reasons
        assert "配件/耗材/资料" in reasons["适用 索尼DSC-T500 T700 T900 相机电池充电器"]

    def test_canon_ixus130_filters_battery_charger_and_usb_cover(self):
        from app.services.bargain import filter_target_items_with_reasons

        items = [
            MockCcdItem("1", "佳能IXUS130 CCD数码相机 正常拍照", 488),
            MockCcdItem("2", "佳能NB-4L电池 IXUS 230 220 120 130 100 全新包邮", 20),
            MockCcdItem("3", "适用于佳能IXUS 115 120 130 NB-4L电池+充电器", 12.8),
            MockCcdItem("4", "佳能IXUS130 IXY400F USB盖子 数据盖子 HDMI盖子", 30),
        ]

        kept, filtered_out = filter_target_items_with_reasons(items, "佳能ixus130")

        assert [item.item_id for item in kept] == ["1"]
        assert len(filtered_out) == 3

    def test_canonical_english_keyword_uses_ccd_filtering(self):
        from app.services.bargain import filter_target_items_with_reasons

        items = [
            MockCcdItem("1", "Sony T700 Cyber-shot CCD camera working", 520),
            MockCcdItem("2", "Mijia T700 toothbrush charging dock", 25),
        ]

        kept, filtered_out = filter_target_items_with_reasons(items, "sony-t700")

        assert [item.item_id for item in kept] == ["1"]
        assert len(filtered_out) == 1

    def test_filters_faulty_or_wrong_model_global_bargain_samples(self):
        from app.services.bargain import filter_target_items_with_reasons

        items = [
            MockCcdItem("1", "奥林巴斯u410/u30相机 严重进水，镜头坏了，当废品处理", 198),
            MockCcdItem("2", "出M07数码相机 白色 功能正常", 130),
            MockCcdItem("3", "Sony T700 Cyber-shot CCD相机 功能正常", 520),
            MockCcdItem("4", "佳能ccd ixus240hs 闪光灯有问题用不了 找人修一下", 788),
        ]

        kept, filtered_out = filter_target_items_with_reasons(items, "Sony T700")

        assert [item.item_id for item in kept] == ["3"]
        reasons = {row["title"]: row["reason"] for row in filtered_out}
        assert reasons["奥林巴斯u410/u30相机 严重进水，镜头坏了，当废品处理"] == "型号不符"
        assert reasons["出M07数码相机 白色 功能正常"] == "型号不符"
        assert reasons["佳能ccd ixus240hs 闪光灯有问题用不了 找人修一下"] == "型号不符"

    def test_filters_faulty_same_model_ccd_samples(self):
        from app.services.bargain import filter_target_items_with_reasons

        items = [
            MockCcdItem("1", "佳能ccd ixus240hs 闪光灯有问题用不了 找人修一下", 788),
            MockCcdItem("2", "佳能IXUS240HS CCD数码相机 功能正常", 980),
        ]

        kept, filtered_out = filter_target_items_with_reasons(items, "ixus 240hs")

        assert [item.item_id for item in kept] == ["2"]
        assert filtered_out[0]["reason"] == "故障/维修/零件机"

    def test_filters_camera_utility_software_samples(self):
        from app.services.bargain import filter_target_items_with_reasons

        items = [
            MockCcdItem("1", "Eosmsg 4.5 佳能相机 测试相机快门次数", 1),
            MockCcdItem("2", "佳能IXUS130 CCD相机 功能正常", 520),
        ]

        kept, filtered_out = filter_target_items_with_reasons(items, "佳能")

        assert [item.item_id for item in kept] == ["2"]
        assert filtered_out[0]["reason"] == "非相机商品"


@pytest.mark.asyncio
async def test_incremental_bargain_refresh_only_deletes_affected_model():
    from app.services.bargain_detector import replace_global_bargains_for_keywords

    session = AsyncMock()
    session.add = MagicMock()

    written = await replace_global_bargains_for_keywords(
        records=[],
        batch_id="sweep-test",
        keywords=["sony t700", "dsc-t700"],
        session=session,
    )

    assert written == 0
    session.execute.assert_awaited_once()
    statement = str(session.execute.await_args.args[0])
    assert "WHERE global_bargains.keyword IN" in statement
    session.commit.assert_awaited_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
