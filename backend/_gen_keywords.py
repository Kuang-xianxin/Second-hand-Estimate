"""从 reference.md 提取全量关键词"""
import re, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')

text = pathlib.Path(r'd:\my progect\估二手\.cursor\skills\ccd-model-database\reference.md').read_text(encoding='utf-8-sig')

# Map section prefix -> (brand_key, var_name, comment)
BRAND_MAP = {
    '## 1. 佳能 Canon Digital IXUS': ('canon_ixus', 'CANON_IXUS_KEYWORDS', '# Canon Digital IXUS / IXY / ELPH / SD 系列'),
    '## 2. 佳能 Canon PowerShot A': ('canon_ps_a', 'CANON_PS_A_KEYWORDS', '# Canon PowerShot A 系列'),
    '## 3. 佳能 Canon PowerShot SX': ('canon_ps_sx', 'CANON_PS_SX_KEYWORDS', '# Canon PowerShot SX 系列'),
    '## 4. 索尼 Sony Cyber-shot T': ('sony_t', 'SONY_T_TX_KEYWORDS', '# Sony Cyber-shot T / TX 系列'),
    '## 5. 索尼 Sony Cyber-shot W': ('sony_w', 'SONY_W_WX_KEYWORDS', '# Sony Cyber-shot W / WX 系列'),
    '## 6. 索尼 Sony Cyber-shot H': ('sony_h', 'SONY_H_KEYWORDS', '# Sony Cyber-shot H / P / M / S / N 系列'),
    '## 7. 尼康 Nikon Coolpix S': ('nikon_s', 'NIKON_COOLPIX_S_KEYWORDS', '# Nikon Coolpix S 系列'),
    '## 8. 尼康 Nikon Coolpix L': ('nikon_l', 'NIKON_COOLPIX_L_KEYWORDS', '# Nikon Coolpix L 系列'),
    '## 9. 松下 Panasonic Lumix': ('panasonic_fx', 'PANASONIC_FX_KEYWORDS', '# Panasonic Lumix FX 系列'),
    '## 10. 卡西欧 Casio Exilim': ('casio_exilim', 'CASIO_EXILIM_KEYWORDS', '# Casio Exilim 系列'),
    '## 11. 三星 Samsung': ('samsung', 'SAMSUNG_KEYWORDS', '# Samsung NV / ST / MV / WB 系列'),
    '## 12. 富士 Fujifilm FinePix': ('fuji', 'FUJIFILM_KEYWORDS', '# Fujifilm FinePix xD 系列'),
    '## 13. 奥林巴斯 Olympus': ('olympus', 'OLYMPUS_KEYWORDS', '# Olympus xD 系列（mu/Stylus/FE/SP）'),
    '## 14. 宾得 Pentax': ('pentax', 'PENTAX_KEYWORDS', '# Pentax Optio 系列'),
    '## 15. 柯达 Kodak': ('kodak', 'KODAK_KEYWORDS', '# Kodak EasyShare 系列'),
}

# Sections that are NOT data sections (skip them)
SKIP_PREFIXES = (
    '## 概览', '## 数据统计', '## 更新日志',
    '### 全部 xD 卡机型统计', '### 全部型号列表',
    '### 传感器切换时间线', '### P / M / S / N 系列',
    '### WX 系列', '### W 系列', '### T 系列', '### TX 系列',
    '### H 系列', '### EX-H / EX-FC / EX-FS / EX-S / EX-TR / EX-ZR 系列',
    '### EX-Z 系列', '### NV 系列', '### ST 系列', '### MV / WB 系列',
    '### 主要型号', '### FX 系列全部型号', '### S 系列全部型号', '### L 系列全部型号',
)

current_brand = None
all_entries = {}

lines = text.splitlines()
for raw_line in lines:
    line = raw_line.strip()
    # Check for brand section header FIRST (before table row check)
    brand_key = None
    for prefix, (bk, vn, vc) in BRAND_MAP.items():
        if line.startswith(prefix):
            current_brand = bk
            if bk not in all_entries:
                all_entries[bk] = []
            brand_key = bk
            break
    if brand_key:
        continue

    # Skip non-data sections
    if current_brand is None:
        continue
    skip = False
    for sp in SKIP_PREFIXES:
        if line.startswith(sp):
            skip = True
            break
    if skip:
        continue

    # Must be a table data row: | ... | ... |
    if not (line.startswith('|') and line.endswith('|') and '---' not in line):
        continue

    parts = [p.strip() for p in line.split('|')]
    if len(parts) < 4:
        continue

    # Year col is parts[3]; must be 4-digit
    year = parts[3].strip()
    if not re.match(r'^\d{4}$', year):
        continue

    # Model col is parts[2]
    model = parts[2].strip()
    if not model:
        continue

    # Keyword col: last non-empty column
    kw_col = ''
    for p in reversed(parts):
        if p.strip():
            kw_col = p.strip()
            break

    # Extract keywords
    kws = []
    for kw in kw_col.split(','):
        kw = kw.strip().lower()
        if kw and len(kw) > 1:
            kws.append(kw)
    if kws:
        all_entries[current_brand].append((model, kws))

# Print stats
total_kws = 0
for brand in ['canon_ixus', 'canon_ps_a', 'canon_ps_sx', 'sony_t', 'sony_w',
              'sony_h', 'nikon_s', 'nikon_l', 'panasonic_fx', 'casio_exilim',
              'samsung', 'fuji', 'olympus', 'pentax', 'kodak']:
    if brand not in all_entries or not all_entries[brand]:
        continue
    entries = all_entries[brand]
    count = sum(len(kws) for _, kws in entries)
    total_kws += count
    print(f"{brand}: {len(entries)} models, {count} keywords")

print(f"\nTotal: {total_kws} keywords from {sum(len(v) for v in all_entries.values())} models")

# Generate ccd_keywords.py
BRAND_VAR_NAMES = {
    'canon_ixus': 'CANON_IXUS_KEYWORDS',
    'canon_ps_a': 'CANON_PS_A_KEYWORDS',
    'canon_ps_sx': 'CANON_PS_SX_KEYWORDS',
    'sony_t': 'SONY_T_TX_KEYWORDS',
    'sony_w': 'SONY_W_WX_KEYWORDS',
    'sony_h': 'SONY_H_KEYWORDS',
    'nikon_s': 'NIKON_COOLPIX_S_KEYWORDS',
    'nikon_l': 'NIKON_COOLPIX_L_KEYWORDS',
    'panasonic_fx': 'PANASONIC_FX_KEYWORDS',
    'casio_exilim': 'CASIO_EXILIM_KEYWORDS',
    'samsung': 'SAMSUNG_KEYWORDS',
    'fuji': 'FUJIFILM_KEYWORDS',
    'olympus': 'OLYMPUS_KEYWORDS',
    'pentax': 'PENTAX_KEYWORDS',
    'kodak': 'KODAK_KEYWORDS',
}

BRAND_COMMENTS = {
    'canon_ixus': '# Canon Digital IXUS / IXY / ELPH / SD 系列',
    'canon_ps_a': '# Canon PowerShot A 系列',
    'canon_ps_sx': '# Canon PowerShot SX 系列',
    'sony_t': '# Sony Cyber-shot T / TX 系列',
    'sony_w': '# Sony Cyber-shot W / WX 系列',
    'sony_h': '# Sony Cyber-shot H / P / M / S / N 系列',
    'nikon_s': '# Nikon Coolpix S 系列',
    'nikon_l': '# Nikon Coolpix L 系列',
    'panasonic_fx': '# Panasonic Lumix FX 系列',
    'casio_exilim': '# Casio Exilim 系列',
    'samsung': '# Samsung NV / ST / MV / WB 系列',
    'fuji': '# Fujifilm FinePix xD 系列',
    'olympus': '# Olympus xD 系列（mu/Stylus/FE/SP）',
    'pentax': '# Pentax Optio 系列',
    'kodak': '# Kodak EasyShare 系列',
}

BRAND_ORDER = ['canon_ixus', 'canon_ps_a', 'canon_ps_sx', 'sony_t', 'sony_w',
               'sony_h', 'nikon_s', 'nikon_l', 'panasonic_fx', 'casio_exilim',
               'samsung', 'fuji', 'olympus', 'pentax', 'kodak']

lines_out = [
    '"""',
    'CCD 全型号关键词生成器——从 reference.md 自动生成',
    f'覆盖: {sum(len(v) for v in all_entries.values())} 型号, {total_kws} 关键词',
    '"""',
    'from typing import List',
    '',
]

for brand in BRAND_ORDER:
    if brand not in all_entries or not all_entries[brand]:
        continue
    entries = all_entries[brand]
    var_name = BRAND_VAR_NAMES[brand]
    lines_out.append(BRAND_COMMENTS[brand])
    lines_out.append(f'{var_name} = [')
    for model, kws in entries:
        for kw in kws:
            lines_out.append(f'    "{kw}",')
    lines_out.append(']')
    lines_out.append('')

lines_out.extend([
    '# 全量关键词列表（去重）',
    'def _dedup(keywords: list) -> list:',
    '    seen = set()',
    '    result = []',
    '    for kw in keywords:',
    '        norm = kw.strip().lower()',
    '        if norm and norm not in seen:',
    '            seen.add(norm)',
    '            result.append(kw.strip())',
    '    return result',
    '',
    'ALL_CCD_KEYWORDS = _dedup(',
])
for brand in BRAND_ORDER:
    if brand not in all_entries or not all_entries[brand]:
        continue
    var_name = BRAND_VAR_NAMES[brand]
    lines_out.append(f'    {var_name}')
lines_out.append('    + KODAK_KEYWORDS')
lines_out.extend([
    ')',
    '',
    'def get_all_keywords() -> list:',
    '    """返回全量 CCD 关键词列表。"""',
    '    return ALL_CCD_KEYWORDS',
    '',
    'def get_keyword_count() -> int:',
    '    """返回关键词总数。"""',
    '    return len(ALL_CCD_KEYWORDS)',
])

output = '\n'.join(lines_out)
out_path = pathlib.Path(r'd:\my progect\估二手\backend\app\services\ccd_keywords.py')
out_path.write_text(output, encoding='utf-8')
print(f'\nWrote {len(output)} chars to ccd_keywords.py')
