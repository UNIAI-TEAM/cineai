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


def test_should_recompose_only_for_character_with_real_intent():
    prev = {"appearance": {"hair": "short"}}
    assert should_recompose_prompt("character", {"appearance": {"hair": "x"}}, prev)
    assert should_recompose_prompt("Character", {"promptManual": False}, prev)
    assert not should_recompose_prompt("scene", {"appearance": {"hair": "x"}}, prev)
    assert not should_recompose_prompt("character", {"visualPrompt": "x"}, prev)
    assert not should_recompose_prompt("character", None, prev)
    # Echo nguyên appearance cũ (PATCH đầy đủ params từ luồng khác) → không ghép lại
    assert not should_recompose_prompt("character", {"appearance": {"hair": " short "}}, prev)
    assert not should_recompose_prompt("character", {"promptManual": True}, prev)


def _patch_params(prev: dict, patch: dict) -> dict:
    """Mô phỏng update_asset: merge params rồi ghép lại prompt khi PATCH thực sự muốn."""
    from app.api.drama.assets import _merge_asset_params

    merged = _merge_asset_params(prev, patch)
    if should_recompose_prompt("character", patch, prev):
        merged = apply_appearance_to_params(merged, "vi")
    return merged


def test_full_params_echo_keeps_custom_prompt():
    prev = {"appearance": {"hair": "short"}, "visualPrompt": "Hair: short"}
    out = _patch_params(prev, {**prev, "voiceAssetId": 9, "visualPrompt": "imported custom prompt"})
    assert out["visualPrompt"] == "imported custom prompt"


def test_echo_of_stored_auto_flag_does_not_recompose():
    prev = {"appearance": {"hair": "short"}, "promptManual": False, "visualPrompt": "Hair: short"}
    out = _patch_params(prev, {**prev, "voiceAssetId": 9, "visualPrompt": "library prompt"})
    assert out["visualPrompt"] == "library prompt"


def test_changed_appearance_recomposes_when_not_manual():
    prev = {"appearance": {"hair": "short"}, "visualPrompt": "Hair: short"}
    out = _patch_params(prev, {"appearance": {"hair": "long"}})
    assert out["visualPrompt"] == "Hair: long"


def test_prompt_manual_false_recomposes():
    prev = {"appearance": {"hair": "short"}, "promptManual": True, "visualPrompt": "mine"}
    out = _patch_params(prev, {"promptManual": False})
    assert out["visualPrompt"] == "Hair: short"


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


# --- Các luồng LLM viết prompt không được đè prompt ghép từ trường ---
def _char(params: dict, name: str = "Lan"):
    """Tư liệu nhân vật giả cho test (không cần DB)."""
    from types import SimpleNamespace

    return SimpleNamespace(id=hash(name) % 1000, type="character", name=name, params=params)


def _project(lang: str = "vi"):
    """Dự án phim truyện giả tối thiểu cho resolve_visual_prompt_for_asset."""
    from types import SimpleNamespace

    script = SimpleNamespace(summary={}, episode_content=None, source="")
    return SimpleNamespace(id=1, user_id=1, title="P", params={"content_lang": lang}, script=script)


async def test_seed_refresh_skips_auto_composed_characters(monkeypatch):
    from app.services.drama import seed, visual_prompt

    called: list[str] = []

    async def fake_resolve(asset, project, incoming=None, **kwargs):
        called.append(asset.name)
        return "LLM rewritten prompt"

    class _Db:
        async def flush(self):
            return None

    monkeypatch.setattr(visual_prompt, "resolve_visual_prompt_for_asset", fake_resolve)
    auto = _char({"appearance": {"hair": "long"}, "visualPrompt": "Hair: long"}, "Auto")
    manual = _char(
        {"appearance": {"hair": "long"}, "promptManual": True, "visualPrompt": "mine"}, "Manual"
    )
    legacy = _char({"visualPrompt": "old"}, "Legacy")
    updated, errors = await seed.refresh_asset_prompts_from_script(_Db(), _project(), [auto, manual, legacy])
    assert errors == []
    assert sorted(called) == ["Legacy", "Manual"]
    assert updated == 2
    assert auto.params["visualPrompt"] == "Hair: long"
    assert legacy.params["visualPrompt"] == "LLM rewritten prompt"


async def test_resolve_keeps_field_composed_or_manual_prompt(monkeypatch):
    from app.services.drama import visual_prompt

    async def boom(*a, **k):
        raise AssertionError("không được gọi LLM cho prompt ghép từ trường / chỉnh tay")

    monkeypatch.setattr(visual_prompt, "drama_chat_text", boom)
    auto = _char({"appearance": {"hair": "long"}, "visualPrompt": "Hair: long"})
    assert await visual_prompt.resolve_visual_prompt_for_asset(auto, _project()) == "Hair: long"
    manual = _char({"promptManual": True, "visualPrompt": "short"})
    assert await visual_prompt.resolve_visual_prompt_for_asset(manual, _project()) == "short"
