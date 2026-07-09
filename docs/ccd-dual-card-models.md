# CCD 双卡兼容机型与“卡状态待确认”规则

资料调查日期：2026-06-25
规则修订日期：2026-06-26

## 目的

这份文档只解决一个问题：在已经确认相机属于 xD 卡机型以后，哪些“xD + SD/SDHC 双兼容”相机遇到“没有明确说明卡状态或卡类型”的描述时，需要打待人工确认标识。

建议标识名使用 `card_status_uncertain_needs_confirm`。如果代码暂时沿用旧名 `ambiguous_card_bundle`，它的含义也应扩展为“卡状态/卡类型待确认”，不再只表示“疑似带卡”。该标识只用于提醒人工核对，不计入 xD 卡价值，也不叠加到捡漏利润。

## 判定树

代码实现时不能直接从“带卡”或“未写卡状态”进入待确认标识，必须按下面顺序判断。

### 第 1 步：先确认是否是 xD 卡机型

入口必须是现有 xD 机型识别逻辑，例如 `is_xd_card_model(keyword)` 或样本兜底后的 xD 机型确认。

- 不是 xD 卡机型：直接退出 xD 卡逻辑，不打卡状态待确认标识。
- 是 xD 卡机型：进入第 2 步。

### 第 2 步：区分 xD 机型类型

已确认是 xD 卡机型后，再分三类：

- `xd_only`：只能用 xD 卡。继续按原有 xD 卡逻辑判断，不打双卡专用的卡状态待确认标识。
- `direct_xd_sd_dual`：相机卡槽直接支持 xD + SD/SDHC。只有这一类才进入第 3 步。
- `masd1_adapter_supported`：通过 MASD-1 卡套使用 microSD，不等于原生 SD 卡槽。不要复用双卡直插逻辑，后续如需要应单独设计 MASD-1 待确认状态。

### 第 3 步：只对 direct_xd_sd_dual 判断卡类型证据

只有同时满足以下条件，才打卡状态待确认标识：

1. 机型已确认是 `direct_xd_sd_dual`。
2. 商品文字没有明确表示不带卡或卡需自备，例如“单机”“不带卡”“不含卡”“无卡”“自备卡”“需自备内存卡”。
3. 商品文字没有明确出现 xD / XD / xD-Picture Card / 富士卡 / 奥林巴斯原装卡。
4. 商品文字没有明确出现 SD / SDHC / TF / microSD / 闪迪 SD 等普通 SD 线索。
5. 图片识别没有确认卡面是 xD 或 SD。

满足这些条件时，不管标题是“带卡/送卡”这种泛称，还是完全没写带不带卡，都应提示用户人工确认。

不满足以上条件时：

- 明确 xD：按 xD 卡容量估值。
- 明确 SD / SDHC / TF / microSD：不计入 xD 卡价值。
- 明确不带卡或自备卡：不打待确认标识。
- 卡状态不明确但不是 `direct_xd_sd_dual`：不打双卡专用待确认标识。

## 高置信：富士 xD + SD/SDHC 双兼容机型

这些机型可作为第一批代码实现名单。来源优先使用 Fujifilm 官方说明书或官方支持页。

| 系列 | 机型 | 兼容类型 | 证据 |
|---|---|---|---|
| FinePix A | A610, A800, A820, A825, A900 | xD + SD | Fujifilm A610/A800/A820/A825/A900 说明书 |
| FinePix F | F40fd, F45fd | xD + SD | Fujifilm F40fd/F45fd 说明书 |
| FinePix F | F480, F485 | xD + SD/SDHC | Fujifilm F480/F485 说明书 |
| FinePix F | F50fd | xD + SD/SDHC | Fujifilm F50fd 说明书 |
| FinePix F | F60fd | xD + SD/SDHC | Fujifilm F60fd 说明书 |
| FinePix F | F100fd | xD + SD/SDHC | Fujifilm F100fd 说明书 |
| FinePix F | F200EXR | xD + SD/SDHC | Fujifilm F200EXR 说明书 |
| FinePix J | J10, J12 | xD + SD/SDHC | Fujifilm J10/J12 说明书 |
| FinePix J | J15fd | xD + SD/SDHC | Fujifilm J15fd 说明书 |
| FinePix J | J50 | xD + SD/SDHC | Fujifilm J50/F480/F485 说明书 |
| FinePix S | S5700, S700, S5800, S800 | xD + SD/SDHC | Fujifilm S5700/S700/S5800/S800 说明书 |
| FinePix S | S1000fd | xD + SD/SDHC | Fujifilm S1000fd 说明书 |
| FinePix Z | Z10fd | xD + SD/SDHC | Fujifilm Z10fd 说明书 |
| FinePix Z | Z20fd | xD + SD/SDHC | Fujifilm Z20fd 说明书 |
| FinePix Z | Z100fd | xD + SD/SDHC | Fujifilm Z100fd 说明书 |
| FinePix Z | Z200fd | xD + SD/SDHC | Fujifilm Z200fd 说明书 |

## 待核对：二级资料支持但未找到同等官方说明书

这些机型暂时不要进第一批自动标识名单，除非后续能找到官方说明书或你人工确认。

| 系列 | 机型 | 当前证据 | 建议 |
|---|---|---|---|
| FinePix A | A805 | ManualsLib 摘录显示 A610/A805 可用 xD + SD | 待找 Fujifilm 原始 PDF 后再入库 |
| FinePix A | A920 | B&H、DPReview、ManyManuals 均显示 xD + SD/SDHC | 待找 Fujifilm 原始 PDF 后再入库 |
| FinePix F | F47fd | Fujifilm 官方固件页提到 SDHC 兼容更新，二级手册摘录显示 xD + SD | 可人工核对后入库 |
| FinePix Z | Z15fd | 常见资料称与 Z10fd/Z20fd 同期，但本次未查到可靠说明书 | 暂不入库 |

## 不应打待确认标识的反例

这些机型容易被“富士/奥林巴斯 + 老 CCD”误伤，但不能按双兼容处理。

| 机型 | 原因 |
|---|---|
| FinePix A700 | Fujifilm 官方说明书只写 xD-Picture Card，不是 xD + SD |
| FinePix A850 | Fujifilm 官方说明书只写 SD |
| FinePix Z30 | Fujifilm 官方说明书只写 SD/SDHC |
| FinePix Z33WP | Fujifilm 官方说明书只写 SD/SDHC |
| FinePix Z35/Z37 | Fujifilm 官方说明书只写 SD/SDHC |
| FinePix S1500, S1800, S2000HD 及之后多数 S 系列 | 官方说明书只写 SD/SDHC，不应进入 xD 或双兼容逻辑 |

## 奥林巴斯 MASD-1 兼容机型

奥林巴斯这里要和富士 F200EXR 区分：MASD-1 是 microSD 转 xD 的特殊卡套，不是相机直接支持标准 SD 卡。它仍然可能造成“带 1G 内存卡”无法判断是原生 xD 还是 microSD + 卡套，但实现时建议使用单独状态，例如 `masd1_card_status_uncertain_needs_confirm`，不要和富士直插 SD 的 `card_status_uncertain_needs_confirm` 混在一起。

可用 MASD-1 的机型参考：

- FE 系列：FE-20, FE-25, FE-26, FE-45, FE-46, FE-3000, FE-3010, FE-360, FE-370, FE-4000, FE-4010, FE-5000, FE-5010, FE-5020, FE-5500。
- SP 系列：SP-565UZ, SP-590UZ, SP-700。
- μ / Stylus 系列：μ 840, μ 850SW, μ 1010, μ 1020, μ 1030SW, μ 1040, μ 1050SW, μ 1060, μ 1070, μ 5000, μ 7000, μ 7010, μ 9000, Tough-6000, Tough-8000，以及对应 Stylus 命名。

注意：这部分当前项目已有 MASD-1 逻辑，后续若实现“卡状态待确认”，需要决定是否给 MASD-1 机型单独加状态，而不是直接复用富士双卡标识。

## 后续代码实现建议

1. 保留现有 `is_xd_card_model(keyword)` 作为总入口；只有它返回 True，才允许进入双兼容或 MASD-1 分支。
2. 在 `backend/app/services/xd_card_models.py` 中新增直接双兼容集合，例如 `FUJIFILM_XD_SD_DUAL_MODELS`。
3. 新增函数 `is_direct_xd_sd_dual_model(keyword: str) -> bool`，内部也要先确认该关键词是 xD 卡机型，再复用现有 `_extract_model_tokens()` 和 `_normalize()` 匹配双兼容集合。
4. 新增文本判定函数，区分：
   - `confirmed_xd_card`
   - `confirmed_sd_card`
   - `card_status_uncertain_needs_confirm`
   - `no_card_or_self_provided`
5. 在捡漏计算中，`card_status_uncertain_needs_confirm` 不应进入 `xd_card_bonus`，只作为返回字段或 `quality_flags` 展示。
6. 前端只显示“卡类型待确认”标识，不展示联系卖家的固定话术。

## 资料来源

- Fujifilm A610/A800/A820/A825/A900 Owner's Manual: https://dl.fujifilm-x.com/support/manual/a/a610_a800_a820_a900_e_manual.pdf
- Fujifilm F40fd/F45fd Owner's Manual: https://dl.fujifilm-x.com/support/manual/f/finepix_f40fd_manual_01.pdf
- Fujifilm F50fd Owner's Manual: https://dl.fujifilm-x.com/support/manual/f/finepix_f50fd_manual_01.pdf
- Fujifilm F100fd Owner's Manual: https://dl.fujifilm-x.com/support/manual/f/finepix_f100fd_manual_01.pdf
- Fujifilm F200EXR Owner's Manual: https://dl.fujifilm-x.com/support/manual/f/finepix_f200exr_manual_01.pdf
- Fujifilm J10/J12 Owner's Manual: https://dl.fujifilm-x.com/support/manual/j/finepix_j10_j12_manual_01.pdf
- Fujifilm J15fd Owner's Manual: https://dl.fujifilm-x.com/support/manual/j/finepix_j15fd_manual_01.pdf
- Fujifilm J50/F480/F485 Owner's Manual: https://dl.fujifilm-x.com/support/manual/j/finepix_j50_f480_f485_manual_01.pdf
- Fujifilm S5700/S700/S5800/S800 Owner's Manual: https://dl.fujifilm-x.com/support/manual/s/finepix_s5700_s700_s5800_s800_manual_01.pdf
- Fujifilm S1000fd Owner's Manual: https://dl.fujifilm-x.com/support/manual/s/finepix_s1000fd_manual_01.pdf
- Fujifilm Z10fd Owner's Manual: https://dl.fujifilm-x.com/support/manual/z/finepix_z10fd_manual_01.pdf
- Fujifilm Z20fd Owner's Manual: https://dl.fujifilm-x.com/support/manual/z/finepix_z20fd_manual_01.pdf
- Fujifilm Z100fd Owner's Manual: https://dl.fujifilm-x.com/support/manual/z/finepix_z100fd_manual_01.pdf
- Fujifilm Z200fd Owner's Manual: https://dl.fujifilm-x.com/support/manual/z/finepix_z200fd_manual_01.pdf
- Fujifilm F47fd firmware page: https://www.fujifilm-x.com/global/support/download/firmware/cameras/f47fd/
- Olympus FE media compatibility table: https://support.jp.omsystem.com/en/support/imsg/digicamera/compati/media/di000374e_fe.html
- Olympus SP media compatibility table: https://support.jp.omsystem.com/en/support/imsg/digicamera/compati/media/di000374e_sp.html
- Olympus MASD-1 microSD/microSDHC compatibility PDF mirror: https://www.farnell.com/datasheets/448319.pdf
