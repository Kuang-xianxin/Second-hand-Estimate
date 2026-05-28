---
name: ccd-model-database
description: CCD相机全型号数据库维护技能。覆盖富士、奥林巴斯、佳能、索尼、尼康、松下、卡西欧等全部CCD品牌型号数据。当需要查询CCD相机型号列表、扩展型号数据库、生成爬取关键词、或为估价系统补充型号覆盖时使用此技能。
---

# CCD 相机全型号数据库

## 数据位置

完整型号数据库在 [reference.md](reference.md)，包含所有品牌的型号清单、价格区间、内存卡类型。

## 品牌覆盖范围

| 品牌 | 系列 | 内存卡 | 估价特性 |
|------|------|--------|----------|
## 品牌覆盖范围

| 品牌 | 系列 | 型号数 | 内存卡 | 估价特性 |
|------|------|--------|--------|---------|
| 佳能 Canon | Digital IXUS / IXY / ELPH / SD | ~63 | SD | 闲鱼最热门，均价最高 |
| 佳能 Canon | PowerShot A | ~54 | SD | 入门家用，价格实惠 |
| 佳能 Canon | PowerShot SX | ~37 | SD | 长焦系列，价格跨度大 |
| 索尼 Sony | Cyber-shot T / TX | ~33 | MS | 热门品牌，触屏经典 |
| 索尼 Sony | Cyber-shot W / WX | ~72 | MS/SD | 热门品牌，型号众多 |
| 索尼 Sony | Cyber-shot H / P / M / S / N | ~44 | MS | 长焦/小众/早期型号 |
| 尼康 Nikon | Coolpix S | ~75 | SD | 时尚超薄，型号极多 |
| 尼康 Nikon | Coolpix L | ~33 | SD | 入门系列 |
| 松下 Panasonic | Lumix FX | ~26 | SD | 时尚系列，德味口碑 |
| 卡西欧 Casio | Exilim（Z/H/FC/FS/TR/ZR系列） | ~70 | SD | 热门品牌，TR自拍神器 |
| 三星 Samsung | NV / ST / MV / WB | ~60 | SD | 小众但有忠实用户 |
| 富士 Fujifilm | FinePix xD（A/F/S/Z/J/E） | ~104 | xD | xD 卡捆绑价值高 |
| 奥林巴斯 Olympus | μ/Stylus/FE/SP（xD） | ~128 | xD | MASD-1 卡套可替代 |
| 宾得 Pentax | Optio | ~25 | SD | 市场小众 |
| 柯达 Kodak | EasyShare | ~38 | SD | 市场小众 |
| **合计** | | **~852** | | |

**全量更新策略**：每 1.5 小时对全部 676 个 CCD 型号（2003 个搜索关键词）进行全量爬取，不分层级。

## 添加新品牌的流程

1. 查阅品牌 Wikipedia 页面确认 CCD 传感器型号列表
2. 确认传感器切换时间点（CCD → CMOS，通常 2010-2012 年）
3. 查阅 `reference.md` 确认品牌章节格式
4. 补充品牌型号到 `reference.md`
5. 更新 `reference.md` 品牌覆盖表格
6. 运行验证：`python .cursor/skills/ccd-model-database/scripts/validate.py`

## 型号数据格式

每个型号至少包含：`型号名` / `像素` / `变焦` / `上市年份` / `内存卡类型`

可选补充：`咸鱼活跃度`（高/中/低）、`热门搜索关键词`、`价格区间`

## 搜索关键词生成规则

### 佳能 IXUS / IXY / ELPH / SD 系列——跨地区同名异名

同一机型在不同地区有不同命名（IXUS = 欧洲/国际，ELPH/SD = 北美，IXY = 日本），搜索时**必须同时包含所有别名**，否则会遗漏 20-30% 的 listing。具体对照表见 `reference.md` 附带的完整别名对照。

### 索尼 Cyber-shot T / TX / W 系列——全球统一型号 + 日文品牌名

索尼型号编号（ DSC-T70、DSC-TX9、DSC-W170 等）**全球统一**，无地区别名。但需注意：
- 日本闲鱼卖家常用日文品牌名 `サイバーショット` 代替 `Cyber-shot`
- TX 系列（触屏）与 T 系列（按钮）是同一硬件的不同形态，需**分开爬取**

详细说明见 `reference.md` 索尼系列章节。

### 通用关键词生成规则

估价爬取需要为每个型号生成 3-5 个搜索关键词：

```
佳能 IXUS 130 → [
    "佳能 IXUS 130",
    "canon ixus 130",
    "IXUS130",
    "ixus 130",
]

索尼 DSC-T70 → [
    "索尼T70",
    "sony t70",
    "dsc-t70",
    "t70",
    "サイバーショット T70",     # 日文名
]
```

关键词格式优先使用**中文品牌 + 型号**（覆盖最多中文 listing），英文名作为补充。

## 验证清单

- [ ] 型号数量与 Wikipedia 记录一致
- [ ] CCD → CMOS 切换时间点标注正确
- [ ] 内存卡类型与官方规格一致
- [ ] 搜索关键词可覆盖闲鱼主流 listing
- [ ] 价格区间参考闲鱼实际成交价

## 参考来源

- 品牌官网兼容性列表
- Wikipedia 词条
- DPReview / Imaging Resource 评测数据库
- 闲鱼实时搜索结果
- 色影无忌 / 蜂鸟网论坛报价帖

## 与 ccd-memory-card 技能的关系

`ccd-memory-card` 技能专注 xD 卡机型细节（MASD-1 卡套、卡价值评估）。本技能负责全品牌全型号数据库，两者互补。估价逻辑中先查本库确认品牌型号，再查 `ccd-memory-card` 获取 xD 卡附加价值。
