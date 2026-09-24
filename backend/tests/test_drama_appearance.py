"""Ngoại hình nhân vật theo trường: chuẩn hóa, ghép prompt, áp vào params."""

from app.services.drama.appearance_prompt import (
    APPEARANCE_KEYS,
    appearance_is_empty,
    apply_appearance_to_params,
    compose_appearance_prompt,
    normalize_appearance,
)


def test_normalize_keeps_eight_keys_and_strips():
    out = normalize_appearance({"hair": "  long black hair ", "age": 25, "bogus": "x"})
    assert tuple(out.keys()) == APPEARANCE_KEYS
    assert out["hair"] == "long black hair"
    assert out["age"] == "25"
    assert "bogus" not in out
    assert out["gender"] == ""


def test_normalize_non_dict_gives_all_empty():
    for raw in (None, "text", ["a"], 3):
        out = normalize_appearance(raw)
        assert appearance_is_empty(out)
        assert tuple(out.keys()) == APPEARANCE_KEYS


def test_compose_english_labels_for_vi_and_en_skips_empty():
    ap = normalize_appearance({"gender": "female", "age": "25", "outfit": "white ao dai"})
    for lang in ("vi", "en"):
        assert compose_appearance_prompt(ap, lang) == "Gender: female. Age: 25. Outfit: white ao dai"


def test_compose_chinese_labels_for_zh():
    ap = normalize_appearance({"gender": "女", "hair": "黑色长发"})
    assert compose_appearance_prompt(ap, "zh") == "性别：女。发型：黑色长发"


def test_compose_all_empty_returns_empty_string():
    assert compose_appearance_prompt(normalize_appearance({}), "vi") == ""


def test_apply_writes_three_prompt_slots_with_role_labels():
    params = {
        "appearance": {"gender": "female", "hair": "ponytail"},
        "roleType": "lead",
        "canvas": {"generation": {"prompt": "old", "ratio": "9:16"}},
    }
    out = apply_appearance_to_params(params, "en")
    expected = "Gender: female. Hair: ponytail. Role: lead"
    assert out["visualPrompt"] == expected
    assert out["visualImage"] == expected
    assert out["canvas"]["generation"] == {"prompt": expected, "ratio": "9:16"}
    assert out["appearance"]["hair"] == "ponytail"
    assert params["canvas"]["generation"]["prompt"] == "old"  # không sửa input


def test_apply_respects_prompt_manual():
    params = {"appearance": {"gender": "male"}, "promptManual": True, "visualPrompt": "hand written"}
    out = apply_appearance_to_params(params, "vi")
    assert out["visualPrompt"] == "hand written"


def test_apply_noop_when_appearance_empty():
    params = {"appearance": {}, "visualPrompt": "keep me"}
    out = apply_appearance_to_params(params, "vi")
    assert out["visualPrompt"] == "keep me"


from app.services.drama.script_summary_prompt import SCRIPT_SUMMARY_SYSTEM_PROMPT
from app.services.drama.seed_asset_params import build_character_params


def test_summary_prompt_asks_for_appearance_fields():
    assert '"appearance"' in SCRIPT_SUMMARY_SYSTEM_PROMPT
    for key in APPEARANCE_KEYS:
        assert f'"{key}"' in SCRIPT_SUMMARY_SYSTEM_PROMPT


def test_build_character_params_uses_appearance_when_present():
    ch = {
        "name": "Lan",
        "roleType": "lead",
        "visualImage": "long paragraph that should be replaced",
        "appearance": {"gender": "female", "age": "25", "hair": "ponytail"},
    }
    params = build_character_params(ch, "vi")
    expected = "Gender: female. Age: 25. Hair: ponytail. Role: lead"
    assert params["visualPrompt"] == expected
    assert params["visualImage"] == expected
    assert params["canvas"]["generation"]["prompt"] == expected
    assert params["appearance"]["hair"] == "ponytail"
    assert params["promptManual"] is False


def test_build_character_params_unchanged_without_appearance():
    ch = {"name": "Lan", "roleType": "lead", "visualImage": "A young woman in a white ao dai"}
    for extra in ({}, {"appearance": None}, {"appearance": "text"}, {"appearance": {}}):
        params = build_character_params({**ch, **extra}, "vi")
        assert params["visualPrompt"] == "A young woman in a white ao dai. Role: lead"
        assert params["visualImage"] == "A young woman in a white ao dai"
        assert "appearance" not in params
        assert "promptManual" not in params
