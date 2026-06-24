from types import SimpleNamespace

from app.services.bargain import (
    ccd_invalid_bargain_reason,
    detect_bargains,
    filter_target_items,
    filter_target_items_with_reasons,
)


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


def test_existing_bargain_alerts_can_be_hidden_without_deleting_rows():
    dirty_alert = _item("old", "三亚免押租佳能IXUS95is 成年芝麻分600+走平台", 17)
    clean_alert = _item("ok", "佳能ixus130 CCD相机 功能正常", 1200)

    assert ccd_invalid_bargain_reason(dirty_alert) == "低价引流/非实价"
    assert ccd_invalid_bargain_reason(clean_alert) == ""
