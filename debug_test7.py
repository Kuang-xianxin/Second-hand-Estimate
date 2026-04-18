# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from app.services.xd_card_models import ALL_XD_MODELS, ALL_XD_MODEL_VARIANTS, _extract_model_tokens

print("=== Checking what keys are actually in ALL_XD_MODELS ===")
keys_to_check = ['mu1060', 'fe140', 'stylus1060', 'z5fd', 'a400', 'f200exr']
for k in keys_to_check:
    in_main = k in ALL_XD_MODELS
    in_var = k in ALL_XD_MODEL_VARIANTS
    print(f"'{k}': in ALL_XD_MODELS={in_main}, in VARIANTS={in_var}")

print()
print("=== Searching for mu1060-like keys ===")
for k in sorted(ALL_XD_MODELS):
    if 'mu' in k or '1060' in k:
        print(f"  '{k}'")

print()
print("=== Searching for fe140-like keys ===")
for k in sorted(ALL_XD_MODELS):
    if 'fe' in k and '140' in k:
        print(f"  '{k}'")
    if k.startswith('fe') and '140' in k:
        print(f"  '{k}'")
