# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Import directly from the running server's modules
from app.services.bargain import detect_xd_card_model_from_items
from app.services.xd_card_models import is_xd_card_model

tests = [
    "z5fd",
    "z5",
    "富士z5fd",
    "olympusu1060",
    "富士 z5fd",
]

print("Backend code verification:")
for kw in tests:
    detect = detect_xd_card_model_from_items([], keyword=kw)
    direct = is_xd_card_model(kw)
    print(f"  keyword={kw!r:20s}  detect={detect}  is_xd={direct}")
