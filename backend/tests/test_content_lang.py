"""AI 输出语言（content_lang）：请求头解析、项目语言推断、提示词本地化（不调用真实 LLM）。"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services import content_lang as cl
from app.services.drama import llm as drama_llm


# --- helper：捕获最终发给 LLM 的 system / user ---
@pytest.fixture
def captured(monkeypatch):
    calls: list[dict] = []
    reply = {"value": "{}"}

    async def fake_chat(system, user, **kwargs):
        calls.append({"system": system, "user": user, **kwargs})
        return reply["value"]

    monkeypatch.setattr(drama_llm, "chat_completions", fake_chat)
    return SimpleNamespace(calls=calls, reply=reply)


def _req(headers: dict[str, str]):
    return SimpleNamespace(headers={k.lower(): v for k, v in headers.items()} | headers)


def test_normalize_lang():
    assert cl.normalize_lang("vi-VN") == "vi"
    assert cl.normalize_lang("en_US") == "en"
    assert cl.normalize_lang("ZH-cn") == "zh"
    assert cl.normalize_lang("fr") is None
    assert cl.normalize_lang(None) is None


def test_request_lang_prefers_ui_header_then_accept_language():
    assert cl.request_lang(_req({"X-UI-Locale": "en", "accept-language": "vi"})) == "en"
    assert cl.request_lang(_req({"accept-language": "fr-FR,vi;q=0.8"})) == "vi"
    assert cl.request_lang(_req({})) == "vi"
    assert cl.request_lang(None) == "vi"


def test_guess_text_lang():
    assert cl.guess_text_lang("大禹治水") == "zh"
    assert cl.guess_text_lang("Chàng trai trẻ đi tìm kho báu") == "vi"
    assert cl.guess_text_lang("A young man hunts treasure") == "en"
    assert cl.guess_text_lang("  ") is None


def test_guess_text_lang_shared_latin_accents_are_not_vietnamese():
    """é/à/ô 等法语/英语外来词也用的字母不能单独判为越南语（只认越南语特有字母）。"""
    assert cl.guess_text_lang("Pokémon evolution") == "en"
    assert cl.guess_text_lang("Why café culture spread") == "en"
    assert cl.guess_text_lang("The naïve résumé") == "en"
    # 真实越南语：含 ư/ơ/đ/ạ 等特有字母
    assert cl.guess_text_lang("Vì sao bầu trời có màu xanh") == "vi"
    assert cl.guess_text_lang("Người đi đường") == "vi"
    # 只含共享声调字母但多数词都带：仍按越南语（短句如「Tôi là ai」）
    assert cl.guess_text_lang("Tôi là ai") == "vi"
    assert cl.guess_text_lang("Xin chào") == "vi"
    # 不带声调的越南语无法与英文区分：按 en（kepu 由界面语言兜底）
    assert cl.guess_text_lang("Tai sao bau troi mau xanh") == "en"
    assert cl.kepu_content_lang("Tai sao bau troi mau xanh", "vi") == "vi"
    assert cl.kepu_content_lang("Pokémon evolution", "en") == "en"


def test_project_content_lang_param_then_inferred_then_default():
    stored = SimpleNamespace(params={"content_lang": "en"}, title="大禹治水")
    assert cl.project_content_lang(stored) == "en"
    # 老项目：无 content_lang，按剧本原文推断
    script = SimpleNamespace(source="上古洪水泛滥，大禹受命治水……", summary=None)
    old = SimpleNamespace(params={}, title="未命名漫剧", script=script)
    assert cl.project_content_lang(old) == "zh"
    vi_old = SimpleNamespace(params=None, title="Truyền thuyết sông Hồng")
    assert cl.project_content_lang(vi_old) == "vi"
    # 无任何内容：请求语言，否则默认 vi
    empty = SimpleNamespace(params={}, title="未命名漫剧")
    assert cl.project_content_lang(empty, _req({"X-UI-Locale": "en"})) == "en"
    assert cl.project_content_lang(empty) == "vi"


def test_kepu_content_lang():
    assert cl.kepu_content_lang("光合作用是什么", "vi") == "zh"
    assert cl.kepu_content_lang("Quang hợp là gì", "en") == "vi"
    # 专有名词 / 短英文主题跟随界面语言
    assert cl.kepu_content_lang("iPhone 15", "vi") == "vi"
    assert cl.kepu_content_lang("Photosynthesis explained", "") == "en"


def test_directive_mentions_language_and_keeps_protocol_markers():
    vi = cl.output_language_directive("vi")
    assert "越南语" in vi and "【字幕：…】" in vi and "不要输出中文" in vi
    assert "英语" in cl.output_language_directive("en")
    assert "简体中文" in cl.output_language_directive("zh")
    assert "英文" in cl.visual_prompt_directive("vi")


def test_localize_system_prompt_replaces_force_chinese():
    src = "1. 每集 title 为 4-12 个汉字\n6. 语言使用简体中文\n7. 语言统一使用简体中文，偏影视风格"
    assert cl.localize_system_prompt(src, "zh") == src
    assert cl.localize_system_prompt(src, None) == src
    out = cl.localize_system_prompt(src, "vi")
    assert "语言使用简体中文" not in out
    assert "语言统一使用简体中文" not in out
    assert "个汉字" not in out
    assert "个词（word）" in out
    assert cl.output_language_directive("vi") in out
    visual = cl.localize_system_prompt("只输出一条简体中文，150–380 字，不要 JSON", "en", kind="visual")
    assert "简体中文" not in visual
    assert "英文（English）" in visual


def test_localize_length_units_skips_field_words():
    text = "不要输出字段标签，字幕 2 行，内容 200–400 字"
    out = cl.localize_length_units(text, "vi")
    assert "字段" in out and "字幕" in out
    assert "140–280 个词（word）" in out


# --- 漫剧剧本 prompt builders ---
async def test_episode_outline_prompt_vi(captured):
    from app.services.drama.agents import run_episode_outline

    captured.reply["value"] = json.dumps(
        {"episodes": [{"episodeNumber": 1, "title": "Mở màn"}, {"episodeNumber": 2, "title": "Đối đầu"}]}
    )
    rows = await run_episode_outline("Một câu chuyện dài về dòng sông", {"synopsis": "x"}, 2, lang="vi")
    assert [r["title"] for r in rows] == ["Mở màn", "Đối đầu"]
    system = captured.calls[-1]["system"]
    assert "语言使用简体中文" not in system
    assert cl.output_language_directive("vi") in system
    # 结构标签说明（build_fragments / seed 依赖中文标签）
    assert "出场人物：" in system


async def test_episode_outline_prompt_zh_unchanged(captured):
    from app.services.drama.agents import EPISODE_OUTLINE_SYSTEM, run_episode_outline

    captured.reply["value"] = json.dumps({"episodes": [{"episodeNumber": 1, "title": "开篇"}]})
    await run_episode_outline("上古洪水泛滥的故事", {"synopsis": "x"}, 1, lang="zh")
    assert EPISODE_OUTLINE_SYSTEM in captured.calls[-1]["system"]
    assert "语言使用简体中文" in captured.calls[-1]["system"]


async def test_script_summary_prompt_en(captured):
    from app.services.drama.agents import run_script_summary

    captured.reply["value"] = json.dumps({"seriesTitle": "River Legend", "characters": []})
    await run_script_summary("A long story about a river kingdom and its heroes", 3, lang="en")
    system = captured.calls[-1]["system"]
    assert "语言统一使用简体中文" not in system
    assert "4–16 个汉字" not in system
    assert "英语" in system
    assert "visualImage 是定妆照生图提示词，用英文" in system


async def test_script_batch_retry_hint_localized(captured):
    from app.services.drama.agents import run_episode_script_batch

    captured.reply["value"] = json.dumps({"episodes": [{"episodeNumber": 1, "content": "ngắn"}]})
    await run_episode_script_batch({"episodeCount": 1}, [], total=1, creative="Ý tưởng", lang="vi")
    # 首次 + 过短重试
    assert len(captured.calls) == 2
    for call in captured.calls:
        assert "语言使用简体中文" not in call["system"]
        assert "汉字" not in call["user"]


# --- 生图 / 音色 / 道具 ---
def _drama_project(lang: str | None, summary: dict | None = None):
    params = {"content_lang": lang} if lang else {}
    script = SimpleNamespace(summary=summary or {}, episode_content=None, source="")
    return SimpleNamespace(id=1, user_id=1, title="P", params=params, script=script)


async def test_visual_prompt_uses_english_for_vi_project(captured):
    from app.services.drama.visual_prompt import resolve_visual_prompt_for_asset

    captured.reply["value"] = "A young woman in a plain ao dai, " * 8
    asset = SimpleNamespace(id=1, type="character", name="Lan", params={"title": "Cô gái làng chài"})
    prompt = await resolve_visual_prompt_for_asset(asset, _drama_project("vi"), force_refresh=True)
    system = captured.calls[-1]["system"]
    assert "只输出一条简体中文" not in system
    assert "英文（English）" in system
    assert prompt.startswith("A young woman")


async def test_voice_prompt_and_sample_follow_project_lang(captured):
    from app.services.drama.voice_prompt import suggest_voice_prompt_for_character

    captured.reply["value"] = "Giọng nữ trẻ, trong trẻo, nói chậm rãi, ấm áp và dịu dàng."
    asset = SimpleNamespace(id=2, type="character", name="Lan", params={})
    prompt, speaker, sample = await suggest_voice_prompt_for_character(asset, _drama_project("vi"))
    system = captured.calls[-1]["system"]
    assert "只输出一条简体中文描述" not in system
    assert "越南语" in system
    assert "_female_" in speaker
    assert sample.startswith("Xin chào") and "Lan" in sample


async def test_extract_props_prompt_en(captured):
    from app.services.drama.extract_props_materials import extract_props_materials

    captured.reply["value"] = json.dumps({"props": [{"name": "Old sword", "visualPrompt": "A rusty bronze sword"}]})
    out = await extract_props_materials(summary={}, episode_bodies=["body"], lang="en")
    assert out["props"][0]["name"] == "Old sword"
    system = captured.calls[-1]["system"]
    assert "visualPrompt 用简体中文" not in system
    assert "name（道具名）使用英语" in system


def test_character_params_english_labels_for_vi():
    from app.services.drama.seed_asset_params import build_character_params, build_scene_params

    ch = {"visualImage": "Young fisherman", "title": "Ngư dân", "roleType": "配角", "personality": "hiền lành"}
    params = build_character_params(ch, "vi")
    assert "Identity: Ngư dân" in params["visualPrompt"]
    assert "身份" not in params["visualPrompt"]
    # stub 中文占位值不进英文提示词
    assert "配角" not in params["visualPrompt"]
    assert build_scene_params("Bến sông", lang="vi")["visualPrompt"].startswith("Scene: Bến sông")
    # 中文项目保持原样
    assert "身份：渔夫" in build_character_params({"title": "渔夫"}, "zh")["visualPrompt"]
    assert build_scene_params("河岸")["visualPrompt"].startswith("场景：河岸")


def test_fragment_plan_system_prompt():
    from app.services.drama.fragment_plan_prompt import (
        FRAGMENT_PLAN_SYSTEM_PROMPT,
        fragment_plan_system_prompt,
    )

    assert fragment_plan_system_prompt("zh") == FRAGMENT_PLAN_SYSTEM_PROMPT
    vi = fragment_plan_system_prompt("vi")
    assert "越南语" in vi and "空镜：" in vi


async def test_optimize_prompt_vi_outputs_english_visual(captured, monkeypatch):
    from app.services.agent import optimize, runner

    async def no_skills(*_args, **_kwargs):
        return ""

    monkeypatch.setattr(runner, "compose_task_skills", no_skills)
    captured.reply["value"] = "Wide shot of @asset:1 walking along the river"
    out = await optimize.optimize_prompt_with_skills(
        None, 1, prompt="@asset:1 đi dọc bờ sông", skill_ids=[1], lang="vi"
    )
    assert "@asset:1" in out
    system = captured.calls[-1]["system"]
    assert "简体中文" not in system.split("【提示词语言】")[0]
    assert "英文（English）画面描述" in system


# --- 字幕 cue ---
def test_drama_subtitle_cue_follows_dialogue_language():
    from app.services.seedance_segments import (
        DRAMA_SUBTITLE_CUE,
        build_seedance_production_section,
        drama_subtitle_cue,
        spoken_text_lang,
    )

    vi_script = "【对白·慢速清晰·同步字幕】Lan：Anh về rồi à?"
    assert spoken_text_lang(vi_script) == "vi"
    assert spoken_text_lang("【对白·慢速清晰·同步字幕】禹：出发！") == "zh"
    assert drama_subtitle_cue("zh") == DRAMA_SUBTITLE_CUE
    cue = drama_subtitle_cue("vi")
    assert "越南语" in cue and "逐句轮换" in cue
    section = build_seedance_production_section(f"{cue}\n{vi_script}")
    assert "烧录越南语字幕" in section
    assert "简体中文" not in section


def test_shorten_intro_keeps_spaces_for_latin():
    from app.services.drama.build_fragments import _shorten_intro

    assert _shorten_intro("Thủ lĩnh trị thủy. Người mở đường") == "Thủ lĩnh trị thủy"
    assert _shorten_intro("治水 首领。夏朝始祖") == "治水首领"


# --- 科普 ---
async def test_kepu_storyboard_system_localized(monkeypatch):
    from app.services import kepu_text

    seen: dict = {}

    async def fake_chat(system, user, **kwargs):
        seen["system"] = system
        raise RuntimeError("stop")

    monkeypatch.setattr(kepu_text, "chat_completions", fake_chat)
    with pytest.raises(RuntimeError):
        await kepu_text.chat_storyboard(
            "Quang hợp", "theme", "style", "", 3, 8, 8, lang="vi", mock=False
        )
    system = seen["system"]
    assert "所有字段必须使用简体中文" not in system
    assert "禁止英文句子" not in system
    assert "越南语" in system


def test_voice_preview_text_and_latin_gender_hints():
    from app.services.voices import infer_drama_speaker_from_prompt, preview_text_for_lang

    assert preview_text_for_lang("vi").startswith("Xin chào")
    assert preview_text_for_lang("en").startswith("Hello")
    assert "试听" in preview_text_for_lang("zh")
    assert "_female_" in infer_drama_speaker_from_prompt("Giọng nữ trẻ, trong trẻo", asset_id=2)
    assert "_male_" in infer_drama_speaker_from_prompt("Deep male voice, calm", asset_id=1)
