path = r"d:\my progect\估二手\.cursor\skills\ccd-model-database\reference.md"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the changelog section
idx = content.find('## 更新日志')
if idx < 0:
    print('更新日志 not found')
else:
    print(f"Found at index {idx}")
    print(repr(content[idx:idx+500]))
