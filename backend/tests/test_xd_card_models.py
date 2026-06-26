from app.services.xd_card_models import is_xd_card_model


def test_casio_z3000_is_not_xd_card_model():
    # WHY: Casio EX-Z3000 uses SD-family cards; "z3000" must not fuzzy-match
    # the Fuji Z3 xD model prefix.
    assert is_xd_card_model("卡西欧z3000") is False
    assert is_xd_card_model("卡西欧z 3000") is False
    assert is_xd_card_model("casio z3000") is False
    assert is_xd_card_model("z3000") is False


def test_non_xd_brand_context_blocks_bare_xd_model_collisions():
    # WHY: bare xD model tokens like A700/Z3 are valid for Fuji, but not when
    # the user's keyword explicitly says Canon/Casio/Sony/etc.
    assert is_xd_card_model("佳能a700") is False
    assert is_xd_card_model("卡西欧z3") is False


def test_fuji_and_olympus_shorthand_still_match_xd_models():
    # WHY: keep the useful shorthand behavior that originally motivated fuzzy
    # matching, but only when the numeric model field is the same.
    assert is_xd_card_model("富士z3") is True
    assert is_xd_card_model("富士z5") is True
    assert is_xd_card_model("finepix z5") is True
    assert is_xd_card_model("奥林巴斯fe3000") is True
