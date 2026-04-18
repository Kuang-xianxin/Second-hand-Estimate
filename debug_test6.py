# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# 单独测试 _extract_model_tokens 和 normalize
from app.services.xd_card_models import _extract_model_tokens, ALL_XD_MODELS, _normalize

test_cases = [
    "olympusu1060",
    "olympus u1060",
    "olympusmu1060",
    "olympusfe140",
    "olympus fe-140",
    "Olympusfe-130",
    "fujife200exr",
    "fujife130",
    "\u5bcc\u58ebz5fd",
    "\u5bcc\u58eb z5fd",
    "\u5bcc\u58eb f200exr",
    "\u5bcc\u58eb fe-130",
    "u1060",
    "stylus1060",
]

for kw in test_cases:
    tokens = _extract_model_tokens(kw)
    matched = [t for t in tokens if t in ALL_XD_MODELS]
    print(f"KW={kw!r}")
    print(f"  tokens={tokens!r}")
    print(f"  matched={matched!r}")
    print(f"  len(ALL_XD_MODELS)={len(ALL_XD_MODELS)}")
    print()
