#!/usr/bin/env python3
"""
CCD 型号数据库验证脚本
检查 reference.md 中的型号数据完整性

用法: python .cursor/skills/ccd-model-database/scripts/validate.py
"""

import re, sys
from pathlib import Path


def count_models(content: str) -> dict[str, int]:
    """按品牌章节统计型号数量"""
    brands = {}

    # 找到所有 ## 一级标题（含品牌名）
    # 格式：## 1. 佳能 Canon Digital IXUS / IXY / ELPH / SD 系列
    # 注意：文件开头可能没有前导换行
    pattern = r'(?:^|\n)##\s+(?:\d+\.\s*)?(.+?)(?=\n## |$)'
    matches = list(re.finditer(pattern, content, re.DOTALL))

    for i, m in enumerate(matches):
        header = m.group(1).strip()
        # 取第一行作为标题
        title = header.split('\n')[0].strip()

        # 排除非品牌章节
        skip_keywords = ['概览', '数据统计', '更新日志', '附', '搜索关键词', '传感器切换']
        if any(kw in title for kw in skip_keywords):
            continue

        # 提取内容区域
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section_body = content[start:end]

        # 统计表格行（| 型号 | ...）
        count = 0
        in_table = False
        for line in section_body.split('\n'):
            stripped = line.strip()
            if not stripped:
                in_table = False
                continue
            # 跳过子标题（### 开头）
            if stripped.startswith('###'):
                in_table = False
                continue
            if stripped.startswith('|') or stripped.startswith('||'):
                # 去除首尾的 | 后再 split（兼容 || 格式）
                inner = stripped.strip('| ')
                cells = inner.split('|')
                if cells:
                    cell = cells[0].strip()
                    # 排除表头、分隔符、空行
                    if (cell
                        and not cell.startswith('-')
                        and cell not in ('型号', '型号名', '系列', '---')
                        and '像素' not in cell
                        and '年份' not in cell
                        and '内存卡' not in cell
                        and '变焦' not in cell
                        and '传感器' not in cell
                        and 'MASD' not in cell
                        and '搜索' not in cell
                        and '典型' not in cell
                        and '型号示例' not in cell
                        and 'Description' not in cell
                    ):
                        count += 1
                        in_table = True
            elif in_table and count > 0:
                break

        if count > 0:
            brands[title] = count

    return brands


def main():
    skill_dir = Path(__file__).parent.parent
    ref_file = skill_dir / 'reference.md'

    if not ref_file.exists():
        print(f'ERROR: {ref_file} not found')
        sys.exit(1)

    content = ref_file.read_text(encoding='utf-8')

    brands = count_models(content)

    total = sum(brands.values())

    print('=== CCD 型号数据库验证 ===')
    print(f'总计品牌章节: {len(brands)}')
    print(f'总计型号: {total}')
    print()
    print('各品牌型号数:')
    for brand, count in sorted(brands.items(), key=lambda x: -x[1]):
        print(f'  {brand}: {count}')

    # 检查必须包含的品牌
    required_brands = ['佳能', '索尼', '尼康', '松下', '富士', '奥林巴斯', '卡西欧', '三星']
    missing = [b for b in required_brands if not any(b in k for k in brands)]
    if missing:
        print(f'\nWARNING: 缺少品牌章节: {", ".join(missing)}')
    else:
        print('\nOK: 所有必需品牌已覆盖')

    print(f'\n验证完成')


if __name__ == '__main__':
    main()
