path = 'd:/cursor项目文件/估二手/backend/app/api/valuate.py'
with open(path, encoding='utf-8') as f:
    lines = f.readlines()

# 找规则筛选那行
rule_line = None
for i, line in enumerate(lines):
    if 'rule_filtered = filter_target_items(merged_items, keyword)' in line:
        rule_line = i
        break

if rule_line is None:
    print('NOT FOUND: rule_filtered line')
else:
    # 找前一行（pending）和后续行
    # 替换 rule_filtered = filter_target_items(...) 这一行
    old_line = lines[rule_line]
    indent = len(old_line) - len(old_line.lstrip())
    ind = ' ' * indent
    lines[rule_line] = f'{ind}rule_filtered, rule_filtered_out = filter_target_items_with_reasons(merged_items, keyword)\n'
    print(f'replaced rule_filtered at line {rule_line+1}')

    # 找 yield done 规则筛选完成 那行，加 filtered_out
    for i in range(rule_line, rule_line+5):
        if '规则筛选完成' in lines[i] and 'filtered_out' not in lines[i]:
            lines[i] = lines[i].replace(
                "'status': 'done'}",
                "'status': 'done', 'filtered_out': rule_filtered_out}"
            ).replace(
                '"status": "done"}',
                '"status": "done", "filtered_out": rule_filtered_out}'
            )
            print(f'patched 规则筛选完成 at line {i+1}')
            break

    # 找 items = [i for i in rule_filtered if i.item_id in keep_ids] 那行
    for i in range(rule_line, rule_line+20):
        if 'items = [i for i in rule_filtered if i.item_id in keep_ids]' in lines[i]:
            ind2 = ' ' * (len(lines[i]) - len(lines[i].lstrip()))
            lines[i] = (
                f'{ind2}llm_kept = [i for i in rule_filtered if i.item_id in keep_ids] if keep_ids else []\n'
                f'{ind2}llm_filtered_out = [\n'
                f'{ind2}    {{"title": i.title, "price": i.price, "reason": "LLM判断不符"}}\n'
                f'{ind2}    for i in rule_filtered if i.item_id not in keep_ids\n'
                f'{ind2}]\n'
                f'{ind2}items = llm_kept\n'
            )
            print(f'replaced items= at line {i+1}')
            break

    # 找 LLM精筛完成 那行，加 filtered_out
    for i in range(rule_line, rule_line+25):
        if 'LLM精筛完成' in lines[i] and 'filtered_out' not in lines[i]:
            lines[i] = lines[i].replace(
                "'status': 'done'}",
                "'status': 'done', 'filtered_out': llm_filtered_out}"
            ).replace(
                '"status": "done"}',
                '"status": "done", "filtered_out": llm_filtered_out}'
            )
            print(f'patched LLM精筛完成 at line {i+1}')
            break

    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print('done')
