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


def test_build_character_params_keeps_rich_visual_image_when_present():
    """Kịch bản có cả đoạn visualImage chi tiết lẫn 8 trường: prompt giữ đoạn chi tiết (8 trường ngắn làm mất chi tiết)."""
    ch = {
        "name": "Lan",
        "roleType": "lead",
        "visualImage": "A slender young woman with a high black ponytail in a white silk ao dai",
        "appearance": {"gender": "female", "age": "25", "hair": "ponytail"},
    }
    params = build_character_params(ch, "vi")
    expected = "A slender young woman with a high black ponytail in a white silk ao dai. Role: lead"
    assert params["visualPrompt"] == expected
    assert params["visualImage"] == expected
    assert params["canvas"]["generation"]["prompt"] == expected
    assert params["appearance"]["hair"] == "ponytail"
    assert params["promptManual"] is False


def test_build_character_params_composes_fields_without_visual_image():
    ch = {"name": "Lan", "roleType": "lead", "appearance": {"gender": "female", "age": "25", "hair": "ponytail"}}
    params = build_character_params(ch, "vi")
    expected = "Gender: female. Age: 25. Hair: ponytail. Role: lead"
    assert params["visualPrompt"] == expected
    assert params["visualImage"] == expected


def test_non_zh_prompt_drops_vietnamese_role_labels():
    """Dự án vi: nhãn danh tính/tính cách viết tiếng Việt không được lọt vào prompt ảnh."""
    ch = {
        "name": "Lâm Phong",
        "title": "Tổng giám đốc tập đoàn",
        "roleType": "Nam chính",
        "coreTags": "lạnh lùng, quyền lực",
        "personality": "Aloof and decisive",
        "visualImage": "A tall man in a charcoal three-piece suit",
    }
    params = build_character_params(ch, "vi")
    assert params["visualPrompt"] == "A tall man in a charcoal three-piece suit. Personality: Aloof and decisive"


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


# --- Prompt ảnh dự án vi/en phải là tiếng Anh ---
async def test_resolve_translates_vietnamese_prompt_to_english(monkeypatch):
    from app.services.drama import visual_prompt

    seen: list[str] = []

    async def fake_chat(system, user, **kwargs):
        seen.append(user)
        return "Female, 25, long black hair, white silk ao dai"

    monkeypatch.setattr(visual_prompt, "drama_chat_text", fake_chat)
    auto = _char({"appearance": {"hair": "tóc đen dài"}, "visualPrompt": "Hair: tóc đen dài. Outfit: áo dài lụa trắng"})
    out = await visual_prompt.resolve_visual_prompt_for_asset(auto, _project("vi"))
    assert out == "Female, 25, long black hair, white silk ao dai"
    assert seen and "tóc đen dài" in seen[0]


async def test_resolve_keeps_english_and_zh_prompts_without_llm(monkeypatch):
    from app.services.drama import visual_prompt

    async def boom(*a, **k):
        raise AssertionError("prompt đã đúng ngôn ngữ thì không gọi LLM dịch")

    monkeypatch.setattr(visual_prompt, "drama_chat_text", boom)
    manual = _char({"promptManual": True, "visualPrompt": "short english prompt"})
    assert await visual_prompt.resolve_visual_prompt_for_asset(manual, _project("vi")) == "short english prompt"
    zh = _char({"promptManual": True, "visualPrompt": "tóc đen dài"})
    assert await visual_prompt.resolve_visual_prompt_for_asset(zh, _project("zh")) == "tóc đen dài"


async def test_resolve_translation_failure_falls_back_to_original(monkeypatch):
    from app.services.drama import visual_prompt

    async def fail(*a, **k):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(visual_prompt, "drama_chat_text", fail)
    manual = _char({"promptManual": True, "visualPrompt": "cô gái tóc đen dài"})
    assert await visual_prompt.resolve_visual_prompt_for_asset(manual, _project("vi")) == "cô gái tóc đen dài"


# --- Sửa trường ngoại hình: AI viết lại đoạn mô tả đầy đủ thay cho bản ghép 8 trường ngắn ---
async def test_rewrite_uses_fields_and_previous_prompt(monkeypatch):
    from app.services.drama import appearance_rewrite

    seen: dict = {}

    async def fake_chat(system, user, **kwargs):
        seen.update(system=system, user=user, **kwargs)
        return "A slender woman in her mid twenties with a short silver bob, wearing a white silk ao dai embroidered with lotus"

    monkeypatch.setattr(appearance_rewrite, "drama_chat_text", fake_chat)
    ap = normalize_appearance({"gender": "female", "hair": "tóc bạc ngắn", "outfit": "white silk ao dai"})
    out = await appearance_rewrite.rewrite_appearance_description(
        ap, "vi", name="Lan", previous="A woman with a long black ponytail and a lotus-embroidered white silk ao dai"
    )
    assert out.startswith("A slender woman")
    assert "tóc bạc ngắn" in seen["user"] and "long black ponytail" in seen["user"]
    assert seen["lang"] == "vi" and seen["lang_kind"] == "visual"


async def test_rewrite_too_short_returns_empty(monkeypatch):
    from app.services.drama import appearance_rewrite

    async def fake_chat(*a, **k):
        return "A woman"

    monkeypatch.setattr(appearance_rewrite, "drama_chat_text", fake_chat)
    ap = normalize_appearance({"gender": "female"})
    assert await appearance_rewrite.rewrite_appearance_description(ap, "en", name="Lan", previous="") == ""


def test_apply_uses_given_body_instead_of_field_compose():
    params = {"appearance": {"gender": "female", "hair": "ponytail"}, "roleType": "lead"}
    out = apply_appearance_to_params(params, "en", body="A young woman with a high ponytail")
    expected = "A young woman with a high ponytail. Role: lead"
    assert out["visualPrompt"] == expected
    assert out["canvas"]["generation"]["prompt"] == expected


async def test_recompose_falls_back_to_field_compose_when_ai_fails(monkeypatch):
    from app.services.drama import appearance_rewrite

    async def fail(*a, **k):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(appearance_rewrite, "rewrite_appearance_description", fail)
    params = {"appearance": {"gender": "female", "hair": "ponytail"}}
    out = await appearance_rewrite.recompose_character_params(
        params, "en", name="Lan", previous="", run=lambda job: job()
    )
    assert out["visualPrompt"] == "Gender: female. Hair: ponytail"


async def test_recompose_uses_ai_body(monkeypatch):
    from app.services.drama import appearance_rewrite

    async def fake_rewrite(appearance, lang, *, name, previous):
        return "A young woman with a high ponytail"

    monkeypatch.setattr(appearance_rewrite, "rewrite_appearance_description", fake_rewrite)
    params = {"appearance": {"gender": "female", "hair": "ponytail"}}
    out = await appearance_rewrite.recompose_character_params(
        params, "en", name="Lan", previous="old", run=lambda job: job()
    )
    assert out["visualPrompt"] == "A young woman with a high ponytail"


async def test_recompose_skips_ai_for_manual_prompt(monkeypatch):
    from app.services.drama import appearance_rewrite

    async def boom(*a, **k):
        raise AssertionError("chế độ chỉnh tay không gọi AI")

    monkeypatch.setattr(appearance_rewrite, "rewrite_appearance_description", boom)
    params = {"appearance": {"hair": "ponytail"}, "promptManual": True, "visualPrompt": "mine"}
    out = await appearance_rewrite.recompose_character_params(
        params, "en", name="Lan", previous="mine", run=lambda job: job()
    )
    assert out["visualPrompt"] == "mine"


# --- Tích hợp PATCH /assets/{id} (cần PostgreSQL) ---
async def _seed_character(db_session, *, balance_fen: int = 100_000):
    from app.models_drama import DramaAsset, DramaProject
    from tests.conftest import make_user

    user = await make_user(db_session, balance_fen=balance_fen)
    project = DramaProject(user_id=user.id, title="P", params={"content_lang": "vi"})
    db_session.add(project)
    await db_session.flush()
    asset = DramaAsset(
        project_id=project.id,
        type="character",
        name="Lan",
        params={
            "appearance": {"gender": "female", "hair": "long black ponytail"},
            "promptManual": False,
            "visualPrompt": "A slender woman with a long black ponytail in a lotus-embroidered white silk ao dai",
        },
    )
    db_session.add(asset)
    await db_session.flush()
    return user, asset


async def test_patch_appearance_writes_ai_description(db_session, priced_routing, monkeypatch):
    from app.api.drama.assets import update_asset
    from app.schemas_drama import DramaAssetUpdate
    from app.services.drama import appearance_rewrite

    seen: dict = {}

    async def fake_rewrite(appearance, lang, *, name, previous):
        seen.update(hair=appearance["hair"], previous=previous)
        return "A slender woman with a short silver bob in a lotus-embroidered white silk ao dai"

    monkeypatch.setattr(appearance_rewrite, "rewrite_appearance_description", fake_rewrite)
    user, asset = await _seed_character(db_session)
    body = DramaAssetUpdate(params={"appearance": {"gender": "female", "hair": "short silver bob"}})
    out = await update_asset(asset.id, body, db=db_session, user=user)
    assert out.params["visualPrompt"] == "A slender woman with a short silver bob in a lotus-embroidered white silk ao dai"
    assert seen["hair"] == "short silver bob"
    assert "long black ponytail" in seen["previous"]


async def test_patch_appearance_without_balance_falls_back_to_fields(db_session, priced_routing, monkeypatch):
    from app.api.drama.assets import update_asset
    from app.schemas_drama import DramaAssetUpdate
    from app.services.drama import appearance_rewrite

    async def boom(*a, **k):
        raise AssertionError("hết số dư thì không được gọi AI")

    monkeypatch.setattr(appearance_rewrite, "rewrite_appearance_description", boom)
    user, asset = await _seed_character(db_session, balance_fen=0)
    body = DramaAssetUpdate(params={"appearance": {"gender": "female", "hair": "short silver bob"}})
    out = await update_asset(asset.id, body, db=db_session, user=user)
    assert out.params["visualPrompt"] == "Gender: female. Hair: short silver bob"
