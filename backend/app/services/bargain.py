from typing import List, Literal
from dataclasses import dataclass
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


@dataclass
class BargainItem:
    item_id: str
    title: str
    price: float
    estimated_price: float
    profit_estimate: float
    url: str


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
        # 允许前缀匹配：j150 匹配 j150w，j150w 匹配 j150
        # 只要任意一对 token 互为前缀关系就认为匹配
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
        kept.append(item)
    return kept, filtered_out


def _is_model_mismatch(query_keyword: str, item_title: str, category: Literal["phone", "ccd", "other"]) -> bool:
    if category == "phone":
        return _phone_model_mismatch(query_keyword, item_title)
    if category == "ccd":
        return _ccd_model_mismatch(query_keyword, item_title)
    return False


def detect_bargains(
    items: list,
    base_price: float,
    query_keyword: str = "",
    threshold: float = None,
) -> List[BargainItem]:
    """
    捡漏检测：当前在售商品价格比基准估价低 threshold 元以上则标记。
    threshold 默认读取配置（120元）。

    按查询词自动识别类目（phone/ccd/other），并应用对应风险词和型号一致性过滤。
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

        profit = base_price - item.price
        if profit >= threshold:
            bargains.append(BargainItem(
                item_id=item.item_id,
                title=item.title,
                price=item.price,
                estimated_price=base_price,
                profit_estimate=round(profit, 2),
                url=item.url,
            ))

    bargains.sort(key=lambda x: x.profit_estimate, reverse=True)
    return bargains
