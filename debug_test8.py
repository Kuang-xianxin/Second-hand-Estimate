# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from app.services.xd_card_models import _normalize, _extract_model_tokens, ALL_XD_MODELS

# Test normalize
for t in ['mu1060', 'mu 1060', 'fe140', 'fe-140', 'stylus1060', 'stylus 1060', 'f200exr']:
    print(f"_normalize({t!r}) = {_normalize(t)!r}")

print()
# Debug olympusu1060
kw = "olympusu1060"
tokens = _extract_model_tokens(kw)
print(f"tokens for {kw!r}: {tokens}")
normalized_tokens = {_normalize(t) for t in tokens}
print(f"normalized tokens: {normalized_tokens}")
print(f"ALL_XD_MODELS contains 'mu1060': {'mu1060' in ALL_XD_MODELS}")
for k in sorted(ALL_XD_MODELS):
    if 'mu1060' in k or k == 'mu1060':
        print(f"  key: {k!r} normalize={_normalize(k)!r}")
