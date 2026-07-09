from types import SimpleNamespace

from app.services.bargain import (
    card_status_uncertain_needs_confirm,
    ccd_invalid_bargain_reason,
    detect_bargains,
    filter_target_items,
    filter_target_items_with_reasons,
)
from app.services.xd_card_models import is_direct_xd_sd_dual_model
from app.services.bargain_detector import detect_global_bargains


def _item(item_id: str, title: str, price: float = 1.0, description: str = ""):
    return SimpleNamespace(
        item_id=item_id,
        title=title,
        description=description,
        price=price,
        sold=False,
        url=f"https://www.goofish.com/item?id={item_id}",
    )


def test_ccd_filter_removes_rental_consulting_and_accessory_listings():
    items = [
        _item("rental", "免押出租 佳能ixus130 ccd机皇 邮寄三天起租 续租15/天", 15),
        _item("consult", "ccd咨询辨真假贴！帮忙推荐ccd的型号 拍下后即可辨别真假", 1),
        _item("filter", "三星CCD数码相机 全新原装滤光片 低通滤镜 适用WB250F", 10),
        _item("camera", "佳能ixus130 CCD相机 功能正常 自用 配件齐全 带电池充电器", 1280),
    ]

    kept, filtered_out = filter_target_items_with_reasons(items, "ccd")

    assert [item.item_id for item in kept] == ["camera"]
    reasons = {entry["title"]: entry["reason"] for entry in filtered_out}
    assert reasons[items[0].title] == "低价引流/非实价"
    assert reasons[items[1].title] == "低价引流/非实价"
    assert reasons[items[2].title] == "配件/耗材/资料"


def test_ccd_sample_filter_keeps_whole_camera_with_gift_accessories():
    items = [
        _item("camera", "佳能A3300is CCD相机 功能正常 自用 送滤镜 带电池充电器", 520),
    ]

    plain_kept = filter_target_items(items, "ccd")
    kept, filtered_out = filter_target_items_with_reasons(items, "ccd")

    assert [item.item_id for item in plain_kept] == ["camera"]
    assert [item.item_id for item in kept] == ["camera"]
    assert filtered_out == []


def test_ccd_sample_filter_keeps_f30_whole_camera_descriptions():
    items = [
        _item(
            "sensor-buttons",
            "富士FinePix F30 香槟色CCD卡片机 功能正常 无拆修 镜头伸缩顺畅 "
            "屏幕显示正常 按键灵敏 CCD传感器 630万像素 3倍光学变焦 "
            "配件：电池、充电器 包邮",
            468,
        ),
        _item(
            "no-mold",
            "富士F30 带521Mb原厂xd卡 富士CCD 整机9新 功能全好 "
            "镜头无霉无划痕 屏幕显示清晰 免费配件 全新电池 万能充 XD卡",
            500,
        ),
        _item(
            "recommend-tag",
            "富士FinePix F30 日版 实价可直拍 功能一切正常 CCD机型 "
            "有问题可以退换 没有问题不退不换 关联：小红书推荐ccd",
            400,
        ),
        _item(
            "film-filter-mode",
            "富士F30 相机 CCD银色 功能正常 出片偏日系 胶卷滤镜 复古出片模式 "
            "配件：内存卡 电池 售后支持收到货有问题可退",
            358,
        ),
        _item(
            "repair-service",
            "富士F30 CCD相机复古数码相机 功能完好 配件：电池 充电器 "
            "本店下单粉丝享一年维修免手工费 只收小额零件费用",
            468,
        ),
        _item(
            "optional-seat-charger",
            "富士f30 成色如图 功能正常 到货清单默认裸机 15元配件含电池 "
            "万能充升级全新座充+10元 若有问题48小时内可以退换",
            428,
        ),
    ]

    kept, filtered_out = filter_target_items_with_reasons(items, "富士f30")

    assert [item.item_id for item in kept] == [
        "sensor-buttons",
        "no-mold",
        "recommend-tag",
        "film-filter-mode",
        "repair-service",
        "optional-seat-charger",
    ]
    assert filtered_out == []


def test_ccd_sample_filter_rejects_short_model_lens_collision():
    items = [
        _item("lens", "索尼FE 16-25mm F2.8 G镜头 E卡口 全画幅 成色几乎全新", 5800),
        _item("camera", "奥林巴斯FE-25 1000万像素相机 3倍光学变焦 功能正常", 299),
    ]

    kept, filtered_out = filter_target_items_with_reasons(items, "奥林巴斯fe25")

    assert [item.item_id for item in kept] == ["camera"]
    assert [entry["title"] for entry in filtered_out] == [items[0].title]


def test_ccd_sample_filter_rejects_nearby_model_and_recycling_ads():
    items = [
        _item("recycle", "全国高价上门回收相机镜头 尼康 佳能 索尼 在线报价 当面打款", 8888),
        _item("d7100", "尼康D7100单反套机 18-140mm镜头 功能正常", 2550),
        _item("s7100", "尼康COOLPIX S7100数码相机 功能正常 屏幕显示正常", 430),
    ]

    kept, filtered_out = filter_target_items_with_reasons(items, "尼康s7100")

    assert [item.item_id for item in kept] == ["s7100"]
    reasons = {entry["title"]: entry["reason"] for entry in filtered_out}
    assert reasons[items[0].title] == "服务/回收广告"
    assert items[1].title in reasons


def test_ccd_sample_filter_keeps_known_model_suffixes():
    items = [
        _item("a2400is", "佳能A2400IS数码相机 樱花粉 功能正常 配电池内存卡", 838),
        _item("a7", "索尼A7M4微单相机 全画幅 功能正常", 9999),
    ]

    kept = filter_target_items(items, "佳能a2400")

    assert [item.item_id for item in kept] == ["a2400is"]


def test_ccd_sample_filter_rejects_real_utf8_accessory_terms():
    items = [
        _item("adapter", "XD卡托1G 适用奥林巴斯FE20 FE25 FE250 U1010 数码相机", 23.8),
        _item("camera", "奥林巴斯FE25数码相机 功能正常 配电池和内存卡", 299),
    ]

    kept, filtered_out = filter_target_items_with_reasons(items, "奥林巴斯fe25")

    assert [item.item_id for item in kept] == ["camera"]
    assert filtered_out[0]["reason"] == "配件/耗材/资料"


def test_ccd_sample_filter_rejects_soft_accessory_compatibility_lists():
    items = [
        _item("battery-pack", "奥林巴斯U750 1050 FE5020 150 160 F E190 290 FE280 230 240 250 320 fe300电池充电器 全新包邮，", 16),
        _item("li42b", "奥林巴斯u1060 u5010 u7000 u7010 FE 5020 5030 5050 5500 照相机Li-42B电池充电器", 17),
        _item("cable", "奥林巴斯相机数据线U1040 U1050 U1060 U10 10 U1020 U1030", 25),
        _item("camera", "奥林巴斯U1060数码相机 功能正常 闪光灯正常 配电池充电器", 320),
    ]

    kept, filtered_out = filter_target_items_with_reasons(items, "奥林巴斯u1060")

    assert [item.item_id for item in kept] == ["camera"]
    assert [entry["reason"] for entry in filtered_out] == [
        "配件/耗材/资料",
        "配件/耗材/资料",
        "配件/耗材/资料",
    ]


def test_ccd_sample_filter_keeps_short_model_token_exact():
    items = [
        _item("sony-t2", "靓机 索尼T2数码相机CCD 成色好 功能全部正常 闪光灯触屏都可以", 350),
        _item("sony-t200", "索尼T200数码相机CCD 成色好 功能正常", 980),
        _item("sony-battery", "索尼NP-BD1电池 适用DSC-TX1/T2/T70/T200/T300/T700相机", 18),
    ]

    kept, filtered_out = filter_target_items_with_reasons(items, "索尼t2")

    assert [item.item_id for item in kept] == ["sony-t2"]
    assert [entry["title"] for entry in filtered_out] == [items[1].title, items[2].title]


def test_ccd_sample_filter_rejects_standalone_xd_card_but_keeps_camera_bundle():
    items = [
        _item("card", "奥林巴斯原装64MB xD卡，全新未用，适合老款奥林巴斯、富士CCD相机", 50),
        _item("brand-list-card", "【可直拍】奥林巴斯&富士&东芝xd卡 全部功能正常 看看店铺有没有喜欢的相机", 85),
        _item("mu-camera", "奥林巴斯μ1020，送2g xd卡，可直拍，拍人也很好看", 380),
        _item("camera", "奥林巴斯u1050sw 银色 CCD相机 功能正常 送原装xd卡1g", 320),
    ]

    kept, filtered_out = filter_target_items_with_reasons(items, "奥林巴斯u1050")

    assert [item.item_id for item in kept] == ["mu-camera", "camera"]
    assert [entry["reason"] for entry in filtered_out] == ["配件/耗材/资料", "配件/耗材/资料"]


def test_ccd_sample_filter_removes_blind_box_low_price_bait():
    bait = _item(
        "bait",
        "佳能A3300is，家里太多了 用不到了 【1.88捡漏】全新未拆 抽抽抽 可许愿 先到先得 没抽到可退 #潮流盲盒",
        1.88,
    )
    camera = _item("camera", "佳能A3300is CCD相机 功能正常 自用", 520)

    plain_kept = filter_target_items([bait, camera], "ccd")
    kept, filtered_out = filter_target_items_with_reasons([bait, camera], "ccd")

    assert [item.item_id for item in plain_kept] == ["camera"]
    assert [item.item_id for item in kept] == ["camera"]
    assert filtered_out[0]["reason"] == "低价引流/盲盒抽奖"


def test_detect_bargains_uses_ccd_bargain_filter():
    items = [
        _item("rental", "【免押租】南昌个人自用佳能ixus130ccd 1天25", 25),
        _item("consult", "回答关于ccd的任何问题 有问题直接拍链接再问", 1.01),
        _item("camera", "佳能ixus130 CCD相机 功能正常 配件齐全", 1280),
    ]

    bargains = detect_bargains(items, base_price=2280, query_keyword="ccd", threshold=80)

    assert [bargain.item_id for bargain in bargains] == ["camera"]


def test_detect_bargains_rejects_blind_box_low_price_bait():
    bait = _item(
        "bait",
        "佳能A3300is，家里太多了 用不到了 【1.88捡漏】全新未拆 抽抽抽 可许愿 先到先得 没抽到可退 #潮流盲盒",
        1.88,
    )
    camera = _item("camera", "佳能A3300is CCD相机 功能正常 自用", 520)

    assert ccd_invalid_bargain_reason(bait) == "低价引流/盲盒抽奖"

    bargains = detect_bargains([bait, camera], base_price=888, query_keyword="ccd", threshold=80)

    assert [bargain.item_id for bargain in bargains] == ["camera"]


def test_non_xd_sony_storage_card_text_does_not_add_xd_bonus():
    sony = _item(
        "sony-h9",
        "索尼H9 CCD数码相机 卡片机 复古相机 810万像素 15X倍光学变焦 送1G卡 标价是实价",
        318,
    )

    bargains = detect_bargains([sony], base_price=350, query_keyword="索尼h9", threshold=80)

    assert bargains == []


def test_non_xd_canon_bare_model_collision_does_not_add_xd_bonus():
    canon = _item(
        "canon-a700",
        "佳能A700，6倍光学变焦，机器性能完好，带2g卡没有其它附件",
        620,
    )

    bargains = detect_bargains([canon], base_price=588, query_keyword="佳能a700", threshold=80)

    assert bargains == []


def test_direct_dual_generic_storage_card_text_needs_confirmation_without_xd_bonus():
    fuji = _item(
        "fuji-f200",
        "富士F200EXR CCD数码相机 功能正常 送1G卡 标价是实价",
        430,
    )

    bargains = detect_bargains([fuji], base_price=500, query_keyword="富士f200exr", threshold=60)

    assert len(bargains) == 1
    assert bargains[0].xd_card_size == ""
    assert bargains[0].xd_card_value == 0
    assert bargains[0].profit_estimate == 70
    assert bargains[0].card_status_uncertain_needs_confirm is True


def test_optional_xd_card_purchase_does_not_add_xd_bonus():
    olympus = _item(
        "olympus-sp550",
        "奥林巴斯sp550uz小长焦 功能正常 自备4节五号电池XD内存卡和读卡器（可选购XD卡256m 115元 1g 148元）",
        430,
    )

    bargains = detect_bargains([olympus], base_price=500, query_keyword="奥林巴斯sp550", threshold=80)

    assert bargains == []


def test_global_bargains_do_not_mark_non_xd_storage_card_as_xd():
    sony = _item(
        "sony-t300",
        "索尼T300 CCD数码相机 1010万像素 5X倍光学变焦 送1G卡 标价是实价",
        298,
    )
    sony.query_keyword = "索尼t300"
    canon = _item(
        "canon-a700",
        "佳能A700，6倍光学变焦，机器性能完好，带2g卡没有其它附件",
        620,
    )
    canon.query_keyword = "佳能a700"
    fuji = _item(
        "fuji-f200",
        "富士F200EXR CCD数码相机 功能正常 送1G卡 标价是实价",
        400,
    )
    fuji.query_keyword = "富士f200exr"

    records = detect_global_bargains(
        [sony, canon, fuji],
        {"索尼t300": 300, "佳能a700": 588, "富士f200exr": 500},
    )

    assert [record.item_id for record in records] == ["fuji-f200"]
    assert records[0].is_xd_card is False
    assert records[0].xd_card_size == ""
    assert records[0].card_status_uncertain_needs_confirm is True


def test_global_bargains_skip_standalone_xd_card_listing():
    card = _item(
        "xd-card",
        "奥林巴斯原装128MB xD卡，金属触点完好，适合老款奥林巴斯、富士CCD相机用",
        45,
    )
    card.query_keyword = "奥林巴斯μ1070"
    brand_list_card = _item(
        "brand-list-card",
        "【可直拍】奥林巴斯&富士&东芝xd卡 全部功能正常 看看店铺有没有喜欢的相机",
        85,
    )
    brand_list_card.query_keyword = "奥林巴斯μ1070"
    camera = _item(
        "camera",
        "奥林巴斯u1070 CCD相机 功能正常 送原装xd卡1g",
        320,
    )
    camera.query_keyword = "奥林巴斯μ1070"
    mu_camera = _item(
        "mu-camera",
        "奥林巴斯μ1020，送2g xd卡，可直拍，拍人也很好看",
        380,
    )
    mu_camera.query_keyword = "奥林巴斯μ1020"

    records = detect_global_bargains(
        [card, brand_list_card, camera, mu_camera],
        {"奥林巴斯μ1070": 450, "奥林巴斯μ1020": 435},
    )

    assert [record.item_id for record in records] == ["camera", "mu-camera"]
    assert all(record.is_xd_card for record in records)


def test_existing_bargain_alerts_can_be_hidden_without_deleting_rows():
    dirty_alert = _item("old", "三亚免押租佳能IXUS95is 成年芝麻分600+走平台", 17)
    clean_alert = _item("ok", "佳能ixus130 CCD相机 功能正常", 1200)

    assert ccd_invalid_bargain_reason(dirty_alert) == "低价引流/非实价"
    assert ccd_invalid_bargain_reason(clean_alert) == ""


def test_direct_xd_sd_dual_model_detection_is_gated_by_xd_model():
    assert is_direct_xd_sd_dual_model("富士 F200EXR")
    assert is_direct_xd_sd_dual_model("FinePix Z10fd")
    assert not is_direct_xd_sd_dual_model("富士 A700")
    assert not is_direct_xd_sd_dual_model("佳能 A700")


def test_direct_dual_generic_card_gets_confirmation_flag_without_xd_bonus():
    item = _item("f200-generic", "富士 F200EXR CCD相机 功能正常 带1G内存卡", 300)

    bargains = detect_bargains([item], base_price=500, query_keyword="富士 F200EXR", threshold=80)

    assert len(bargains) == 1
    assert bargains[0].xd_card_value == 0
    assert bargains[0].profit_estimate == 200
    assert bargains[0].card_status_uncertain_needs_confirm is True


def test_direct_dual_missing_card_status_gets_confirmation_flag():
    item = _item("f200-unknown", "富士 F200EXR CCD相机 功能正常", 300)

    assert card_status_uncertain_needs_confirm(item, "富士 F200EXR") is True


def test_direct_dual_explicit_no_card_or_sd_does_not_get_confirmation_flag():
    no_card = _item("f200-no-card", "富士 F200EXR CCD相机 功能正常 不带卡", 300)
    sd_card = _item("f200-sd", "富士 F200EXR CCD相机 功能正常 带1G SD卡", 300)

    assert card_status_uncertain_needs_confirm(no_card, "富士 F200EXR") is False
    assert card_status_uncertain_needs_confirm(sd_card, "富士 F200EXR") is False


def test_direct_dual_explicit_xd_card_adds_bonus_without_confirmation_flag():
    item = _item("f200-xd", "富士 F200EXR CCD相机 功能正常 带1G XD卡", 300)

    bargains = detect_bargains([item], base_price=500, query_keyword="富士 F200EXR", threshold=80)

    assert len(bargains) == 1
    assert bargains[0].xd_card_size == "1g"
    assert bargains[0].xd_card_value == 148
    assert bargains[0].profit_estimate == 348
    assert bargains[0].card_status_uncertain_needs_confirm is False


def test_xd_only_generic_card_still_counts_as_xd_without_confirmation_flag():
    item = _item("a700-xd", "富士 A700 CCD相机 功能正常 带1G卡", 300)

    bargains = detect_bargains([item], base_price=500, query_keyword="富士 A700", threshold=80)

    assert len(bargains) == 1
    assert bargains[0].xd_card_value == 148
    assert bargains[0].card_status_uncertain_needs_confirm is False
