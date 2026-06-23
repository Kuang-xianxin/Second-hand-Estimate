"""Verification script - compiles all modified backend files."""
import py_compile
import sys
import os

os.chdir(os.path.dirname(__file__))

files = [
    "app/config.py",
    "app/models/item.py",
    "app/models/database.py",
    "app/crawler/xianyu.py",
    "app/services/crawl_worker.py",
    "app/services/cache_updater.py",
    "app/scheduler.py",
    "main.py",
    "trigger_crawl.py",
]

ok = 0
fail = 0
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"OK: {f}")
        ok += 1
    except py_compile.PyCompileError as e:
        print(f"FAIL: {f}: {e}")
        fail += 1

print(f"\n=== {ok} OK, {fail} FAIL ===")
if fail:
    sys.exit(1)
