"""CCD domain knowledge — seed documents for RAG ingestion.

Covers: camera specs, storage cards (xD, SD, CF, MS), common faults,
pricing rules, and business logic.  Used by ingestion.py to bootstrap
the Qdrant knowledge base.

Sources: internal verified, Xianyu market observation, manual research.
"""
from __future__ import annotations

# ── Storage card knowledge ──

STORAGE_KNOWLEDGE = [
    {
        "document_id": "storage_xd_card_overview",
        "document_type": "camera_knowledge",
        "topic": "storage_card",
        "content": """【xD Picture Card 存储卡概述】

xD卡（eXtreme Digital Picture Card）是富士胶片和奥林巴斯在2002年联合推出的
存储卡标准，广泛用于2000年代中后期的数码相机。

容量范围：16MB ~ 2GB（Type M/H），后期 Type M+ 可达 2GB。
兼容性：xF卡只能在 xD 卡槽中使用，不支持 SD 卡槽。
读取速度：Type M 约 4MB/s，Type H 约 10MB/s。

常见品牌：富士（Fujifilm）、奥林巴斯（Olympus）原厂 xD卡。
后期有第三方品牌如 SanDisk 也生产过少量 xD卡。

⚠ 注意事项：
- xD卡已经停产，新卡价格远高于二手Camera本身
- 市面上大部分 xD卡是二手、拆机卡
- 奥林巴斯 MASD-1 是微型 xD 卡适配器，可让 microSD 在 xD 卡槽中使用
- 购买二手 CCD 相机时确认是否附带存储卡，单买卡可能比相机还贵""",
    },
    {
        "document_id": "storage_xd_card_pricing",
        "document_type": "camera_knowledge",
        "topic": "storage_card",
        "content": """【xD 卡二手市场价格参考】

富士/奥林巴斯原厂 xD卡：
- 16MB：¥5-10（无实用价值）
- 64MB：¥10-20
- 128MB：¥15-25
- 256MB：¥20-35
- 512MB：¥30-50
- 1GB：¥45-70
- 2GB（Type M+）：¥60-100

第三方/杂牌 xD卡：价格约为原厂 50-70%

⚠ 估价原则：
- 裸机（无卡）：市场价格扣减 0
- 带小容量卡（≤256MB）：计入 +¥15-25
- 带中容量卡（512MB-1GB）：计入 +¥30-50
- 带大容量卡（2GB）：计入 +¥50-80
- 带 MASD-1 卡套：计入 +¥25-40""",
    },
    {
        "document_id": "storage_masd1_adapter",
        "document_type": "camera_knowledge",
        "topic": "storage_card",
        "content": """【奥林巴斯 MASD-1 卡套】

MASD-1 是奥林巴斯推出的 microSD 转 xD 卡适配器。
可将 microSD 卡插入 MASD-1，然后在 xD 卡槽中使用。

兼容性：
- 仅支持奥林巴斯部分机型（FE系列、μ系列后期型号）
- 富士相机基本不兼容 MASD-1
- 使用前务必确认机型兼容性

市场价值：
- MASD-1 卡套单独售价：¥25-40
- 搭配 microSD 卡可大幅降低存储成本
- 二手市场上 MASD-1 较稀缺""",
    },
    {
        "document_id": "storage_sd_cf_ms_overview",
        "document_type": "camera_knowledge",
        "topic": "storage_card",
        "content": """【其他存储卡类型概述】

SD卡：最通用的存储卡类型，广泛用于佳能 IXUS、PowerShot、索尼 W/T 系列、
尼康 COOLPIX、松下 Lumix、卡西欧 Exilim 等。

CF卡（CompactFlash）：用于早期专业级数码单反和高档消费相机。
部分早期 CCD 相机如佳能 PowerShot G 系列使用 CF 卡。

MS卡（Memory Stick）：索尼专有标准，用于索尼 P/T/W 系列 CCD 相机。
包括 MS、MS Duo、MS PRO Duo 等多种变体。

MS PRO Duo 可通过适配器在标准 MS 卡槽中使用。

⚠ 估价原则：
- SD卡极便宜（¥5-20），不显著影响相机估价
- CF卡价格略高于SD卡
- 索尼 MS 卡比 SD 贵，原厂 MS PRO Duo 价格 ¥20-50""",
    },
]

# ── Camera model knowledge ──

CAMERA_KNOWLEDGE = [
    {
        "document_id": "camera_canon_ixus_series",
        "brand": "Canon",
        "model": "IXUS",
        "document_type": "camera_knowledge",
        "topic": "spec",
        "content": """【佳能 IXUS 系列 CCD 相机】

佳能 IXUS 系列（北美称 ELPH）是 2000 年代最畅销的时尚卡片机系列。
全部使用 CCD 传感器，SD 卡存储。

热门型号：
- IXUS 130 / 120 IS / 110 IS：1/2.3英寸 CCD，1400万像素
- IXUS 105 / 100 IS：1200万像素，性价比高
- IXUS 95 IS / 90 IS：1000万像素，经典款
- IXUS 80 IS / 75：800万像素，入门级

特点：
- 全金属机身，做工精致
- DIGIC 4 图像处理器
- 光学防抖（IS 型号）
- 锂离子电池 NB-4L / NB-6L

常见故障：
- 电池仓接触不良
- 镜头伸缩卡顿（排线问题）
- 屏幕老化（偏色/暗角）
- 闪光灯电容老化""",
    },
    {
        "document_id": "camera_sony_t_series",
        "brand": "Sony",
        "model": "T系列",
        "document_type": "camera_knowledge",
        "topic": "spec",
        "content": """【索尼 Cyber-shot T 系列 CCD 相机】

索尼 T 系列以超薄滑盖设计闻名，是 CCD 时代的工业设计标杆。
全部使用 CCD 传感器，MS Duo 存储卡。

热门型号：
- DSC-T900 / T90：1200万像素，3.5英寸触摸屏
- DSC-T700 / T77：1000万像素，4GB 内置存储
- DSC-T300 / T200：800-1000万像素，5倍变焦
- DSC-T100 / T50 / T30：经典滑盖设计
- DSC-T9 / T7 / T5 / T3 / T1：早期型号

特点：
- 滑盖开关机，设计优雅
- 卡尔·蔡司（Carl Zeiss）镜头
- Super SteadyShot 光学防抖
- 触摸屏（部分后期型号）

常见故障：
- 滑盖排线断裂（最常见）
- 触摸屏失灵（T900/T90）
- MS 卡读取异常
- 电池 NP-BD1 / NP-FD1 老化""",
    },
    {
        "document_id": "camera_fuji_finepix",
        "brand": "Fujifilm",
        "model": "FinePix",
        "document_type": "camera_knowledge",
        "topic": "spec",
        "content": """【富士 FinePix 系列 CCD 相机】

富士 FinePix 系列以 Super CCD 和胶片模拟色彩著称。
部分型号使用 xD 卡存储。

热门型号：
- FinePix F30 / F31fd：Super CCD HR VI，高感之王
- FinePix F200EXR / F100fd：Super CCD EXR
- FinePix F10 / F11 / F20：经典高感系列
- FinePix Z 系列：超薄时尚
- FinePix A 系列：入门级（用 SD 卡）

存储卡：
- F 系列 F10-F31fd：xD 卡
- F 系列 F100fd 及以后：SD 卡
- Z 系列：xD 卡
- A 系列：SD 卡或 xD 卡

⚠ xD 卡风险：
- 富士 F30/F31fd 只支持 xD 卡，无 SD 卡槽
- 市面上 xD 卡越来越稀少，价格走高
- 购买前务必确认是否附带存储卡

常见故障：
- xD 卡槽接触不良
- 电池 NP-95 老化
- 液晶屏老化""",
    },
    {
        "document_id": "camera_olympus_mju",
        "brand": "Olympus",
        "model": "μ系列",
        "document_type": "camera_knowledge",
        "topic": "spec",
        "content": """【奥林巴斯 μ（mju）系列 CCD 相机】

奥林巴斯 μ 系列以生活防水和精致设计著称。
早期型号使用 xD 卡，后期部分型号支持 MASD-1。

热门型号：
- μ 1030SW / 850SW：三防（防水/防震/防冻）
- μ 1020 / 1010 / 1000：1000万像素
- μ 840 / 830 / 820：800万像素
- μ 790SW / 770SW：防水系列
- μ 750 / 740 / 730：700万像素

存储卡：
- 大部分 μ 系列使用 xD 卡
- μ 1030SW 及后期型号支持 MASD-1 卡套
- 可通过 MASD-1 使用 microSD 卡

⚠ 注意事项：
- 防水型号的密封圈老化可能导致漏水
- xD 卡槽故障率较高
- 镜头排线故障（μ 840 系列常见）""",
    },
    {
        "document_id": "camera_nikon_coolpix",
        "brand": "Nikon",
        "model": "COOLPIX",
        "document_type": "camera_knowledge",
        "topic": "spec",
        "content": """【尼康 COOLPIX 系列 CCD 相机】

尼康 COOLPIX 系列以优秀的成像质量和简洁设计著称。
全部使用 SD 卡存储。

热门型号：
- COOLPIX S 系列：超薄时尚（S5100/S4000/S3000/S220/S210）
- COOLPIX L 系列：入门长焦（L20/L19/L16）
- COOLPIX P 系列：高性能便携（P5100/P5000）

特点：
- NIKKOR 尼克尔镜头
- VR 光学防抖（部分型号）
- AA 电池供电（L 系列）
- SD 卡存储（通用性强）

常见故障：
- 镜头伸缩异常
- 模式拨盘松动
- 电池仓弹簧老化（AA 电池机型）""",
    },
    {
        "document_id": "camera_panasonic_lumix",
        "brand": "Panasonic",
        "model": "Lumix",
        "document_type": "camera_knowledge",
        "topic": "spec",
        "content": """【松下 Lumix 系列 CCD 相机】

松下 Lumix 以徕卡镜头和优秀的图像处理引擎著称。
全部使用 SD 卡存储。

热门型号：
- DMC-FX 系列：超薄时尚（FX30/FX33/FX55/FX100）
- DMC-FS 系列：入门级（FS3/FS5/FS20）
- DMC-FZ 系列：长焦（FZ8/FZ18/FZ28）
- DMC-LX 系列：高端便携（LX3/LX2/LX1）

特点：
- 徕卡 DC VARIO-ELMARIT 镜头
- Mega O.I.S. 光学防抖
- Venus Engine 图像处理器
- 部分型号支持 RAW 拍摄

常见故障：
- 防抖组件异响
- 镜头盖不闭合
- 模式转盘漂移""",
    },
]

# ── Fault / risk knowledge ──

FAULT_KNOWLEDGE = [
    {
        "document_id": "fault_lens_stuck",
        "document_type": "camera_knowledge",
        "topic": "fault",
        "content": """【常见故障：镜头伸缩卡顿/不伸出】

症状：开机后镜头不伸出、反复伸缩、发出异响后自动关机。

常见原因：
1. 排线断裂（最普遍）：镜头伸缩排线长期弯折导致断裂
2. 齿轮卡死：镜头变焦齿轮组进入异物或磨损
3. 电机故障：镜头驱动电机老化

维修成本：
- 排线更换：¥80-150（需焊接）
- 镜头模组更换：¥150-300
- 维修后可靠性：约 70%（可能再次故障）

⚠ 购买建议：
- 确认镜头伸缩顺畅、无杂音
- 测试变焦全程（近→远→近）
- 镜头故障机价格应扣减 ¥100-200""",
    },
    {
        "document_id": "fault_screen_aging",
        "document_type": "camera_knowledge",
        "topic": "fault",
        "content": """【常见故障：屏幕老化/偏色/暗角】

症状：屏幕发黄、偏绿、亮度下降、四角发暗、显示横线。

常见原因：
1. CCFL 背光灯管老化（老款 CCD 相机使用 CCFL 背光）
2. LCD 偏光膜老化（高温环境下加速）
3. 排线接触不良

维修成本：
- 屏幕总成更换：¥100-200（拆机件）
- 偏光膜更换：¥50-80

⚠ 购买建议：
- 轻微偏色不影响使用，可适当砍价（-¥30-50）
- 严重老化（无法看清构图）应扣减 ¥100-150
- 注意区分屏幕老化和 CCD 传感器老化（后者成像也会偏色）""",
    },
    {
        "document_id": "fault_battery_aging",
        "document_type": "camera_knowledge",
        "topic": "fault",
        "content": """【常见故障：电池老化/不蓄电】

症状：充满电拍几张就关机、待机时间短、电池鼓包。

原因：
- 锂离子电池寿命约 2-3 年（300-500 次循环）
- CCD 相机距今已 15-20 年，原装电池几乎全部老化
- 第三方电池质量参差不齐

更换成本：
- 第三方兼容电池：¥15-30
- 原装拆机电池：¥30-60（已老化）
- 少数可买到全新原装电池：¥50-100+

⚠ 购买建议：
- 询问是否附带电池和充电器
- 最好能测试实际拍摄几张
- 无电池充电器的机器价格应扣减 ¥30-50""",
    },
    {
        "document_id": "fault_xd_card_slot",
        "document_type": "camera_knowledge",
        "topic": "fault",
        "content": """【常见故障：xD 卡槽接触不良】

症状：插入 xD 卡后提示"卡错误"、"未插入卡"、间歇性无法识别。

原因：
- xD 卡槽触点氧化（高发）
- 卡槽弹簧片变形
- 卡槽焊接点虚焊

维修成本：
- 触点清洁：¥30-50
- 卡槽更换：¥80-150

⚠ 购买建议：
- 必须测试 xD 卡插入后能否正常识别和读写
- 富士 F30/F31fd 等 xD Only 机型务必验证
- 卡槽故障机价格应扣减 ¥80-150""",
    },
]

# ── Pricing rules ──

PRICING_RULES = [
    {
        "document_id": "rule_accessory_deduction",
        "document_type": "rule",
        "topic": "pricing",
        "content": """【估价规则：配件和成色修正】

裸机（无任何附件）：基础估价扣减 10-15%
带原装电池+充电器：基础估价不变
带包装盒+说明书：+5-10%
带原装配件齐全（箱说全）：+15-20%

成色修正：
- 99新（几乎无使用痕迹）：+10-15%
- 95新（轻微使用痕迹）：+5%
- 9成新（正常使用痕迹）：基准价
- 8成新（明显痕迹/小划痕）：-5-10%
- 7成新（明显磨损/掉漆）：-15-20%
- 6成新及以下（功能正常但外观差）：-25-30%""",
    },
    {
        "document_id": "rule_bait_filtering",
        "document_type": "rule",
        "topic": "pricing",
        "content": """【估价规则：低价引流/异常价格过滤】

以下类型商品不纳入正常估价样本：

1. 盲盒/福袋/随机发货（标题含"盲盒""福袋""随机"）
2. 低价引流（价格低于型号均价 40%，且标题含"配件""维修"等）
3. 出租/租赁（标题含"出租""免押""租赁""租金"）
4. 咨询/辨真假（标题含"咨询""辨真假""鉴定"）
5. 配件/耗材（主机标题但描述为"单电池""充电器""数据线"）
6. 回收/求购（标题含"回收""求购""收购""高价回收"）

过滤逻辑：IQR 去极值 + 业务规则双层过滤""",
    },
    {
        "document_id": "rule_iqr_pricing",
        "document_type": "rule",
        "topic": "pricing",
        "content": """【估价规则：IQR 去极值与加权中位数】

1. 收集目标型号近期有效样本（默认 40 条）
2. 按价格排序，计算 Q1（25百分位）、Q3（75百分位）
3. IQR = Q3 - Q1
4. 过滤异常值：价格 < Q1 - 1.5*IQR 或 > Q3 + 1.5*IQR
5. 对保留样本按成色、质量评分加权
6. 取加权中位数作为基准估价
7. 估价区间 = [中位数 * 0.85, 中位数 * 1.15]

置信度：
- 样本量 ≥ 20：高置信度
- 样本量 10-19：中等置信度
- 样本量 5-9：低置信度（标注）
- 样本量 < 5：不足以估价""",
    },
]

# ── FAQ ──

FAQ_KNOWLEDGE = [
    {
        "document_id": "faq_what_is_ccd",
        "document_type": "faq",
        "topic": "general",
        "content": """【什么是 CCD 相机？】

CCD（Charge-Coupled Device）是一种图像传感器技术，2000年代广泛用于数码相机。

与 CMOS 的区别：
- CCD 成像色彩更浓郁，有独特的"胶片感"
- CMOS 功耗更低、读取速度更快（现代手机/相机主流）

为什么 CCD 相机重新流行：
- 复古成像风格（低像素、高噪点、色彩偏移）
- 小红书/抖音复古摄影潮流
- 价格便宜，入门门槛低

⚠ 购买提醒：
- CCD 相机均已停产 15-20 年，无保修
- 电子元件老化是必然的
- 确认功能正常再购买""",
    },
    {
        "document_id": "faq_how_to_inspect",
        "document_type": "faq",
        "topic": "general",
        "content": """【购买二手 CCD 相机的验机步骤】

1. 外观检查：屏幕有无划痕、机身有无磕碰、电池仓有无腐蚀
2. 镜头检查：伸缩是否顺畅、有无异响、镜片有无霉斑
3. 屏幕检查：有无老化偏色、坏点、横线
4. 拍摄测试：拍几张照片检查成像是否正常
5. 闪光灯测试：闪光灯是否正常触发
6. 按键测试：所有按键、拨盘是否灵敏
7. 存储卡测试：插拔卡、格式化、读写
8. 电池测试：充满电后能拍多少张
9. 接口测试：USB/AV 输出是否正常（如有）

⚠ 闲鱼交易建议：
- 要求卖家拍摄验机视频
- 走平台交易，不直接转账
- 确认退换货政策""",
    },
]


# ── Aggregate all seed documents ──

def get_all_seed_documents() -> list[dict]:
    """Return all seed documents for initial knowledge base ingestion."""
    return STORAGE_KNOWLEDGE + CAMERA_KNOWLEDGE + FAULT_KNOWLEDGE + PRICING_RULES + FAQ_KNOWLEDGE
