"""
xD 卡 CCD 相机完整机型数据库。

数据来源（按优先级）：
1. Olympus 官网兼容性列表（support.jp.omsystem.com）— FE/μ/Stylus/SP 系列
2. Wikipedia FinePix 系列词条 — 富士各系列
3. Wikipedia XD-Picture Card 词条 — xD 卡历史及停产时间

数据原则：
- 所有 xD 卡机型约在 2002-2009 年间生产，2009 年后富士/奥林巴斯全面停产 xD
- 一个型号只写一个位置（不重复）
- 没有在可靠来源中确认的机型，不写入数据库

使用方式：
    from app.services.xd_card_models import is_xd_card_model
    if is_xd_card_model("富士 F200EXR"):
        print("xD 卡机型")
"""

# ============================================================================
# 富士 FinePix 系列
# ============================================================================

# A 系列：家用入门
# 确认：A101/A201 仅 SD（最早两款），A100 及以后全部 xD（Wikipedia: "All but the first two A-series cameras have used xD"）
FUJIFILM_A_XD: set[str] = {
    # 仅 xD（A101/A201 是例外，外逃单独处理）
    "a100", "a120", "a150", "a170", "a175", "a180",
    "a200", "a202", "a203", "a205", "a210",
    "a220", "a225", "a230", "a235",
    "a303", "a310", "a330", "a340", "a345", "a350",
    "a400", "a500", "a510", "a600", "a607",
    "a610", "a700", "a800", "a805", "a810", "a820", "a850", "a900", "a920",
    "ax350", "ax510", "ax550",
    "av200", "av220", "av230", "av250",
}

FUJIFILM_A_XD_VARIANTS: set[str] = {
    "finepix a100", "finepix a120", "finepix a150", "finepix a170",
    "finepix a175", "finepix a180", "finepix a200", "finepix a202",
    "finepix a203", "finepix a205", "finepix a210", "finepix a220",
    "finepix a225", "finepix a230", "finepix a235", "finepix a303",
    "finepix a310", "finepix a330", "finepix a340", "finepix a345",
    "finepix a350", "finepix a400", "finepix a500", "finepix a510",
    "finepix a600", "finepix a607", "finepix a610", "finepix a700",
    "finepix a800", "finepix a805", "finepix a820", "finepix a850",
    "finepix a900", "finepix a920",
    "fuji a100", "fuji a120", "fuji a150", "fuji a170",
    "fuji a175", "fuji a180", "fuji a200", "fuji a202",
    "fuji a203", "fuji a205", "fuji a210", "fuji a220",
    "fuji a225", "fuji a230", "fuji a235", "fuji a303",
    "fuji a310", "fuji a330", "fuji a340", "fuji a345",
    "fuji a350", "fuji a400", "fuji a500", "fuji a510",
    "fuji a600", "fuji a607", "fuji a610", "fuji a700",
    "fuji a800", "fuji a805", "fuji a820", "fuji a850",
    "fuji a900", "fuji a920",
}

# F 系列：旗舰/中高端
# 确认：F401-F200EXR 使用 xD，F70EXR 起改 SD
FUJIFILM_F_XD: set[str] = {
    # 早期 xD 型号
    "f401", "f402", "f410", "f420", "f440", "f450", "f455", "f460", "f470",
    "f650", "f700",
    # F10-F31fd 仅 xD
    "f10", "f11", "f20", "f30", "f31fd",
    # F40fd-F200EXR：xD + SD 双插槽
    "f40fd", "f47fd", "f480", "f50fd", "f60fd", "f100fd", "f200exr",
}

FUJIFILM_F_XD_VARIANTS: set[str] = {
    "finepix f401", "finepix f402", "finepix f410", "finepix f420",
    "finepix f440", "finepix f450", "finepix f455", "finepix f460", "finepix f470",
    "finepix f650", "finepix f700",
    "finepix f10", "finepix f11", "finepix f20", "finepix f30", "finepix f31fd",
    "finepix f40fd", "finepix f47fd", "finepix f480",
    "finepix f50fd", "finepix f60fd", "finepix f100fd", "finepix f200exr",
    "fuji f401", "fuji f402", "fuji f410", "fuji f420",
    "fuji f440", "fuji f450", "fuji f455", "fuji f460", "fuji f470",
    "fuji f650", "fuji f700",
    "fuji f10", "fuji f11", "fuji f20", "fuji f30", "fuji f31fd",
    "fuji f40fd", "fuji f47fd", "fuji f480",
    "fuji f50fd", "fuji f60fd", "fuji f100fd", "fuji f200exr",
}

# S 系列：长焦 bridge 机 + DSLR
# 确认：S5000-S9600 + S1/S2/S3/S5 Pro + IS Pro 使用 xD
#       S2500fd 起改 SD（2008年后）
FUJIFILM_S_XD: set[str] = {
    # DSLR
    "s1pro", "s1 pro", "s2pro", "s2 pro",
    "s3pro", "s3 pro", "s5pro", "s5 pro",
    "ispro", "is pro",
    # Bridge xD 机型
    "s3500",
    "s5000", "s5100", "s5200", "s5500", "s5600",
    "s5700", "s5800",
    "s6000fd", "s6500fd",
    "s7000", "s9000", "s9500", "s9600",
    "sp-1", "sp1",
}

FUJIFILM_S_XD_VARIANTS: set[str] = {
    "finepix s1pro", "finepix s1 pro", "finepix s2pro", "finepix s2 pro",
    "finepix s3pro", "finepix s3 pro", "finepix s5pro", "finepix s5 pro",
    "finepix ispro", "finepix is pro",
    "finepix s3500", "finepix s5000", "finepix s5100", "finepix s5200",
    "finepix s5500", "finepix s5600", "finepix s5700", "finepix s5800",
    "finepix s6000fd", "finepix s6500fd",
    "finepix s7000", "finepix s9000", "finepix s9500", "finepix s9600",
    "fuji s1pro", "fuji s1 pro", "fuji s2pro", "fuji s2 pro",
    "fuji s3pro", "fuji s3 pro", "fuji s5pro", "fuji s5 pro",
    "fuji s3500", "fuji s5000", "fuji s5100", "fuji s5200",
    "fuji s5500", "fuji s5600", "fuji s5700", "fuji s5800",
    "fuji s6000fd", "fuji s6500fd",
    "fuji s7000", "fuji s9000", "fuji s9500", "fuji s9600",
}

# Z 系列：时尚超薄
# 确认（Wikipedia + Imaging Resource）：
# Z1/Z2/Z3/Z5fd 仅 xD；Z10fd/Z15fd/Z20fd/Z30/Z35/Z37 xD+SD
# Z70 起全 SD
FUJIFILM_Z_XD: set[str] = {
    "z1", "z2", "z3",
    "z5fd", "z10fd", "z15fd",
    "z20fd", "z30", "z33wp", "z35", "z37",
    "z100fd", "z200fd", "z250",
}

FUJIFILM_Z_XD_VARIANTS: set[str] = {
    "finepix z1", "finepix z2", "finepix z3",
    "finepix z5fd", "finepix z10fd", "finepix z15fd",
    "finepix z20fd", "finepix z30", "finepix z33wp", "finepix z35", "finepix z37",
    "finepix z100fd", "finepix z200fd", "finepix z250",
    "fuji z1", "fuji z2", "fuji z3",
    "fuji z5fd", "fuji z10fd", "fuji z15fd",
    "fuji z20fd", "fuji z30", "fuji z33wp", "fuji z35", "fuji z37",
    "fuji z100fd", "fuji z200fd", "fuji z250",
}

# E 系列：入门（全部 xD）
FUJIFILM_E_XD: set[str] = {
    "e500", "e510", "e550", "e900",
}

FUJIFILM_E_XD_VARIANTS: set[str] = {
    "finepix e500", "finepix e510", "finepix e550", "finepix e900",
    "fuji e500", "fuji e510", "fuji e550", "fuji e900",
}

# J 系列：家用入门
# 确认（Wikipedia）：仅 J10/J12/J15fd/J50 使用 xD，J15fd 是 xD+SD 双卡槽，J20 及以后全部 SD
FUJIFILM_J_XD: set[str] = {
    "j10", "j12", "j15fd", "j50",
}

FUJIFILM_J_XD_VARIANTS: set[str] = {
    "finepix j10", "finepix j12", "finepix j15fd", "finepix j50",
    "fuji j10", "fuji j12", "fuji j15fd", "fuji j50",
}

# V / M 系列（全部 xD）
FUJIFILM_OTHER_XD: set[str] = {
    "v10", "m603",
}

FUJIFILM_OTHER_XD_VARIANTS: set[str] = {
    "finepix v10", "finepix m603",
    "fuji v10", "fuji m603",
}

# 富士所有 xD 机型全集
FUJIFILM_ALL_XD: set[str] = (
    FUJIFILM_A_XD
    | FUJIFILM_F_XD
    | FUJIFILM_S_XD
    | FUJIFILM_Z_XD
    | FUJIFILM_E_XD
    | FUJIFILM_J_XD
    | FUJIFILM_OTHER_XD
)

FUJIFILM_ALL_XD_VARIANTS: set[str] = (
    FUJIFILM_A_XD_VARIANTS
    | FUJIFILM_F_XD_VARIANTS
    | FUJIFILM_S_XD_VARIANTS
    | FUJIFILM_Z_XD_VARIANTS
    | FUJIFILM_E_XD_VARIANTS
    | FUJIFILM_J_XD_VARIANTS
    | FUJIFILM_OTHER_XD_VARIANTS
)


# ============================================================================
# 奥林巴斯 Olympus 系列
# 数据来源：Olympus 官网兼容性表（support.jp.omsystem.com）
# ============================================================================

# E 系列 DSLR（四 thirds 系统）
# 确认：E-1/E-300 仅 CF；E-330-E-620 支持 xD+CF；E-5 仅 SD+CF
OLYMPUS_E_DSLR_XD: set[str] = {
    "e-330", "e330",
    "e-410", "e410",
    "e-420", "e420",
    "e-500", "e500",
    "e-510", "e510",
    "e-520", "e520",
    "e-620", "e620",
    "e-30", "e30",
    "e-3", "e3",
}

OLYMPUS_E_DSLR_XD_VARIANTS: set[str] = {
    "olympus e-330", "olympus e330",
    "olympus e-410", "olympus e410",
    "olympus e-420", "olympus e420",
    "olympus e-500", "olympus e500",
    "olympus e-510", "olympus e510",
    "olympus e-520", "olympus e520",
    "olympus e-620", "olympus e620",
    "olympus e-30", "olympus e30",
    "olympus e-3", "olympus e3",
}

# μ / Stylus 系列：时尚/潜水/三防
# 确认（Olympus 官网 + Wikipedia）：
# - μ-mini Digital 全部 xD
# - μ 300-1000 系列全部 xD
# - μ 1010-1070 全部 xD
# - μ 5000/5010 全部 xD
# - μ 7000/7010 全部 xD
# - μ 9000 全部 xD
# - Tough-6000/8000 xD + microSD
# - μ 5500WP SD；Tough-3000/6020/8010 SD
OLYMPUS_MU_STYLUS_XD: set[str] = {
    # μ-mini Digital
    "mu-mini digital", "mu-mini digital s",
    # μ 300-1000
    "mu 300", "mu 400", "mu 410", "mu 410d",
    "mu 500", "mu 600", "mu 700", "mu 710",
    "mu 720sw", "mu 725sw", "mu 730", "mu 740",
    "mu 750", "mu 760", "mu 770sw", "mu 780",
    "mu 790sw", "mu 800", "mu 810", "mu 820",
    "mu 830", "mu 840", "mu 850sw", "mu 1000",
    # μ 1010-1200
    "mu 1010", "mu 1020", "mu 1030sw",
    "mu 1040", "mu 1050sw", "mu 1060", "mu 1070",
    "mu 1200",
    # μ 5000/5010
    "mu 5000", "mu 5010",
    # μ 7000/7010
    "mu 7000", "mu 7010",
    # μ 9000
    "mu 9000",
    # Tough xD 机型
    "mu tough-6000", "tough-6000", "tough6000",
    "mu tough-8000", "tough-8000", "tough8000",
    # Stylus 同名
    "stylus 300", "stylus 400", "stylus 410", "stylus 410d",
    "stylus 500", "stylus 600", "stylus 700", "stylus 710",
    "stylus 720sw", "stylus 725sw", "stylus 730", "stylus 740",
    "stylus 750", "stylus 760", "stylus 770sw", "stylus 780",
    "stylus 790sw", "stylus 800", "stylus 810", "stylus 820",
    "stylus 830", "stylus 840", "stylus 850sw", "stylus 1000",
    "stylus 1010", "stylus 1020", "stylus 1030sw",
    "stylus 1040", "stylus 1050sw", "stylus 1060", "stylus 1070",
    "stylus 1200",
    "stylus 5000", "stylus 5010",
    "stylus 7000", "stylus 7010",
    "stylus 9000",
    "stylus tough-6000", "stylus tough-8000",
}

OLYMPUS_MU_STYLUS_XD_VARIANTS: set[str] = {
    "olympus mu-mini digital", "olympus mu-mini digital s",
    "olympus mu 300", "olympus mu 400", "olympus mu 410", "olympus mu 410d",
    "olympus mu 500", "olympus mu 600", "olympus mu 700", "olympus mu 710",
    "olympus mu 720sw", "olympus mu 725sw", "olympus mu 730", "olympus mu 740",
    "olympus mu 750", "olympus mu 760", "olympus mu 770sw", "olympus mu 780",
    "olympus mu 790sw", "olympus mu 800", "olympus mu 810", "olympus mu 820",
    "olympus mu 830", "olympus mu 840", "olympus mu 850sw", "olympus mu 1000",
    "olympus mu 1010", "olympus mu 1020", "olympus mu 1030sw",
    "olympus mu 1040", "olympus mu 1050sw", "olympus mu 1060", "olympus mu 1070",
    "olympus mu 1200",
    "olympus mu 5000", "olympus mu 5010",
    "olympus mu 7000", "olympus mu 7010",
    "olympus mu 9000",
    "olympus tough-6000", "olympus tough-8000",
    "olympus stylus 300", "olympus stylus 400", "olympus stylus 410", "olympus stylus 410d",
    "olympus stylus 500", "olympus stylus 600", "olympus stylus 700", "olympus stylus 710",
    "olympus stylus 720sw", "olympus stylus 725sw", "olympus stylus 730", "olympus stylus 740",
    "olympus stylus 750", "olympus stylus 760", "olympus stylus 770sw", "olympus stylus 780",
    "olympus stylus 790sw", "olympus stylus 800", "olympus stylus 810", "olympus stylus 820",
    "olympus stylus 830", "olympus stylus 840", "olympus stylus 850sw", "olympus stylus 1000",
    "olympus stylus 1010", "olympus stylus 1020", "olympus stylus 1030sw",
    "olympus stylus 1040", "olympus stylus 1050sw", "olympus stylus 1060", "olympus stylus 1070",
    "olympus stylus 1200",
    "olympus stylus 5000", "olympus stylus 5010",
    "olympus stylus 7000", "olympus stylus 7010",
    "olympus stylus 9000",
}

# FE 系列：入门家用
# 确认（Olympus 官网兼容性表）：
# SD 卡型号：FE-47, FE-4020, FE-4030, FE-4050, FE-5020, FE-5040, FE-5050
# 其余全部 xD（FE-20/25/26/45/46 + FE-100~FE-5500）
OLYMPUS_FE_XD: set[str] = {
    # FE-20/25/26/45/46（2008-2009）
    "fe-20", "fe-25", "fe-26", "fe-45", "fe-46",
    # FE-100~FE-250（2005-2007）
    "fe-100", "fe-110", "fe-120", "fe-130", "fe-140",
    "fe-150", "fe-160", "fe-170", "fe-180", "fe-190", "fe-200",
    "fe-210", "fe-220", "fe-230", "fe-240", "fe-250",
    # FE-270~FE-5500（2008-2010）全部 xD
    # FE-270~FE-370：xD（FE-360/370 额外支持 microSD via MASD-1）
    "fe-270", "fe-280", "fe-290", "fe-300",
    "fe-310", "fe-320", "fe-330", "fe-340",
    "fe-350 wide", "fe-350wide",
    "fe-360", "fe-370",
    # FE-3000~FE-5500（2008-2010）全部 xD
    "fe-3000", "fe-3010",
    "fe-4000", "fe-4010", "fe-4020", "fe-4030",
    "fe-5000", "fe-5010", "fe-5030",
    "fe-5500",
}

OLYMPUS_FE_XD_VARIANTS: set[str] = {
    "olympus fe-20", "olympus fe-25", "olympus fe-26", "olympus fe-45", "olympus fe-46",
    "olympus fe-100", "olympus fe-110", "olympus fe-120", "olympus fe-130", "olympus fe-140",
    "olympus fe-150", "olympus fe-160", "olympus fe-170", "olympus fe-180", "olympus fe-190", "olympus fe-200",
    "olympus fe-210", "olympus fe-220", "olympus fe-230", "olympus fe-240", "olympus fe-250",
    "olympus fe-3000", "olympus fe-3010",
    "olympus fe-4000", "olympus fe-4010",
    "olympus fe-5000", "olympus fe-5010",
    "olympus fe-5500",
}

# SP 系列：长焦机
# 确认（Olympus 官网 + Wikipedia + Imaging Resource）：
# SP-500~SP-590UZ 使用 xD；SP-600UZ 及以后改 SD
OLYMPUS_SP_XD: set[str] = {
    "sp-310", "sp-320", "sp-350",
    "sp-500uz", "sp-510uz",
    "sp-550uz", "sp-560uz",
    "sp-565uz", "sp-570uz",
    "sp-590uz",
}

OLYMPUS_SP_XD_VARIANTS: set[str] = {
    "olympus sp-310", "olympus sp-320", "olympus sp-350",
    "olympus sp-500uz", "olympus sp-510uz",
    "olympus sp-550uz", "olympus sp-560uz",
    "olympus sp-565uz", "olympus sp-570uz",
    "olympus sp-590uz",
}

# 奥林巴斯所有 xD 机型全集
OLYMPUS_ALL_XD: set[str] = (
    OLYMPUS_E_DSLR_XD
    | OLYMPUS_MU_STYLUS_XD
    | OLYMPUS_FE_XD
    | OLYMPUS_SP_XD
)

OLYMPUS_ALL_XD_VARIANTS: set[str] = (
    OLYMPUS_E_DSLR_XD_VARIANTS
    | OLYMPUS_MU_STYLUS_XD_VARIANTS
    | OLYMPUS_FE_XD_VARIANTS
    | OLYMPUS_SP_XD_VARIANTS
)


# ============================================================================
# MASD-1 卡套兼容相机（奥林巴斯 xD 卡相机中支持 microSD+卡套替代的机型）
# 数据来源：Olympus 官方 MASD-1 兼容列表（2010年8月更新）+ Retro Digitals / Memorypack
#
# 分类说明：
# - 可用 MASD-1 全景功能不受限（✅）
# - 使用 MASD-1 时全景功能不可用（⚠️），需原生 xD 卡才能用全景
# ============================================================================

# μ / Stylus 系列 MASD-1 兼容（17款）
OLYMPUS_MASD1_MU_STYLUS: set[str] = {
    # ⚠️ 全景功能不可用
    "mu 840", "stylus 840",
    "mu 850sw", "stylus 850sw",
    "mu 1010", "stylus 1010",
    "mu 1020", "stylus 1020",
    "mu 1030sw", "stylus 1030sw",
    "mu 1040", "stylus 1040",
    "mu 1050sw", "stylus 1050sw",
    "mu 1060", "stylus 1060",
    # ✅ 全景功能可用
    "mu 1070", "stylus 1070",
    "mu 5000", "stylus 5000",
    "mu 550wp", "stylus 550wp",
    "mu 7000", "stylus 7000",
    "mu 7010", "stylus 7010",
    "mu 7020", "stylus 7020",
    "mu 9000", "stylus 9000",
    "mu tough-6000", "stylus tough-6000", "tough-6000", "tough6000",
    "mu tough-8000", "stylus tough-8000", "tough-8000", "tough8000",
}

OLYMPUS_MASD1_MU_STYLUS_VARIANTS: set[str] = {
    "olympus mu 840", "olympus stylus 840",
    "olympus mu 850sw", "olympus stylus 850sw",
    "olympus mu 1010", "olympus stylus 1010",
    "olympus mu 1020", "olympus stylus 1020",
    "olympus mu 1030sw", "olympus stylus 1030sw",
    "olympus mu 1040", "olympus stylus 1040",
    "olympus mu 1050sw", "olympus stylus 1050sw",
    "olympus mu 1060", "olympus stylus 1060",
    "olympus mu 1070", "olympus stylus 1070",
    "olympus mu 5000", "olympus stylus 5000",
    "olympus mu 550wp", "olympus stylus 550wp",
    "olympus mu 7000", "olympus stylus 7000",
    "olympus mu 7010", "olympus stylus 7010",
    "olympus mu 7020", "olympus stylus 7020",
    "olympus mu 9000", "olympus stylus 9000",
    "olympus mu tough-6000", "olympus stylus tough-6000",
    "olympus mu tough-8000", "olympus stylus tough-8000",
}

# FE 系列 MASD-1 兼容（13款）
OLYMPUS_MASD1_FE: set[str] = {
    # ⚠️ 全景功能不可用
    "fe-20",
    "fe-360",
    "fe-370",
    # ✅ 全景功能可用
    "fe-25",
    "fe-26",
    "fe-45",
    "fe-46",
    "fe-3000",
    "fe-3010",
    "fe-4000",
    "fe-4010",
    "fe-5000",
    "fe-5010",
    "fe-5020",
}

OLYMPUS_MASD1_FE_VARIANTS: set[str] = {
    "olympus fe-20",
    "olympus fe-25",
    "olympus fe-26",
    "olympus fe-45",
    "olympus fe-46",
    "olympus fe-3000",
    "olympus fe-3010",
    "olympus fe-360",
    "olympus fe-370",
    "olympus fe-4000",
    "olympus fe-4010",
    "olympus fe-5000",
    "olympus fe-5010",
    "olympus fe-5020",
}

# SP 系列 MASD-1 兼容（3款）
OLYMPUS_MASD1_SP: set[str] = {
    # ⚠️ 全景功能不可用
    "sp-565uz",
    # ✅ 全景功能可用
    "sp-590uz",
    "sp-700",
}

OLYMPUS_MASD1_SP_VARIANTS: set[str] = {
    "olympus sp-565uz",
    "olympus sp-590uz",
    "olympus sp-700",
}

# MASD-1 兼容全集
OLYMPUS_MASD1_ALL: set[str] = (
    OLYMPUS_MASD1_MU_STYLUS
    | OLYMPUS_MASD1_FE
    | OLYMPUS_MASD1_SP
)

OLYMPUS_MASD1_ALL_VARIANTS: set[str] = (
    OLYMPUS_MASD1_MU_STYLUS_VARIANTS
    | OLYMPUS_MASD1_FE_VARIANTS
    | OLYMPUS_MASD1_SP_VARIANTS
)


# ============================================================================
# 合并全集
# ============================================================================

ALL_XD_MODELS: set[str] = FUJIFILM_ALL_XD | OLYMPUS_ALL_XD
ALL_XD_MODEL_VARIANTS: set[str] = FUJIFILM_ALL_XD_VARIANTS | OLYMPUS_ALL_XD_VARIANTS


# ============================================================================
# 关键词匹配函数
# ============================================================================

import re, logging
logger = logging.getLogger(__name__)


NON_XD_BRAND_ALIASES: tuple[str, ...] = (
    # WHY: Casio/Sony/Canon model numbers can share short tokens with Fuji or
    # Olympus xD models, so brand context must win before fuzzy model matching.
    "canon", "佳能", "ixus", "ixy", "powershot",
    "nikon", "尼康", "coolpix",
    "sony", "索尼", "cybershot", "cyber-shot",
    "panasonic", "松下", "lumix",
    "casio", "卡西欧", "exilim",
    "ricoh", "理光",
    "kodak", "柯达",
    "samsung", "三星",
    "pentax", "宾得",
)

XD_BRAND_ALIASES: tuple[str, ...] = (
    "fuji", "fujifilm", "finepix", "富士",
    "olympus", "奥林巴斯", "mju", "stylus",
)


def _contains_alias(text: str, aliases: tuple[str, ...]) -> bool:
    low = (text or "").lower()
    for alias in aliases:
        alias_low = alias.lower()
        if alias_low.isascii() and alias_low.isalnum():
            if re.search(r"(?<![a-z0-9])" + re.escape(alias_low) + r"(?![a-z0-9])", low):
                return True
        elif alias_low in low:
            return True
    return False


def _has_non_xd_brand_context(text: str) -> bool:
    return _contains_alias(text, NON_XD_BRAND_ALIASES) and not _contains_alias(text, XD_BRAND_ALIASES)


def _normalize(text: str) -> str:
    """将关键词标准化：小写、去除空格和连字符、μ→mu"""
    text = text.lower()
    # 希腊字母 μ (U+03BC) 替换为 mu
    text = text.replace("\u03bc", "mu")
    # 注意：Olympus 的 "u" -> "mu" 转换不在这里做，
    # 而是在 _extract_model_tokens 里单独处理（避免破坏 fuji/fujifilm 等词）
    return re.sub(r"[\s\-–—_]", "", text)


def _extract_model_tokens(text: str) -> set[str]:
    """
    从关键词中提取所有可能的机型标识符。

    核心兼容性处理：
    - Olympus u 系列：olympus 与 u 之间有/无空格均可
    - 希腊字母 μ 和英文字母 u 均映射到 mu
    - 连写格式：olympusfe140 / fujife200exr（品牌+型号无空格）
    - 中文字符与英文之间 \b 边界不生效，需要用 (?<![a-z])...(?![a-z])
    """
    low = text.lower()
    tokens: set[str] = set()

    # 1. 希腊字母 μ (U+03BC) 替换为 mu
    low = low.replace("\u03bc", "mu")

    # 2. Olympus "u####" 替换（low 层面：处理 olympus u1060 / olympusu1060）
    for prefix in ("olympus",):
        low = re.sub(rf"(?<={prefix})\s*mu\s*(?=\d{{3,4}})", "mu", low)
        low = re.sub(rf"(?<={prefix})\s*u\s*(?=\d{{3,4}})", "mu", low)
    # 中文"奥林巴斯"后跟 u/mu/μ
    low = re.sub(r"(?<=奥林巴斯)\s*mu\s*(?=\d{3,4})", "mu", low)
    low = re.sub(r"(?<=奥林巴斯)\s*u\s*(?=\d{3,4})", "mu", low)
    low = low.replace("奥林巴斯\u03bc", "奥林巴斯mu")

    # 3. Olympus u#### 格式提取（mu1060）
    for u_re in [
        r"olympus\s*mu\s*(\d{3,4}[a-z]?)\b",
        r"olympus\s*u\s*(\d{3,4}[a-z]?)\b",
        r"奥林巴斯\s*mu\s*(\d{3,4}[a-z]?)\b",
        r"奥林巴斯\s*u\s*(\d{3,4}[a-z]?)\b",
    ]:
        m = re.search(u_re, low)
        if m:
            tokens.add(f"mu{m.group(1)}")

    # 4. 有分隔符的型号（fe-140, z5fd, a400）
    # \b 在中文字符旁不工作，改用 (?<![a-z])...(?![a-z])
    # \d{1,6} 兼容 z5fd（1位数字）
    raw_tokens = re.findall(
        r"(?<![a-z])[a-z]{1,4}[- ]+\d{1,6}[a-z]{0,3}(?![a-z])",
        low, flags=re.IGNORECASE,
    )
    for t in raw_tokens:
        clean = _normalize(t)
        if len(clean) >= 4:
            tokens.add(clean)
            # 修正富士 f200exr -> ff200exr -> f200exr
            if clean.startswith("ff"):
                tokens.add(clean[1:])

    # 5. 无空格连写兜底（stripped = 纯 ASCII 字母数字）
    stripped = re.sub(r"[^a-z0-9]", "", low)
    # Olympus FE/mu/Stylus 无空格
    for m in re.finditer(
        r"(?:olympus)(fe|mu|stylus)(\d{2,4}[a-z]?)", stripped, flags=re.IGNORECASE
    ):
        tokens.add(f"{m.group(1)}{m.group(2)}")
    # Fuji FE/A/F/J/Z 无空格
    for m in re.finditer(
        r"(?:fuji)(fe|a|f|j|z|s|jx)(\d{2,4}[a-z]?)", stripped, flags=re.IGNORECASE
    ):
        candidate = f"{m.group(1)}{m.group(2)}"
        tokens.add(candidate)
        # 回溯减少数字位数（如 fe200exr -> fe20exr -> fe2exr -> fe200 -> fe20）
        while len(candidate) > 4:
            num_part = candidate[len(m.group(1)):]
            if len(num_part) <= 2:
                break
            # 去掉最后一个数字
            candidate = candidate[:-1]
            tokens.add(candidate)
    # 中文"富士" + 型号无空格
    for m in re.finditer(
        r"(?:富士)(fe|a|f|j|z|s|jx)(\d{2,4}[a-z]?)", low, flags=re.IGNORECASE
    ):
        tokens.add(f"{m.group(1)}{m.group(2)}")
    # 中文"奥林巴斯" + 型号无空格
    for m in re.finditer(
        r"(?:奥林巴斯)(fe|mu|stylus)(\d{2,4}[a-z]?)", low, flags=re.IGNORECASE
    ):
        tokens.add(f"{m.group(1)}{m.group(2)}")

    # 6. 独立 u#### / mu#### / Stylus#####（无品牌前缀）
    for m in re.finditer(r"\bu\s*(\d{3,4}[a-z]?)\b", stripped, flags=re.IGNORECASE):
        tokens.add(f"mu{m.group(1)}")
    for m in re.finditer(r"\bmu\s*(\d{3,4}[a-z]?)\b", stripped, flags=re.IGNORECASE):
        tokens.add(f"mu{m.group(1)}")
    for m in re.finditer(r"^stylus\s*(\d{3,4}[a-z]?)$", stripped, flags=re.IGNORECASE):
        tokens.add(f"stylus{m.group(1)}")

    # 7. 品牌前缀增强（已有 token 时加上品牌前缀）
    has_olympus = "olympus" in low or "奥林巴斯" in text
    has_fuji = "fuji" in low or "finepix" in low or "富士" in text
    for t in list(tokens):
        if has_fuji:
            tokens.add(f"fuji {t}")
            tokens.add(f"finepix {t}")
        if has_olympus:
            tokens.add(f"olympus {t}")

    return tokens


def _model_parts(token: str) -> tuple[str, str, str] | None:
    match = re.fullmatch(r"([a-z]{1,8})(\d{1,6})([a-z]{0,5})", token or "")
    if not match:
        return None
    prefix, number, suffix = match.groups()
    return prefix, number.lstrip("0") or "0", suffix


def _model_token_compatible(query_token: str, xd_model_token: str) -> bool:
    query_norm = _normalize(query_token)
    model_norm = _normalize(xd_model_token)
    if query_norm == model_norm:
        return True

    query_parts = _model_parts(query_norm)
    model_parts = _model_parts(model_norm)
    if not query_parts or not model_parts:
        return False

    query_prefix, query_number, query_suffix = query_parts
    model_prefix, model_number, model_suffix = model_parts
    if query_prefix != model_prefix or query_number != model_number:
        return False

    # WHY: allow incomplete suffix searches like "富士 z5" -> "z5fd", while
    # rejecting numeric-prefix collisions like "z3000" -> Fuji "z3".
    return not query_suffix or model_suffix.startswith(query_suffix)


def _ascii_model_candidates(keyword: str) -> set[str]:
    normalized = _normalize(keyword)
    ascii_only = re.sub(r"[^a-z0-9]", "", normalized)
    candidates = {ascii_only} if ascii_only else set()
    for prefix in ("finepix", "fujifilm", "fuji", "olympus"):
        if ascii_only.startswith(prefix) and len(ascii_only) > len(prefix):
            candidates.add(ascii_only[len(prefix):])
    return {candidate for candidate in candidates if _model_parts(candidate)}


def is_xd_card_model(keyword: str) -> bool:
    """
    根据关键词判断该 CCD 是否为使用 xD 卡的机型。

    判断逻辑（两级）：
    1. 关键词预判：从关键词提取机型标识，在 xD 机型数据库中匹配
       - 匹配到 -> 返回 True（高可信）
       - 未匹配到 -> 进入第 2 步
    2. 样本描述兜底：在后续爬取完成后，通过样本标题/描述进一步确认
       （由调用方通过 detect_xd_card_model_from_items 完成）

    数据来源：
    - Olympus 官网兼容性列表（support.jp.omsystem.com）
    - Wikipedia FinePix 系列词条
    - Wikipedia XD-Picture Card 词条

    Args:
        keyword: 用户输入的搜索关键词，如 "富士 F200EXR"、"olympus fe-140"

    Returns:
        True: 关键词明确命中 xD 机型数据库
        False: 关键词未命中，交给样本描述兜底判断
    """
    if not keyword:
        return False

    if _has_non_xd_brand_context(keyword):
        return False

    tokens = _extract_model_tokens(keyword)
    # 数据库 key 有各种格式（有空格如"mu 1060"、有连字符如"fe-140"），
    # 提取的 token 是无分隔符格式（如"mu1060"、"fe140"）。
    # 所以匹配时两边都要规范化
    normalized_tokens = {_normalize(t) for t in tokens}
    # 预计算规范化的数据库 key 集合（模块加载时一次性生成）
    if not hasattr(is_xd_card_model, "_norm_models"):
        is_xd_card_model._norm_models = {_normalize(k) for k in ALL_XD_MODELS}
        is_xd_card_model._norm_variants = {_normalize(k) for k in ALL_XD_MODEL_VARIANTS}
    for token in normalized_tokens:
        if token in is_xd_card_model._norm_models:
            return True
        if token in is_xd_card_model._norm_variants:
            return True

    # 原始 token 直接查 VARIANTS（有精确匹配如 "olympus fe-140"）
    for token in tokens:
        if token in ALL_XD_MODEL_VARIANTS:
            return True

    # WHY: this fallback supports shorthand searches such as "富士z5" matching
    # "z5fd", but it compares complete numeric model fields to avoid treating
    # "z3000" as Fuji "z3".
    for candidate in _ascii_model_candidates(keyword):
        for model_norm in is_xd_card_model._norm_models:
            if _model_token_compatible(candidate, model_norm):
                return True

    return False


def is_masd1_compatible_model(keyword: str) -> tuple[bool, bool]:
    """
    判断相机机型是否支持 MASD-1 xD 卡套（microSD 替代方案）。

    仅对已确认的 xD 卡相机进行检测，富士机型不支持 MASD-1。

    判断逻辑：
    1. 首先确认是否为 xD 卡机型（调用 is_xd_card_model）
    2. 如果是奥林巴斯 xD 机型，再进一步匹配 MASD-1 兼容数据库
    3. 如果是富士 xD 机型，直接返回 False（富士不支持 MASD-1）

    数据来源：
    - Olympus 官网 MASD-1 兼容列表（2010年8月更新）
    - Retro Digitals / Memorypack 兼容数据

    Args:
        keyword: 用户输入的搜索关键词，如 "奥林巴斯 μ 1030SW"、"olympus fe-3000"

    Returns:
        tuple[bool, bool]: (is_compatible, panorama_blocked)
            - is_compatible: True 表示支持 MASD-1 卡套
            - panorama_blocked: True 表示使用卡套时全景功能不可用（仅在 is_compatible=True 时有效）
        例如：(True, False) = 支持卡套，全景正常
              (True, True)  = 支持卡套，但全景功能不可用
              (False, False) = 不支持 MASD-1 卡套
    """
    if not keyword:
        return False, False

    if not is_xd_card_model(keyword):
        return False, False

    tokens = _extract_model_tokens(keyword)
    normalized_tokens = {_normalize(t) for t in tokens}

    if not hasattr(is_masd1_compatible_model, "_norm_models"):
        is_masd1_compatible_model._norm_models = {_normalize(k) for k in OLYMPUS_MASD1_ALL}
        is_masd1_compatible_model._norm_variants = {_normalize(k) for k in OLYMPUS_MASD1_ALL_VARIANTS}

    matched_token = None
    for token in normalized_tokens:
        if token in is_masd1_compatible_model._norm_models:
            matched_token = token
            break
        if token in is_masd1_compatible_model._norm_variants:
            matched_token = token
            break

    if matched_token is None:
        for token in tokens:
            if token in OLYMPUS_MASD1_ALL_VARIANTS:
                matched_token = token
                break

    if matched_token is None:
        normalized = _normalize(keyword)
        for model_norm in is_masd1_compatible_model._norm_models:
            if model_norm in normalized or normalized in model_norm:
                matched_token = model_norm
                break

    if matched_token is None:
        return False, False

    PANORAMA_BLOCKED_MODELS = {
        "mu840", "stylus840",
        "mu850sw", "stylus850sw",
        "mu1010", "stylus1010",
        "mu1020", "stylus1020",
        "mu1030sw", "stylus1030sw",
        "mu1040", "stylus1040",
        "mu1050sw", "stylus1050sw",
        "mu1060", "stylus1060",
        "fe20",
        "fe360",
        "fe370",
        "sp565uz",
    }

    norm_matched = _normalize(matched_token)
    for blocked in PANORAMA_BLOCKED_MODELS:
        if blocked in norm_matched or norm_matched in blocked:
            return True, True

    return True, False
