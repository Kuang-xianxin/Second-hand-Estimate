from typing import List, Literal
from dataclasses import dataclass, field
import re

from app.config import settings


PHONE_HINT_KEYWORDS = [
    "iphone", "苹果", "华为", "小米", "vivo", "oppo", "三星", "手机", "pro max", "ultra", "fold",
]

CCD_HINT_KEYWORDS = [
    "ccd", "卡片机", "数码相机", "相机", "镜头", "佳能", "尼康", "富士", "索尼", "松下", "奥林巴斯", "理光",
]

COMMON_RISK_KEYWORDS = [
    "不包好坏", "当配件", "尸体", "仅机身", "无测试", "不退不换",
]

PHONE_RISK_KEYWORDS = [
    "重摔", "摔过", "坏屏", "屏坏", "漏液", "不开机", "主板", "故障", "维修",
    "拆修", "换屏", "国产屏", "零件机", "配件机", "有锁", "id锁", "ic锁",
    "卡贴", "内置卡贴", "背裂", "裂痕", "边框磕碰", "屏幕划痕", "明显划痕",
]

CCD_RISK_KEYWORDS = [
    "进灰", "霉", "霉斑", "镜片划伤", "镜头划伤", "快门故障", "快门异常",
    "对焦故障", "对焦异常", "不开机", "死机", "电池仓腐蚀", "维修", "拆修",
    "漏光", "暗角严重", "传感器坏点", "屏幕坏", "闪光灯坏", "仅机身无配件",
]

CCD_ACCESSORY_KEYWORDS = [
    "说明书", "电子版", "pdf", "外屏", "内屏", "液晶屏", "显示屏", "屏幕总成",
    "电池", "充电器", "充电线", "数据线", "镜头盖", "镜头组", "转接环", "滤镜", "遮光罩",
    "读卡器", "内存卡", "存储卡", "相机包", "保护套", "贴膜", "背带", "三脚架", "快装板", "热靴",
    "拆机", "零件", "主板", "排线",
]

CCD_BRANDS = {
    "canon": ["canon", "佳能", "ixus", "powershot", "ixy", "kiss"],
    "nikon": ["nikon", "尼康", "coolpix"],
    "sony": ["sony", "索尼", "cybershot", "dsc"],
    "fujifilm": ["fujifilm", "fuji", "富士", "finepix"],
    "olympus": ["olympus", "奥林巴斯", "mju", "stylus"],
    "panasonic": ["panasonic", "松下", "lumix"],
    "ricoh": ["ricoh", "理光"],
    "casio": ["casio", "卡西欧", "exilim"],
}

# XD 卡价格表（富士/奥林巴斯老相机常见配卡）
XD_CARD_PRICES = {
    "16mb": 50,
    "32mb": 60,
    "64mb": 70,
    "128mb": 108,
    "256mb": 120,
    "512mb": 134,
    "512mb高速": 139,
    "1g": 148,
    "1g高速": 160,
    "2g": 162,
    "2g高速": 175,
}

XD_CARD_SIZE_PATTERNS = [
    (r"(\d+)\s*g(?:高速)?", lambda m: f"{m.group(1)}g"),
    (r"(\d+)\s*gb", lambda m: f"{m.group(1)}g"),
    (r"(\d+)\s*mb(?:高速)?", lambda m: f"{m.group(1)}mb"),
    (r"(\d{2,4})\s*mb", lambda m: f"{m.group(1)}mb"),
]

# 检测"相机自备XD卡"的文本模式——说明这是XD卡机型且卖家单独说明要另购
XD_SELF_PROVIDE_PATTERNS = [
    r"xd卡自备", r"卡自备", r"不带卡", r"不含卡", r"无卡",
    r"xd卡买家自备", r"需要自备", r"需自备", r"xd卡另购",
    r"xd卡加购", r"xd卡另加", r"另购xd卡", r"需加购xd卡",
    r"xd卡需另买", r"卡需自备", r"xd卡买家",
]

# 检测"相机捆绑XD卡销售"的文本模式
XD_BUNDLE_PATTERNS = [
    r"xd卡", r"富士卡", r"奥林巴斯卡", r"原装卡",
    r"带\s*\d+\s*[gm]\s*卡", r"带\d+[gm]卡",
    r"\d+[gm]卡送", r"送\d+[gm]卡", r"卡送",
    r"带\s*xd卡", r"配有\s*xd",
]

# 检测XD卡机型标志（机身/描述中提及XD卡说明该机型用XD卡）
XD_MODEL_SIGNAL_PATTERNS = [
    # 高度宽松：只要标题/描述中出现过"xd卡"就高度怀疑该机型使用XD卡
    r"xd卡",
    # 自备类：卖家会说"自备XD卡"或"XD卡另购"，直接说明是XD卡机型
    r"需自备xd卡", r"自备\s*xd卡", r"xd卡需另购",
    r"xd卡买家自备", r"xd卡需自备",
    # 捆绑类：标题出现XD卡说明是XD卡机型
    r"富士\s*xd卡", r"富士\s+\d+[gm]\s*卡", r"富士\d+[gm]卡",
    r"奥林巴斯\s*xd卡", r"奥林巴斯\s+\d+[gm]\s*卡",
    r"富士finepix", r"fuji\s*finepix", r"finepix",
    r"olympus\s*mju", r"olympus\s*stylus",
    r"olympus\s*(fe|sz|sp|tg|xz|ep)",
    r"富士\s*(jx|z|a|avens?|xp)\d",
    r"lumix\s*(fh|zs)\d",
    r"xd卡槽", r"xD卡槽", r"xd-p", r"xD-P",
    r"储存介质\s*[为:]?\s*xd", r"储存介质\s*[为:]?\s*xD",
    r"存储介质\s*[为:]?\s*xd",
]


def _infer_category(keyword: str) -> Literal["phone", "ccd", "other"]:
    text = (keyword or "").lower()
    if any(kw in text for kw in CCD_HINT_KEYWORDS):
        return "ccd"
    if any(kw in text for kw in PHONE_HINT_KEYWORDS):
        return "phone"
    return "other"


def _item_text(item) -> str:
    return f"{getattr(item, 'title', '')} {getattr(item, 'description', '')}".lower()


def _extract_iphone_generation(text: str) -> str:
    m = re.search(r"iphone\s*([0-9]{2})", text, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"苹果\s*([0-9]{2})", text)
    if m:
        return m.group(1)
    return ""


def _phone_model_mismatch(keyword: str, title: str) -> bool:
    kw = (keyword or "").lower()
    t = (title or "").lower()

    kw_gen = _extract_iphone_generation(kw)
    item_gen = _extract_iphone_generation(t)
    if kw_gen and item_gen and kw_gen != item_gen:
        return True

    if "pro max" in kw and "pro max" not in t:
        return True
    if "pro max" not in kw and "pro max" in t and "pro" in kw:
        return True
    if "pro" in kw and "pro" not in t:
        return True
    if "plus" in kw and "plus" not in t:
        return True
    return False


def _extract_ccd_brand(text: str) -> str:
    low = (text or "").lower()
    for brand, aliases in CCD_BRANDS.items():
        if any(alias in low for alias in aliases):
            return brand
    return ""


def _extract_model_tokens(text: str) -> set[str]:
    low = (text or "").lower()
    tokens = set(re.findall(r"[a-z]{1,5}[- ]?\d{2,4}[a-z]?", low))
    clean = {t.replace(" ", "").replace("-", "") for t in tokens}
    return {t for t in clean if len(t) >= 3}


def _ccd_model_mismatch(keyword: str, title: str) -> bool:
    kw_brand = _extract_ccd_brand(keyword)
    item_brand = _extract_ccd_brand(title)
    if kw_brand and item_brand and kw_brand != item_brand:
        return True

    kw_tokens = _extract_model_tokens(keyword)
    item_tokens = _extract_model_tokens(title)
    if kw_tokens and item_tokens:
        def _tokens_overlap(a, b):
            for ta in a:
                for tb in b:
                    if ta == tb or ta.startswith(tb) or tb.startswith(ta):
                        return True
            return False
        if not _tokens_overlap(kw_tokens, item_tokens):
            return True

    return False


def _is_risky_by_category(item, category: Literal["phone", "ccd", "other"]) -> bool:
    text = _item_text(item)
    category_risk = []
    if category == "phone":
        category_risk = PHONE_RISK_KEYWORDS
    elif category == "ccd":
        category_risk = CCD_RISK_KEYWORDS + CCD_ACCESSORY_KEYWORDS

    risk_keywords = COMMON_RISK_KEYWORDS + category_risk
    return any(kw.lower() in text for kw in risk_keywords)


def filter_target_items(items: list, query_keyword: str) -> list:
    """仅按型号一致性过滤样本（估价主流程），配件/故障判断交给LLM"""
    kept, _ = filter_target_items_with_reasons(items, query_keyword)
    return kept


def filter_target_items_with_reasons(items: list, query_keyword: str):
    """返回 (kept, filtered_out)，filtered_out 是被排除条目的原因列表"""
    category = _infer_category(query_keyword)
    kept = []
    filtered_out = []
    for item in items:
        if _is_model_mismatch(query_keyword, item.title, category):
            filtered_out.append({
                "title": item.title,
                "price": item.price,
                "reason": "型号不符",
            })
            continue
        # 配件关键词过滤：电池、充电器、镜头盖、USB盖、胶条等配件直接排除
        if category == "ccd":
            title_lower = item.title.lower()
            accessory_hit = next((kw for kw in CCD_ACCESSORY_KEYWORDS if kw.lower() in title_lower), None)
            if accessory_hit:
                filtered_out.append({
                    "title": item.title,
                    "price": item.price,
                    "reason": f"配件（{accessory_hit}）非整机",
                })
                continue
        kept.append(item)
    return kept, filtered_out


def _is_model_mismatch(query_keyword: str, item_title: str, category: Literal["phone", "ccd", "other"]) -> bool:
    if category == "phone":
        return _phone_model_mismatch(query_keyword, item_title)
    if category == "ccd":
        return _ccd_model_mismatch(query_keyword, item_title)
    return False


# ---------------------------------------------------------------------------
# XD 卡相关逻辑
# ---------------------------------------------------------------------------

def detect_xd_card_model_from_items(items: list) -> bool:
    """
    爬取完成后，通过分析商品标题/描述判断相机是否使用 XD 卡。

    判断逻辑：扫描前5条商品，只要有一条明确提到"自备xd卡"即认为是XD卡机型。
    """
    for item in items[:5]:
        text = _item_text(item)
        for pat in XD_MODEL_SIGNAL_PATTERNS:
            if re.search(pat, text, flags=re.IGNORECASE):
                return True
    return False


def _get_xd_card_value(size: str) -> float:
    """根据卡容量返回卡的价格表估值，未知容量返回 0。"""
    key = size.lower().strip()
    return XD_CARD_PRICES.get(key, 0.0)


def _extract_xd_card_from_text(text: str) -> str:
    """
    从文字中提取 XD 卡容量。
    返回容量字符串如 "256mb"、"1g高速"，找不到返回 ""。
    """
    for pat in XD_SELF_PROVIDE_PATTERNS:
        if re.search(pat, text):
            return ""

    has_bundle = any(re.search(p, text) for p in XD_BUNDLE_PATTERNS)
    if not has_bundle:
        return ""

    for pattern, extractor in XD_CARD_SIZE_PATTERNS:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            size = extractor(m)
            start = max(0, m.start() - 5)
            end = min(len(text), m.end() + 5)
            nearby = text[start:end]
            is_high_speed = "高速" in nearby or "hs" in nearby.lower()
            key = size if not is_high_speed else f"{size}高速"
            if key in XD_CARD_PRICES:
                return key
            if size in XD_CARD_PRICES:
                return size
    return ""


def _is_xd_bundle_from_text(item, query_keyword: str) -> tuple[bool, str]:
    """
    检测单个商品是否捆绑了 XD 卡。
    返回 (is_bundle, card_size)
    """
    text = _item_text(item)
    card_size = _extract_xd_card_from_text(text)
    return bool(card_size), card_size


@dataclass
class XDCardBundleInfo:
    """单个商品的XD卡捆绑信息"""
    item_id: str
    card_size: str           # "256mb", "1g高速" 等
    card_value: float         # 对应价格表估值
    price: float             # 原始总价
    camera_only_price: float # 剔除卡值后的纯相机价格


def strip_xd_card_prices(items: list) -> tuple[list, list[XDCardBundleInfo]]:
    """
    对所有商品进行XD卡文字检测，返回两组数据：

    1. camera_only_items：所有不含卡/自备卡的纯相机商品（price保持原价不变）
       这些商品参与算法估价，避免带卡捆绑商品虚高基准价
    2. bundle_infos：检测到捆绑XD卡的商品详情列表，供后续判断捡漏利润叠加

    注意：此函数仅做文字检测（快速），不调用视觉模型。
    图片检测由调用方在有视觉模型时单独做，合并到 bundle_infos 中。
    """
    bundle_infos: list[XDCardBundleInfo] = []
    # 含卡商品的 item_id 集合，用于在算法估价时排除这些商品
    xd_bundle_ids: set = set()

    for item in items:
        is_bundle, card_size = _is_xd_bundle_from_text(item, "")
        if is_bundle and card_size:
            card_val = _get_xd_card_value(card_size)
            raw_price = float(item.price)
            xd_bundle_ids.add(item.item_id)
            bundle_infos.append(XDCardBundleInfo(
                item_id=item.item_id,
                card_size=card_size,
                card_value=card_val,
                price=raw_price,
                camera_only_price=max(raw_price - card_val, raw_price * 0.7),
            ))

    # 构建纯相机商品列表（排除含卡捆绑商品），供算法估价使用
    camera_only_items = [item for item in items if item.item_id not in xd_bundle_ids]

    return camera_only_items, bundle_infos


def merge_xd_bundle_with_vision(
    text_bundles: list[XDCardBundleInfo],
    vision_results: dict,
) -> list[XDCardBundleInfo]:
    """
    将视觉检测结果与文字检测结果合并。

    规则：
    - 文字检测已有结果：保留（文字结果通常更准，因为来自卖家描述）
    - 文字未检测到但视觉检测���：追加
    - 两者都有但视觉置信度更高：按 vision_results 覆盖
    - 视觉置信度为 "low"：忽略视觉结果，保留文字结果

    vision_results: dict，key=item_id，value=dict 含 card_size/card_value/confidence
    """
    # 先按 item_id 建立文字检测字典
    by_id: dict[str, XDCardBundleInfo] = {b.item_id: b for b in text_bundles}

    for item_id, vr in vision_results.items():
        conf = str(vr.get("confidence", "low")).lower()
        card_size = vr.get("card_size", "")
        card_val = _get_xd_card_value(card_size)

        if card_val <= 0:
            continue
        # 低置信忽略
        if conf == "low":
            continue

        if item_id not in by_id:
            # 文字没检测到，视觉检测到高/中置信 → 追加
            by_id[item_id] = XDCardBundleInfo(
                item_id=item_id,
                card_size=card_size,
                card_value=card_val,
                price=0.0,  # 视觉检测时原始价格由调用方补填
                camera_only_price=0.0,
            )
        else:
            # 两者都有，且视觉置信 high 时覆盖
            if conf == "high" and card_val > by_id[item_id].card_value:
                by_id[item_id] = XDCardBundleInfo(
                    item_id=item_id,
                    card_size=card_size,
                    card_value=card_val,
                    price=by_id[item_id].price,
                    camera_only_price=max(by_id[item_id].price - card_val, by_id[item_id].price * 0.7),
                )

    return list(by_id.values())


@dataclass
class BargainItem:
    item_id: str
    title: str
    price: float
    estimated_price: float
    profit_estimate: float
    url: str
    xd_card_size: str = ""       # XD 卡容量，如 "256mb"、"1g高速"
    xd_card_value: float = 0.0   # XD 卡估值（按价格表）


def detect_bargains(
    items: list,
    base_price: float,
    query_keyword: str = "",
    threshold: float = None,
    xd_card_bonus: dict = None,
) -> List[BargainItem]:
    """
    捡漏检测：当前在售商品价格比基准估价低 threshold 元以上则标记。

    xd_card_bonus：可选 dict，key=item_id，value=(card_size, card_value)
    表示某些商品通过图片分析识别出了 XD 卡捆绑，返回 (容量文字, 卡估值)。
    """
    if threshold is None:
        threshold = settings.bargain_threshold

    category = _infer_category(query_keyword)

    bargains = []
    for item in items:
        if item.sold:
            continue
        if _is_risky_by_category(item, category):
            continue
        if _is_model_mismatch(query_keyword, item.title, category):
            continue

        is_bundle, card_size = _is_xd_bundle_from_text(item, query_keyword)
        card_value = _get_xd_card_value(card_size) if card_size else 0.0

        if xd_card_bonus and item.item_id in xd_card_bonus:
            bonus_size, bonus_value = xd_card_bonus[item.item_id]
            if bonus_value > card_value:
                card_size = bonus_size
                card_value = bonus_value
                is_bundle = True

        profit = base_price - item.price

        if category == "ccd" and card_value > 0:
            total_profit = profit + card_value
        else:
            total_profit = profit

        if total_profit >= threshold:
            bargains.append(BargainItem(
                item_id=item.item_id,
                title=item.title,
                price=item.price,
                estimated_price=base_price,
                profit_estimate=round(total_profit, 2),
                url=item.url,
                xd_card_size=card_size,
                xd_card_value=round(card_value, 2),
            ))

    bargains.sort(key=lambda x: x.profit_estimate, reverse=True)
    return bargains
