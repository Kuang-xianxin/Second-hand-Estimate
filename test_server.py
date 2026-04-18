# -*- coding: utf-8 -*-
import sys, os, urllib.request, json, time

url = "http://127.0.0.1:8000/api/valuate/stream"

# 先尝试用简单的 HTTP 请求看服务器响应
req = urllib.request.Request(
    "http://127.0.0.1:8000/docs",
    headers={"Accept": "text/html"}
)
try:
    with urllib.request.urlopen(req, timeout=3) as r:
        print(f"Server responded: {r.status}")
except Exception as e:
    print(f"Server error: {e}")

print()

# 直接导入服务器模块测试
sys.path.insert(0, r"d:\cursor项目文件\估二手\backend")
from app.services.bargain import detect_xd_card_model_from_items
from app.services.xd_card_models import is_xd_card_model

# 打印源文件修改时间
import pathlib
src = pathlib.Path(r"d:\cursor项目文件\估二手\backend\app\services\xd_card_models.py")
print(f"Source file mtime: {src.stat().st_mtime}")

# 检查 is_xd_card_model 函数源码
import inspect
src_lines = inspect.getsource(is_xd_card_model)
print("\nis_xd_card_model source (last 30 lines):")
print('\n'.join(src_lines.strip().split('\n')[-30:]))

print()
# 测试
for kw in ["z5", "z5fd", "富士z5", "富士z5fd"]:
    r = detect_xd_card_model_from_items([], keyword=kw)
    print(f"detect({kw!r}) = {r}")
