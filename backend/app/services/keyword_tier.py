"""
CCD 关键词分层与型号归并系统。

T0（热门 55 个）：每 5 分钟
T1（普通 ~200 个）：每 12 小时
T2（长尾 ~400+ 个）：每 3 天

从 ccd_keywords.py 导入全量 2003 关键词，自动分配层级。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict


class KeywordTier(str, Enum):
    T0_HOT = "t0"
    T1_WARM = "t1"
    T2_COLD = "t2"


@dataclass
class CanonicalModel:
    model_id: str
    display_name: str
    brand: str
    series: str
    keywords: List[str] = field(default_factory=list)
    tier: KeywordTier = KeywordTier.T2_COLD


# ============================================================
# T0 热门型号（55 个，市场交易最活跃的 CCD 型号）
# ============================================================
T0_CANONICAL_MODELS: List[CanonicalModel] = [
    # --- Canon IXUS ---
    CanonicalModel("canon-ixus-130", "Canon IXUS 130 / SD1400 IS", "canon", "IXUS", [
        "佳能ixus130", "canon ixus 130", "ixus130", "sd1400is",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-105", "Canon IXUS 105 / SD1300 IS", "canon", "IXUS", [
        "佳能ixus105", "canon ixus 105", "sd1300is",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-95", "Canon IXUS 95 / SD1200 IS", "canon", "IXUS", [
        "佳能ixus95", "canon ixus 95", "ixus95is", "sd1200is",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-80", "Canon IXUS 80 / SD1100 IS", "canon", "IXUS", [
        "佳能ixus80", "canon ixus 80", "ixus80is", "sd1100is",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-70", "Canon IXUS 70 / SD1000", "canon", "IXUS", [
        "佳能ixus70", "canon ixus 70", "sd1000",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-210", "Canon IXUS 210 / SD3500 IS", "canon", "IXUS", [
        "佳能ixus210", "canon ixus 210", "ixus210", "sd3500is",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-300hs", "Canon IXUS 300 HS / SD4000 IS", "canon", "IXUS", [
        "佳能ixus300", "canon ixus 300", "ixus300hs", "sd4000is",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-220hs", "Canon IXUS 220 HS / ELPH 300 HS", "canon", "IXUS", [
        "佳能ixus220", "canon ixus 220", "ixus220hs", "elph300hs",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-115hs", "Canon IXUS 115 HS / ELPH 100 HS", "canon", "IXUS", [
        "佳能ixus115", "canon ixus 115", "ixus115hs", "elph100hs",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-110", "Canon IXUS 110 / SD960 IS", "canon", "IXUS", [
        "佳能ixus110", "canon ixus 110", "sd960is",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-90", "Canon IXUS 90 / SD790 IS", "canon", "IXUS", [
        "佳能ixus90", "canon ixus 90", "ixus90is", "sd790is",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-85", "Canon IXUS 85 / SD770 IS", "canon", "IXUS", [
        "佳能ixus85", "canon ixus 85", "ixus85is", "sd770is",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-860", "Canon IXUS 860 / SD870 IS", "canon", "IXUS", [
        "佳能ixus860", "canon ixus 860", "ixus860is", "sd870is",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-240hs", "Canon IXUS 240 HS / ELPH 320 HS", "canon", "IXUS", [
        "佳能ixus240", "canon ixus 240", "ixus240hs", "elph320hs",
    ], KeywordTier.T0_HOT),
    CanonicalModel("canon-ixus-1000hs", "Canon IXUS 1000 HS / SD4500 IS", "canon", "IXUS", [
        "佳能ixus1000", "canon ixus 1000", "ixus1000hs", "sd4500is",
    ], KeywordTier.T0_HOT),
    # --- Sony T/TX ---
    CanonicalModel("sony-t700", "Sony Cyber-shot DSC-T700", "sony", "Cyber-shot", [
        "索尼t700", "sony t700", "dsc-t700", "t700",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-t900", "Sony Cyber-shot DSC-T900", "sony", "Cyber-shot", [
        "索尼t900", "sony t900", "dsc-t900", "t900",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-t300", "Sony Cyber-shot DSC-T300", "sony", "Cyber-shot", [
        "索尼t300", "sony t300", "dsc-t300", "t300",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-t200", "Sony Cyber-shot DSC-T200", "sony", "Cyber-shot", [
        "索尼t200", "sony t200", "dsc-t200", "t200",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-t100", "Sony Cyber-shot DSC-T100", "sony", "Cyber-shot", [
        "索尼t100", "sony t100", "dsc-t100", "t100",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-t77", "Sony Cyber-shot DSC-T77", "sony", "Cyber-shot", [
        "索尼t77", "sony t77", "dsc-t77", "t77",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-t70", "Sony Cyber-shot DSC-T70", "sony", "Cyber-shot", [
        "索尼t70", "sony t70", "dsc-t70", "t70",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-t50", "Sony Cyber-shot DSC-T50", "sony", "Cyber-shot", [
        "索尼t50", "sony t50", "dsc-t50", "t50",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-t30", "Sony Cyber-shot DSC-T30", "sony", "Cyber-shot", [
        "索尼t30", "sony t30", "dsc-t30", "t30",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-t20", "Sony Cyber-shot DSC-T20", "sony", "Cyber-shot", [
        "索尼t20", "sony t20", "dsc-t20", "t20",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-t10", "Sony Cyber-shot DSC-T10", "sony", "Cyber-shot", [
        "索尼t10", "sony t10", "dsc-t10", "t10",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-t2", "Sony Cyber-shot DSC-T2", "sony", "Cyber-shot", [
        "索尼t2", "sony t2", "dsc-t2", "t2",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-tx7", "Sony Cyber-shot DSC-TX7", "sony", "Cyber-shot", [
        "索尼tx7", "sony tx7", "dsc-tx7", "tx7",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-tx9", "Sony Cyber-shot DSC-TX9", "sony", "Cyber-shot", [
        "索尼tx9", "sony tx9", "dsc-tx9", "tx9",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-tx10", "Sony Cyber-shot DSC-TX10", "sony", "Cyber-shot", [
        "索尼tx10", "sony tx10", "dsc-tx10", "tx10",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-tx20", "Sony Cyber-shot DSC-TX20", "sony", "Cyber-shot", [
        "索尼tx20", "sony tx20", "dsc-tx20", "tx20",
    ], KeywordTier.T0_HOT),
    # --- Sony W/WX ---
    CanonicalModel("sony-w800", "Sony Cyber-shot DSC-W800", "sony", "Cyber-shot", [
        "索尼w800", "sony w800", "dsc-w800", "w800",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-w830", "Sony Cyber-shot DSC-W830", "sony", "Cyber-shot", [
        "索尼w830", "sony w830", "dsc-w830", "w830",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-wx500", "Sony Cyber-shot DSC-WX500", "sony", "Cyber-shot", [
        "索尼wx500", "sony wx500", "dsc-wx500", "wx500",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-wx350", "Sony Cyber-shot DSC-WX350", "sony", "Cyber-shot", [
        "索尼wx350", "sony wx350", "dsc-wx350", "wx350",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-wx300", "Sony Cyber-shot DSC-WX300", "sony", "Cyber-shot", [
        "索尼wx300", "sony wx300", "dsc-wx300", "wx300",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-w300", "Sony Cyber-shot DSC-W300", "sony", "Cyber-shot", [
        "索尼w300", "sony w300", "dsc-w300", "w300",
    ], KeywordTier.T0_HOT),
    CanonicalModel("sony-w100", "Sony Cyber-shot DSC-W100", "sony", "Cyber-shot", [
        "索尼w100", "sony w100", "dsc-w100", "w100",
    ], KeywordTier.T0_HOT),
    # --- Nikon Coolpix S ---
    CanonicalModel("nikon-s7000", "Nikon Coolpix S7000", "nikon", "Coolpix", [
        "尼康s7000", "nikon s7000",
    ], KeywordTier.T0_HOT),
    CanonicalModel("nikon-s6900", "Nikon Coolpix S6900", "nikon", "Coolpix", [
        "尼康s6900", "nikon s6900",
    ], KeywordTier.T0_HOT),
    CanonicalModel("nikon-s6200", "Nikon Coolpix S6200", "nikon", "Coolpix", [
        "尼康s6200", "nikon s6200",
    ], KeywordTier.T0_HOT),
    CanonicalModel("nikon-s3100", "Nikon Coolpix S3100", "nikon", "Coolpix", [
        "尼康s3100", "nikon s3100",
    ], KeywordTier.T0_HOT),
    # --- Fujifilm FinePix ---
    CanonicalModel("fuji-f100fd", "Fujifilm FinePix F100fd", "fuji", "FinePix", [
        "富士f100", "fuji f100", "finepix f100fd", "f100fd",
    ], KeywordTier.T0_HOT),
    CanonicalModel("fuji-f200exr", "Fujifilm FinePix F200EXR", "fuji", "FinePix", [
        "富士f200", "fuji f200", "finepix f200exr", "f200exr",
    ], KeywordTier.T0_HOT),
    CanonicalModel("fuji-f30", "Fujifilm FinePix F30", "fuji", "FinePix", [
        "富士f30", "fuji f30", "finepix f30", "f30",
    ], KeywordTier.T0_HOT),
    CanonicalModel("fuji-f31fd", "Fujifilm FinePix F31fd", "fuji", "FinePix", [
        "富士f31", "fuji f31", "finepix f31fd", "f31fd",
    ], KeywordTier.T0_HOT),
    # --- Olympus mu ---
    CanonicalModel("olympus-mu300", "Olympus mu300", "olympus", "mu", [
        "奥林巴斯μ300", "olympus 300", "mu300",
    ], KeywordTier.T0_HOT),
    CanonicalModel("olympus-mu400", "Olympus mu400", "olympus", "mu", [
        "奥林巴斯μ400", "olympus 400", "mu400",
    ], KeywordTier.T0_HOT),
    CanonicalModel("olympus-mu1010", "Olympus mu1010", "olympus", "mu", [
        "奥林巴斯μ1010", "olympus 1010", "mu1010",
    ], KeywordTier.T0_HOT),
    # --- Panasonic Lumix FX ---
    CanonicalModel("panasonic-fx01", "Panasonic Lumix DMC-FX01", "panasonic", "Lumix", [
        "松下fx01", "panasonic fx01", "dmc-fx01",
    ], KeywordTier.T0_HOT),
    CanonicalModel("panasonic-fx9", "Panasonic Lumix DMC-FX9", "panasonic", "Lumix", [
        "松下fx9", "panasonic fx9", "dmc-fx9",
    ], KeywordTier.T0_HOT),
    CanonicalModel("panasonic-fx30", "Panasonic Lumix DMC-FX30", "panasonic", "Lumix", [
        "松下fx30", "panasonic fx30", "dmc-fx30",
    ], KeywordTier.T0_HOT),
    # --- Casio Exilim ---
    CanonicalModel("casio-z3", "Casio Exilim EX-Z3", "casio", "Exilim", [
        "卡西欧z3", "casio z3", "ex-z3",
    ], KeywordTier.T0_HOT),
    CanonicalModel("casio-z40", "Casio Exilim EX-Z40", "casio", "Exilim", [
        "卡西欧z40", "casio z40", "ex-z40",
    ], KeywordTier.T0_HOT),
    # --- Samsung ---
    CanonicalModel("samsung-nv10", "Samsung NV10", "samsung", "NV", [
        "三星nv10", "samsung nv10", "nv10",
    ], KeywordTier.T0_HOT),
]


# ============================================================
# T1 普通型号：从 ccd_keywords.py 中属于主流系列但非 T0 的关键词
# ============================================================
_T1_SERIES_PATTERNS = [
    # Canon IXUS 系列（T0 已覆盖热门子型号，其余归 T1）
    ("ixus", "canon", "IXUS"),
    ("powershot a", "canon", "PowerShot A"),
    ("powershot sx", "canon", "PowerShot SX"),
    # Sony Cyber-shot T/TX/W/WX/H 系列（T0 已覆盖最热门）
    ("dsc-t", "sony", "Cyber-shot"),
    ("dsc-tx", "sony", "Cyber-shot"),
    ("dsc-w", "sony", "Cyber-shot"),
    ("dsc-wx", "sony", "Cyber-shot"),
    ("dsc-h", "sony", "Cyber-shot"),
    # Nikon Coolpix S/L
    ("coolpix s", "nikon", "Coolpix"),
    ("coolpix l", "nikon", "Coolpix"),
    # Panasonic Lumix FX
    ("dmc-fx", "panasonic", "Lumix"),
    # Casio Exilim
    ("ex-z", "casio", "Exilim"),
    # Samsung NV/ST
    ("nv", "samsung", "NV"),
    ("st", "samsung", "ST"),
    # Fujifilm FinePix
    ("finepix", "fuji", "FinePix"),
    # Olympus mu/FE/SP
    ("olympus", "olympus", "mu"),
    # Pentax Optio
    ("optio", "pentax", "Optio"),
    # Kodak EasyShare
    ("kodak", "kodak", "EasyShare"),
]


def _infer_brand(keyword_lower: str) -> str:
    brands = [
        ("canon", "canon"), ("nikon", "nikon"), ("sony", "sony"),
        ("fuji", "fuji"), ("olympus", "olympus"), ("panasonic", "panasonic"),
        ("lumix", "panasonic"), ("casio", "casio"), ("samsung", "samsung"),
        ("pentax", "pentax"), ("kodak", "kodak"),
        ("佳能", "canon"), ("尼康", "nikon"), ("索尼", "sony"),
        ("富士", "fuji"), ("奥林巴斯", "olympus"), ("松下", "panasonic"),
        ("卡西欧", "casio"), ("三星", "samsung"),
    ]
    for pattern, brand in brands:
        if pattern in keyword_lower:
            return brand
    return "other"


def _matches_t1(keyword_lower: str) -> bool:
    for pattern, _, _ in _T1_SERIES_PATTERNS:
        if pattern in keyword_lower:
            return True
    # Chinese brand-only keywords are also T1 (e.g. "佳能ccd")
    for prefix in ["佳能", "索尼", "尼康", "富士", "松下", "卡西欧", "三星", "奥林巴斯"]:
        if keyword_lower.startswith(prefix):
            return True
    return False


# ============================================================
# 索引构建
# ============================================================

_keyword_to_model: Dict[str, CanonicalModel] = {}
_model_by_id: Dict[str, CanonicalModel] = {}
_tier_keywords: Dict[KeywordTier, List[str]] = {t: [] for t in KeywordTier}


def _build_indices():
    from app.services.ccd_keywords import get_model_keyword_groups

    groups = get_model_keyword_groups()
    group_aliases = [
        {keyword.strip().lower() for keyword in group}
        for group in groups
    ]

    _keyword_to_model.clear()
    _model_by_id.clear()
    for tier in KeywordTier:
        _tier_keywords[tier] = []

    # Match explicit T0 definitions to generated groups before mutating either
    # index. Sorting by overlap keeps similarly named models such as IXUS 300
    # and IXUS 300 HS distinct.
    candidates = []
    for model_index, model in enumerate(T0_CANONICAL_MODELS):
        aliases = {keyword.strip().lower() for keyword in model.keywords}
        for group_index, group_set in enumerate(group_aliases):
            overlap = len(aliases & group_set)
            if overlap >= 2:
                candidates.append((overlap, model_index, group_index))
    candidates.sort(key=lambda candidate: (-candidate[0], candidate[1], candidate[2]))

    group_to_t0: Dict[int, CanonicalModel] = {}
    assigned_models = set()
    for _overlap, model_index, group_index in candidates:
        if model_index in assigned_models or group_index in group_to_t0:
            continue
        assigned_models.add(model_index)
        group_to_t0[group_index] = T0_CANONICAL_MODELS[model_index]

    if len(assigned_models) != len(T0_CANONICAL_MODELS):
        missing = [
            model.model_id
            for index, model in enumerate(T0_CANONICAL_MODELS)
            if index not in assigned_models
        ]
        raise RuntimeError(f"T0 models missing generated keyword groups: {missing}")

    # Register T0 models first so ambiguous aliases keep their curated mapping.
    used_representatives = set()
    for model in T0_CANONICAL_MODELS:
        _model_by_id[model.model_id] = model
        for kw in model.keywords:
            _keyword_to_model.setdefault(kw.strip().lower(), model)
        representative = model.keywords[0].strip()
        _tier_keywords[KeywordTier.T0_HOT].append(representative)
        used_representatives.add(representative.lower())

    # Map every generated alias group to exactly one model and one unique
    # representative search keyword.
    for group_index, group in enumerate(groups):
        overlap = group_to_t0.get(group_index)
        if overlap is not None:
            for kw in group:
                norm = kw.strip().lower()
                _keyword_to_model.setdefault(norm, overlap)
                if kw.strip() not in overlap.keywords:
                    overlap.keywords.append(kw.strip())
            continue

        representative = next(
            (
                keyword.strip()
                for keyword in group
                if keyword.strip().lower() not in used_representatives
                and keyword.strip().lower() not in _keyword_to_model
            ),
            None,
        )
        if representative is None:
            raise RuntimeError(f"Model group has no unique representative: {group}")

        norm = representative.lower()
        brand = _infer_brand(norm)
        is_t1 = any(_matches_t1(kw.strip().lower()) for kw in group)
        tier = KeywordTier.T1_WARM if is_t1 else KeywordTier.T2_COLD

        model_id = f"tier:{brand}:{group_index:04d}"
        model = CanonicalModel(
            model_id=model_id, display_name=representative,
            brand=brand, series="",
            keywords=[kw.strip() for kw in group], tier=tier,
        )
        _model_by_id[model_id] = model
        for kw in group:
            _keyword_to_model.setdefault(kw.strip().lower(), model)
        _tier_keywords[tier].append(representative)
        used_representatives.add(norm)

    representative_count = sum(len(keywords) for keywords in _tier_keywords.values())
    if representative_count != len(groups):
        raise RuntimeError(
            "Representative model schedule does not match normalized model groups: "
            f"{representative_count} != {len(groups)}"
        )


_build_indices()


# ============================================================
# 公开 API
# ============================================================

def get_canonical_model(keyword: str) -> Optional[CanonicalModel]:
    value = keyword.strip().lower()
    return _keyword_to_model.get(value) or _model_by_id.get(value)


def get_model_by_id(model_id: str) -> Optional[CanonicalModel]:
    return _model_by_id.get(model_id)


def get_keywords_by_tier(tier: KeywordTier) -> List[str]:
    return list(_tier_keywords.get(tier, []))


def get_tier(keyword: str) -> KeywordTier:
    model = get_canonical_model(keyword)
    return model.tier if model else KeywordTier.T2_COLD


def get_canonical_keyword(keyword: str) -> str:
    model = get_canonical_model(keyword)
    if model:
        return model.model_id
    return keyword.strip().lower()


def get_display_name(keyword: str) -> str:
    model = get_canonical_model(keyword)
    return model.display_name if model else keyword


def get_all_model_ids() -> List[str]:
    return list(_model_by_id.keys())


def get_t0_model_ids() -> List[str]:
    return [m.model_id for m in T0_CANONICAL_MODELS]


def get_tier_counts() -> Dict[str, int]:
    return {tier.value: len(kws) for tier, kws in _tier_keywords.items()}


def get_model_keywords_for_pricing(keyword: str) -> List[str]:
    model = get_canonical_model(keyword)
    if model:
        return list(model.keywords)
    return [keyword.strip()]


def get_all_keywords() -> List[str]:
    result = []
    for tier in (KeywordTier.T0_HOT, KeywordTier.T1_WARM, KeywordTier.T2_COLD):
        result.extend(_tier_keywords.get(tier, []))
    return result
