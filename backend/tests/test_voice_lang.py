"""Giọng đọc theo ngôn ngữ: danh mục có languages hợp lệ, chọn giọng mặc định, tự đổi giọng, nghe thử."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import tts_service as ts
from app.services import voices
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot
from app.services.voice_lang import (
    default_voice_for_lang,
    preview_lang_for_voice,
    voice_for_lang,
    voice_languages,
    voice_supports_lang,
)
from app.services.voices import VOICE_PRESETS, edge_tts_voice_for_text, infer_speaker_gender

MP3 = b"ID3" + b"\x00" * 3000


# ---- Danh mục ---------------------------------------------------------------


def test_catalog_ids_unique_and_languages_valid():
    ids = [p["id"] for p in VOICE_PRESETS]
    speakers = [p["speaker"] for p in VOICE_PRESETS]
    assert len(ids) == len(set(ids))
    assert len(speakers) == len(set(speakers))
    for p in VOICE_PRESETS:
        langs = p["languages"]
        assert langs and set(langs) <= {"zh", "vi", "en"}, p["id"]
        assert p["gender"] in {"female", "male"}
        # Nhãn đủ 3 ngôn ngữ, không rỗng
        assert all((p["label_i18n"].get(k) or "").strip() for k in ("zh", "en", "vi")), p["id"]
        # Id theo tiền tố ngôn ngữ / giới tính phải khớp trường khai báo
        prefix, gender = p["speaker"].split("_")[:2]
        assert prefix in langs and gender == p["gender"], p["id"]


def test_catalog_has_male_and_female_for_each_lang():
    for lang in ("zh", "vi", "en"):
        genders = {p["gender"] for p in VOICE_PRESETS if lang in p["languages"]}
        assert genders == {"female", "male"}, lang


def test_list_voices_exposes_languages():
    assert all("languages" in v for v in voices.list_voices())


# ---- Chọn giọng theo ngôn ngữ -------------------------------------------------


def test_default_voice_is_first_of_lang_and_keeps_gender():
    assert default_voice_for_lang("zh") == "zh_female_cancan_uranus_bigtts"
    assert default_voice_for_lang("vi") == "vi_female_ruan_uranus_bigtts"
    assert default_voice_for_lang("en") == "en_female_hayley_uranus_bigtts"
    assert default_voice_for_lang("vi", "male") == "vi_male_wumg_uranus_bigtts"
    assert default_voice_for_lang("en", "male") == "en_male_tim_uranus_bigtts"
    assert default_voice_for_lang("ja") is None


def test_voice_languages_inference():
    assert voice_languages("narrator_calm") == ["zh"]  # alias mẫu → giọng Trung
    assert voice_languages("vi_female_ruan_uranus_bigtts") == ["vi"]
    assert voice_languages("en_male_adam_mars_bigtts") == ["en"]  # ngoài danh mục: theo tiền tố
    assert voice_languages("vi-VN-HoaiMyNeural") == ["vi"]
    assert voice_languages("S_abc123") is None  # giọng clone: không biết → không can thiệp
    assert voice_languages("") is None


def _gender_of(speaker: str) -> str:
    return next(p["gender"] for p in VOICE_PRESETS if p["speaker"] == speaker)


def test_voice_for_lang_swaps_unsupported_voice_keeping_gender():
    cases = [
        ("zh_male_m191_uranus_bigtts", "vi", "male"),
        ("zh_female_vv_uranus_bigtts", "en", "female"),
        ("narrator_calm", "vi", "female"),
        ("vi_female_ruan_uranus_bigtts", "zh", "female"),
    ]
    for src, lang, gender in cases:
        out = voice_for_lang(src, lang)
        assert voice_supports_lang(out, lang), (src, out)
        assert _gender_of(out) == gender, (src, out)
    # 只有一个同性别音色时就是它
    assert voice_for_lang("zh_male_m191_uranus_bigtts", "vi") == "vi_male_wumg_uranus_bigtts"


def test_voice_for_lang_is_stable_and_spreads_same_gender_voices():
    """同一原音色 → 同一替换；不同原音色 → 分散到该语言多个同性别音色（不再全落到第一个）。"""
    zh_female = [p["speaker"] for p in VOICE_PRESETS if p["languages"] == ["zh"] and p["gender"] == "female"]
    assert len(zh_female) >= 3
    picks = {src: voice_for_lang(src, "vi") for src in zh_female}
    assert picks == {src: voice_for_lang(src, "vi") for src in zh_female}  # 稳定
    assert all(_gender_of(v) == "female" and voice_supports_lang(v, "vi") for v in picks.values())
    assert len(set(picks.values())) >= 2  # 分散
    # 别名与其 speaker 视为同一原音色
    alias_target = voices.VOICE_ALIASES["narrator_calm"]
    assert voice_for_lang("narrator_calm", "en") == voice_for_lang(alias_target, "en")
    # 用户未选音色时的默认音色仍是该语言第一个
    assert default_voice_for_lang("vi", "female") == "vi_female_ruan_uranus_bigtts"


def test_drama_speaker_inferred_directly_in_project_lang():
    """vi / en 项目：按资产稳定地直接在该语言同性别音色里挑，不同角色分散。"""
    from app.services.voices import infer_drama_speaker_from_prompt

    picks = [
        infer_drama_speaker_from_prompt("Giọng nữ trẻ, trong trẻo", character_name=f"Nhân vật {i}", asset_id=i, lang="vi")
        for i in range(1, 13)
    ]
    assert all(p.startswith("vi_female_") for p in picks)
    assert len(set(picks)) >= 3
    again = infer_drama_speaker_from_prompt("Giọng nữ trẻ, trong trẻo", character_name="Nhân vật 1", asset_id=1, lang="vi")
    assert again == picks[0]
    male = infer_drama_speaker_from_prompt("Deep male voice", character_name="Tom", asset_id=4, lang="en")
    assert male.startswith("en_male_")
    # zh / 未传 lang：沿用中文关键词规则
    assert infer_drama_speaker_from_prompt("温柔少女", asset_id=2).startswith("zh_")


def test_voice_for_lang_keeps_supported_unknown_and_clone():
    assert voice_for_lang("vi_female_linh_uranus_bigtts", "vi") == "vi_female_linh_uranus_bigtts"
    assert voice_for_lang("zh_male_m191_uranus_bigtts", "zh") == "zh_male_m191_uranus_bigtts"
    assert voice_for_lang("S_clone1", "vi") == "S_clone1"
    assert voice_for_lang("zh_male_m191_uranus_bigtts", None) == "zh_male_m191_uranus_bigtts"
    assert voice_supports_lang("anything", "fr")


def test_preview_lang_falls_back_to_voice_language():
    assert preview_lang_for_voice("vi_female_ruan_uranus_bigtts", "vi") == "vi"
    assert preview_lang_for_voice("vi_female_ruan_uranus_bigtts", "en") == "vi"
    assert preview_lang_for_voice("zh_female_cancan_uranus_bigtts", "vi") == "zh"
    assert preview_lang_for_voice("en_male_tim_uranus_bigtts", "zh") == "en"
    assert preview_lang_for_voice("S_clone", "en") == "en"


def test_gender_inferred_for_vi_en_speakers():
    assert infer_speaker_gender("vi_male_wumg_uranus_bigtts") == "male"
    assert infer_speaker_gender("en_female_skye_uranus_bigtts") == "female"


def test_edge_fallback_voice_by_lang():
    assert edge_tts_voice_for_text("en_male_tim_uranus_bigtts", "Hello there", "en") == "en-US-GuyNeural"
    assert edge_tts_voice_for_text("en_female_skye_uranus_bigtts", "Hello") == "en-US-JennyNeural"
    assert edge_tts_voice_for_text("vi_male_wumg_uranus_bigtts", "Xin chào", "vi") == "vi-VN-NamMinhNeural"
    assert edge_tts_voice_for_text("zh_female_cancan_uranus_bigtts", "你好", "zh") == "zh-CN-XiaoxiaoNeural"
    # Chỉ định thẳng giọng edge theo id
    assert edge_tts_voice_for_text("vi-VN-HoaiMyNeural", "Hello") == "vi-VN-HoaiMyNeural"


# ---- TtsService tự đổi giọng ----------------------------------------------------


@pytest.fixture
def audio_snapshot():
    prev = get_routing_snapshot()
    ch = SystemModelChannel(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="k",
                            has_api_key=True, protocol="openai", models=["gpt-4o-mini-tts"], enabled=True)
    _refresh_routing_snapshot(
        [ch], FunctionBindings(slots={"audio": [ModelBinding(channel_id="openai", model="gpt-4o-mini-tts")]})
    )
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


def _svc(monkeypatch, tmp_path, adapter):
    monkeypatch.setattr(ts, "get_adapter", lambda proto: adapter)
    monkeypatch.setattr(ts.storage, "project_dir", lambda pid: tmp_path)
    monkeypatch.setattr(ts.storage, "publish_local", lambda p, sync=False: f"/static/{p.name}")
    monkeypatch.setattr(ts, "is_near_silent_audio", lambda p: False)
    return ts.TtsService(SimpleNamespace(ffmpeg_path="ffmpeg", volc_tts_speaker=""), mock=False)


async def test_synthesize_swaps_voice_for_explicit_lang(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(return_value=MP3), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    await svc.synthesize("Hello world", "zh_male_m191_uranus_bigtts", project_id=1, shot_no=1, lang="en")
    assert adapter.tts.await_args.args[1].voice == voice_for_lang("zh_male_m191_uranus_bigtts", "en")
    assert adapter.tts.await_args.args[1].voice.startswith("en_male_")


async def test_synthesize_guesses_lang_from_text(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(return_value=MP3), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    await svc.synthesize("Xin chào các bạn", "narrator_calm", project_id=1, shot_no=2)
    assert adapter.tts.await_args.args[1].voice == voice_for_lang("narrator_calm", "vi")
    assert adapter.tts.await_args.args[1].voice.startswith("vi_female_")
    await svc.synthesize("大家好", "narrator_calm", project_id=1, shot_no=3)
    assert adapter.tts.await_args.args[1].voice == "zh_female_cancan_uranus_bigtts"


async def test_synthesize_keeps_clone_voice(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(return_value=MP3), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    await svc.synthesize("Xin chào", "S_clone42", project_id=1, shot_no=4, lang="vi")
    assert adapter.tts.await_args.args[1].voice == "S_clone42"


async def test_edge_fallback_receives_lang(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(side_effect=RuntimeError("down")), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    seen: dict = {}

    async def edge(text, dest: Path, voice_hint="", lang=None):
        seen.update(voice_hint=voice_hint, lang=lang)
        dest.write_bytes(MP3)

    monkeypatch.setattr(svc, "_tts_edge", edge)
    await svc.synthesize("Hello", "zh_female_vv_uranus_bigtts", project_id=1, shot_no=5, lang="en")
    assert seen == {"voice_hint": voice_for_lang("zh_female_vv_uranus_bigtts", "en"), "lang": "en"}
    assert seen["voice_hint"].startswith("en_female_")


# ---- Nghe thử ---------------------------------------------------------------


async def test_preview_uses_voice_language_when_ui_lang_unsupported(monkeypatch, tmp_path):
    calls: list = []

    class FakeArk:
        async def tts(self, text, speaker, **kw):
            calls.append((text, speaker, kw.get("lang")))
            return "/static/x.mp3"

    import app.services.ark as ark_mod
    import app.services.storage as storage

    monkeypatch.setattr(ark_mod, "get_ark", lambda: FakeArk())
    monkeypatch.setattr(storage, "local_path_from_url", lambda url: None)
    monkeypatch.setattr(voices, "PREVIEW_CACHE_TAG", f"test{tmp_path.name}")
    url = await voices.ensure_voice_preview("vi_female_ruan_uranus_bigtts", "en")
    assert url == "/static/x.mp3"
    text, speaker, lang = calls[0]
    assert speaker == "vi_female_ruan_uranus_bigtts" and lang == "vi"
    assert text == voices.preview_text_for_lang("vi")
