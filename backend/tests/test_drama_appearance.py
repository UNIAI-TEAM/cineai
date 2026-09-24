"""Ngoại hình nhân vật theo trường: chuẩn hóa, ghép prompt, áp vào params, AI tách trường."""

import pytest

from app.errors import AppError
from app.services.drama import appearance_extract
from app.services.drama.appearance_prompt import (
    APPEARANCE_KEYS,
    appearance_is_empty,
    apply_appearance_to_params,
    compose_appearance_prompt,
    normalize_appearance,
    should_recompose_prompt,
)
from app.services.drama.script_summary_prompt import SCRIPT_SUMMARY_SYSTEM_PROMPT
from app.services.drama.seed_asset_params import build_character_params


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


def test_should_recompose_only_for_character_with_appearance_keys():
    assert should_recompose_prompt("character", {"appearance": {"hair": "x"}})
    assert should_recompose_prompt("Character", {"promptManual": False})
    assert not should_recompose_prompt("scene", {"appearance": {"hair": "x"}})
    assert not should_recompose_prompt("character", {"visualPrompt": "x"})
    assert not should_recompose_prompt("character", None)


def test_manual_prompt_survives_later_appearance_edit():
    params = {"appearance": {"hair": "short"}, "promptManual": True, "visualPrompt": "my own prompt"}
    params = apply_appearance_to_params({**params, "appearance": {"hair": "long"}}, "vi")
    assert params["visualPrompt"] == "my own prompt"
    params = apply_appearance_to_params({**params, "promptManual": False}, "vi")
    assert params["visualPrompt"] == "Hair: long"


class _Asset:
    id = 7
    name = "Lan"
    type = "character"
    params = {"visualPrompt": "A young woman, 25, long black ponytail, white ao dai"}


async def test_extract_normalizes_llm_output(monkeypatch):
    async def fake_json(system, user, **kwargs):
        assert "A young woman" in user
        return {"hair": "long black ponytail", "age": 25, "junk": "x"}

    monkeypatch.setattr(appearance_extract, "drama_chat_json", fake_json)
    out = await appearance_extract.extract_appearance_fields(_Asset(), "vi")
    assert tuple(out.keys()) == APPEARANCE_KEYS
    assert out["hair"] == "long black ponytail"
    assert out["age"] == "25"


async def test_extract_all_empty_raises(monkeypatch):
    async def fake_json(system, user, **kwargs):
        return ["not", "a", "dict"]

    monkeypatch.setattr(appearance_extract, "drama_chat_json", fake_json)
    with pytest.raises(AppError) as err:
        await appearance_extract.extract_appearance_fields(_Asset(), "vi")
    assert err.value.code == "drama.appearance_extract_failed"


async def test_extract_without_source_text_raises(monkeypatch):
    class _Empty(_Asset):
        params = {}

    async def fake_json(*a, **k):
        raise AssertionError("không được gọi LLM khi không có mô tả")

    monkeypatch.setattr(appearance_extract, "drama_chat_json", fake_json)
    with pytest.raises(AppError) as err:
        await appearance_extract.extract_appearance_fields(_Empty(), "vi")
    assert err.value.code == "drama.appearance_extract_failed"
