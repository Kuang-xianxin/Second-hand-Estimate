"""Gold evaluation dataset — 120 manually curated test cases.

Design doc §9.1 categories:
  - 30 model & spec queries
  - 25 price & trend queries
  - 20 adjacent model discrimination
  - 20 accessory/rental/repair/bait identification
  - 15 multi-condition purchase queries
  - 10 insufficient/conflicting information queries
"""
from __future__ import annotations

from app.rag.evaluation import EvalQuery

# ── Category 1: Model & Spec Queries (30 cases) ──

MODEL_SPEC_QUERIES: list[EvalQuery] = [
    EvalQuery("M001", "佳能IXUS130是什么传感器", ["camera_canon_ixus_series"], "model_query"),
    EvalQuery("M002", "富士F30用的是什么存储卡", ["camera_fuji_finepix", "storage_xd_card_overview"], "model_query"),
    EvalQuery("M003", "索尼T900的屏幕多大", ["camera_sony_t_series"], "model_query"),
    EvalQuery("M004", "奥林巴斯μ系列防水吗", ["camera_olympus_mju"], "model_query"),
    EvalQuery("M005", "尼康COOLPIX用什么电池", ["camera_nikon_coolpix"], "model_query"),
    EvalQuery("M006", "松下Lumix是徕卡镜头吗", ["camera_panasonic_lumix"], "model_query"),
    EvalQuery("M007", "佳能IXUS系列有哪些热门型号", ["camera_canon_ixus_series"], "model_query"),
    EvalQuery("M008", "索尼T系列和W系列有什么区别", ["camera_sony_t_series"], "model_query"),
    EvalQuery("M009", "富士F31fd和F30有什么区别", ["camera_fuji_finepix"], "model_query"),
    EvalQuery("M010", "奥林巴斯μ1030SW防水深度多少", ["camera_olympus_mju"], "model_query"),
    EvalQuery("M011", "松下LX3是什么级别的相机", ["camera_panasonic_lumix"], "model_query"),
    EvalQuery("M012", "尼康COOLPIX S5100参数", ["camera_nikon_coolpix"], "model_query"),
    EvalQuery("M013", "佳能IXUS 95 IS像素多少", ["camera_canon_ixus_series"], "model_query"),
    EvalQuery("M014", "索尼T700有内置存储吗", ["camera_sony_t_series"], "model_query"),
    EvalQuery("M015", "富士FinePix F系列全部用xD卡吗", ["camera_fuji_finepix", "storage_xd_card_overview"], "model_query"),
    EvalQuery("M016", "奥林巴斯μ840常见故障", ["camera_olympus_mju", "fault_lens_stuck"], "model_query"),
    EvalQuery("M017", "松下FX30是CCD还是CMOS", ["camera_panasonic_lumix"], "model_query"),
    EvalQuery("M018", "尼康P5100是专业机吗", ["camera_nikon_coolpix"], "model_query"),
    EvalQuery("M019", "佳能IXUS 130上市时间", ["camera_canon_ixus_series"], "model_query"),
    EvalQuery("M020", "索尼T900支持触摸屏吗", ["camera_sony_t_series"], "model_query"),
    EvalQuery("M021", "富士F200EXR传感器类型", ["camera_fuji_finepix"], "model_query"),
    EvalQuery("M022", "奥林巴斯MASD-1是什么", ["storage_masd1_adapter"], "model_query"),
    EvalQuery("M023", "松下FZ28是长焦机吗", ["camera_panasonic_lumix"], "model_query"),
    EvalQuery("M024", "尼康L20用AA电池吗", ["camera_nikon_coolpix"], "model_query"),
    EvalQuery("M025", "佳能PowerShot和IXUS什么关系", ["camera_canon_ixus_series"], "model_query"),
    EvalQuery("M026", "索尼记忆棒有哪些类型", ["storage_sd_cf_ms_overview"], "model_query"),
    EvalQuery("M027", "xD卡最大容量多少", ["storage_xd_card_overview"], "model_query"),
    EvalQuery("M028", "CF卡和SD卡哪个快", ["storage_sd_cf_ms_overview"], "model_query"),
    EvalQuery("M029", "CCD和CMOS有什么区别", ["faq_what_is_ccd"], "model_query"),
    EvalQuery("M030", "买二手CCD怎么验机", ["faq_how_to_inspect"], "model_query"),
]

# ── Category 2: Price & Trend Queries (25 cases) ──

PRICE_QUERIES: list[EvalQuery] = [
    EvalQuery("P001", "佳能IXUS130现在多少钱", ["camera_canon_ixus_series"], "price_trend"),
    EvalQuery("P002", "富士F30二手价格区间", ["camera_fuji_finepix"], "price_trend"),
    EvalQuery("P003", "索尼T900最近涨价了吗", ["camera_sony_t_series"], "price_trend"),
    EvalQuery("P004", "奥林巴斯μ系列哪个性价比最高", ["camera_olympus_mju"], "price_trend"),
    EvalQuery("P005", "尼康COOLPIX便宜型号推荐", ["camera_nikon_coolpix"], "price_trend"),
    EvalQuery("P006", "300元能买到什么CCD相机", [], "price_trend"),
    EvalQuery("P007", "500以内性价比最高的CCD", [], "price_trend"),
    EvalQuery("P008", "佳能IXUS 105和130价格差多少", ["camera_canon_ixus_series"], "price_trend"),
    EvalQuery("P009", "富士F30比F20贵多少", ["camera_fuji_finepix"], "price_trend"),
    EvalQuery("P010", "索尼T系列哪个最保值", ["camera_sony_t_series"], "price_trend"),
    EvalQuery("P011", "CCD相机最近降价了吗", [], "price_trend"),
    EvalQuery("P012", "松下LX3二手价格走势", ["camera_panasonic_lumix"], "price_trend"),
    EvalQuery("P013", "奥林巴斯μ系列二手行情", ["camera_olympus_mju"], "price_trend"),
    EvalQuery("P014", "尼康P5100现在还值钱吗", ["camera_nikon_coolpix"], "price_trend"),
    EvalQuery("P015", "佳能IXUS 80 IS现在多少", ["camera_canon_ixus_series"], "price_trend"),
    EvalQuery("P016", "索尼T77和T90价格对比", ["camera_sony_t_series"], "price_trend"),
    EvalQuery("P017", "富士F100fd二手多少钱", ["camera_fuji_finepix"], "price_trend"),
    EvalQuery("P018", "松下FX55现在还值得买吗", ["camera_panasonic_lumix"], "price_trend"),
    EvalQuery("P019", "100元以内能买到CCD吗", [], "price_trend"),
    EvalQuery("P020", "CCD相机为什么涨价了", ["faq_what_is_ccd"], "price_trend"),
    EvalQuery("P021", "带XD卡的富士F30比裸机贵多少", ["camera_fuji_finepix", "storage_xd_card_pricing"], "price_trend"),
    EvalQuery("P022", "佳能IXUS系列哪个型号最便宜", ["camera_canon_ixus_series"], "price_trend"),
    EvalQuery("P023", "索尼T300入手价多少合适", ["camera_sony_t_series"], "price_trend"),
    EvalQuery("P024", "奥林巴斯μ1030SW二手行情", ["camera_olympus_mju"], "price_trend"),
    EvalQuery("P025", "CCD相机什么时候买最划算", [], "price_trend"),
]

# ── Category 3: Adjacent Model Discrimination (20 cases) ──

MODEL_DISCRIMINATION: list[EvalQuery] = [
    EvalQuery("D001", "IXUS130和IXUS105有什么区别", ["camera_canon_ixus_series"], "model_discrimination"),
    EvalQuery("D002", "T900和T90是一个型号吗", ["camera_sony_t_series"], "model_discrimination"),
    EvalQuery("D003", "F30和F31fd哪个好", ["camera_fuji_finepix"], "model_discrimination"),
    EvalQuery("D004", "LX3和LX2差别大吗", ["camera_panasonic_lumix"], "model_discrimination"),
    EvalQuery("D005", "μ1030SW和μ850SW怎么选", ["camera_olympus_mju"], "model_discrimination"),
    EvalQuery("D006", "尼康S5100和S4000哪个好", ["camera_nikon_coolpix"], "model_discrimination"),
    EvalQuery("D007", "佳能IXUS 110 IS和130哪个新", ["camera_canon_ixus_series"], "model_discrimination"),
    EvalQuery("D008", "索尼T77和T90怎么区分", ["camera_sony_t_series"], "model_discrimination"),
    EvalQuery("D009", "富士F100fd和F200EXR哪个好", ["camera_fuji_finepix"], "model_discrimination"),
    EvalQuery("D010", "松下FX30和FX33区别", ["camera_panasonic_lumix"], "model_discrimination"),
    EvalQuery("D011", "奥林巴斯μ840和μ830差别", ["camera_olympus_mju"], "model_discrimination"),
    EvalQuery("D012", "尼康P5100和P5000比较", ["camera_nikon_coolpix"], "model_discrimination"),
    EvalQuery("D013", "佳能IXUS 95 IS和90 IS区别", ["camera_canon_ixus_series"], "model_discrimination"),
    EvalQuery("D014", "索尼T200和T300怎么选", ["camera_sony_t_series"], "model_discrimination"),
    EvalQuery("D015", "富士F30对比松下LX3", ["camera_fuji_finepix", "camera_panasonic_lumix"], "model_discrimination"),
    EvalQuery("D016", "佳能IXUS和索尼T系列哪个好", ["camera_canon_ixus_series", "camera_sony_t_series"], "model_discrimination"),
    EvalQuery("D017", "尼康S220和S210差别", ["camera_nikon_coolpix"], "model_discrimination"),
    EvalQuery("D018", "奥林巴斯μ750和μ740", ["camera_olympus_mju"], "model_discrimination"),
    EvalQuery("D019", "松下FS3和FS5选哪个", ["camera_panasonic_lumix"], "model_discrimination"),
    EvalQuery("D020", "富士F10/F11/F20系列对比", ["camera_fuji_finepix"], "model_discrimination"),
]

# ── Category 4: Risk Identification (20 cases) ──

RISK_QUERIES: list[EvalQuery] = [
    EvalQuery("R001", "富士F30不附带存储卡能买吗", ["camera_fuji_finepix", "storage_xd_card_overview"], "risk"),
    EvalQuery("R002", "闲鱼上IXUS130只要200靠谱吗", ["rule_bait_filtering"], "risk"),
    EvalQuery("R003", "索尼T900镜头有异响能修吗", ["camera_sony_t_series", "fault_lens_stuck"], "risk"),
    EvalQuery("R004", "奥林巴斯屏幕老化怎么判断", ["fault_screen_aging"], "risk"),
    EvalQuery("R005", "出租的CCD相机能买吗", ["rule_bait_filtering"], "risk"),
    EvalQuery("R006", "富士F30电池不耐用正常吗", ["fault_battery_aging", "camera_fuji_finepix"], "risk"),
    EvalQuery("R007", "xD卡槽接触不良怎么修", ["fault_xd_card_slot"], "risk"),
    EvalQuery("R008", "闲鱼盲盒CCD相机值得买吗", ["rule_bait_filtering"], "risk"),
    EvalQuery("R009", "镜头伸缩卡顿修好要多少钱", ["fault_lens_stuck"], "risk"),
    EvalQuery("R010", "尼康COOLPIX模式拨盘松了", ["camera_nikon_coolpix"], "risk"),
    EvalQuery("R011", "配件机当整机卖怎么识别", ["rule_bait_filtering", "rule_accessory_deduction"], "risk"),
    EvalQuery("R012", "索尼记忆棒坏了有替代吗", ["storage_sd_cf_ms_overview"], "risk"),
    EvalQuery("R013", "松下防抖组件异响正常吗", ["camera_panasonic_lumix"], "risk"),
    EvalQuery("R014", "CCD相机闪光灯不亮", ["camera_canon_ixus_series"], "risk"),
    EvalQuery("R015", "低价引流的商品怎么过滤", ["rule_bait_filtering"], "risk"),
    EvalQuery("R016", "奥林巴斯防水机密封圈老化", ["camera_olympus_mju"], "risk"),
    EvalQuery("R017", "第三方电池能用吗", ["fault_battery_aging"], "risk"),
    EvalQuery("R018", "闲鱼上回收CCD的是骗局吗", ["rule_bait_filtering"], "risk"),
    EvalQuery("R019", "富士F30镜头排线故障率", ["camera_fuji_finepix", "fault_lens_stuck"], "risk"),
    EvalQuery("R020", "买二手CCD最大的坑是什么", ["faq_how_to_inspect"], "risk"),
]

# ── Category 5: Multi-condition Purchase (15 cases) ──

MULTI_CONDITION: list[EvalQuery] = [
    EvalQuery("C001", "300-500元，适合女生的CCD相机推荐", [], "multi_condition"),
    EvalQuery("C002", "500以内带XD卡的富士相机推荐", ["camera_fuji_finepix", "storage_xd_card_pricing"], "multi_condition"),
    EvalQuery("C003", "索尼滑盖CCD 300元左右买哪个", ["camera_sony_t_series"], "multi_condition"),
    EvalQuery("C004", "给女朋友买CCD 外观好看拍照好", [], "multi_condition"),
    EvalQuery("C005", "入门CCD推荐 预算200-300", [], "multi_condition"),
    EvalQuery("C006", "适合拍人的CCD相机 500以内", [], "multi_condition"),
    EvalQuery("C007", "防水防尘的CCD相机推荐", ["camera_olympus_mju"], "multi_condition"),
    EvalQuery("C008", "长焦CCD相机推荐 拍远景用", ["camera_panasonic_lumix", "camera_nikon_coolpix"], "multi_condition"),
    EvalQuery("C009", "佳能IXUS系列400元哪个最好", ["camera_canon_ixus_series"], "multi_condition"),
    EvalQuery("C010", "复古外观CCD推荐 不要太贵", [], "multi_condition"),
    EvalQuery("C011", "带触屏的索尼CCD推荐", ["camera_sony_t_series"], "multi_condition"),
    EvalQuery("C012", "适合收藏的经典CCD型号", [], "multi_condition"),
    EvalQuery("C013", "超薄CCD卡片机 300-400预算", ["camera_canon_ixus_series", "camera_sony_t_series"], "multi_condition"),
    EvalQuery("C014", "富士和佳能CCD 预算500选哪个", ["camera_fuji_finepix", "camera_canon_ixus_series"], "multi_condition"),
    EvalQuery("C015", "奥林巴斯μ系列买哪个型号最值", ["camera_olympus_mju"], "multi_condition"),
]

# ── Category 6: Insufficient/Edge Cases (10 cases) ──

EDGE_CASES: list[EvalQuery] = [
    EvalQuery("E001", "相机", [], "insufficient", min_expected_hits=0),
    EvalQuery("E002", "便宜", [], "insufficient", min_expected_hits=0),
    EvalQuery("E003", "佳能5D4多少钱", [], "model_discrimination"),  # DSLR, not CCD
    EvalQuery("E004", "索尼A7M3二手价格", [], "model_discrimination"),
    EvalQuery("E005", "富士X100V", [], "model_discrimination"),
    EvalQuery("E006", "GR3和X100V哪个好", [], "model_discrimination"),
    EvalQuery("E007", "", [], "insufficient", min_expected_hits=0),
    EvalQuery("E008", "有没有3000元的CCD相机", [], "insufficient"),
    EvalQuery("E009", "帮我查一下尼康Z50", [], "model_discrimination"),  # mirrorless, not CCD
    EvalQuery("E010", "索尼T900和iPhone15拍照对比", ["camera_sony_t_series"], "model_discrimination"),
]


def get_gold_dataset() -> list[EvalQuery]:
    """Return the full 120-case gold evaluation dataset."""
    return (
        MODEL_SPEC_QUERIES
        + PRICE_QUERIES
        + MODEL_DISCRIMINATION
        + RISK_QUERIES
        + MULTI_CONDITION
        + EDGE_CASES
    )
