"""Chế độ lồng tiếng phim truyện: resolver + prompt Seedance không phát giọng người."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.drama.build_seedance_generate_body import build_seedance_generate_body
from app.services.drama.generation import (
    FragmentVideoPrepared,
    deserialize_fragment_video_prepared,
    serialize_fragment_video_prepared,
)
from app.services.drama.voice_mode import resolve_project_voice_mode
from app.services.seedance_segments import build_seedance_production_section

SCRIPT = "00:00-00:04 【对白·慢速清晰】Lan：Anh đi đâu vậy?\n00:04-00:08 【画面】Mưa rơi ngoài cửa sổ"


def _project(params=None, lang="vi"):
    return SimpleNamespace(params={**(params or {}), "content_lang": lang})


def test_voice_mode_defaults_by_language():
    assert resolve_project_voice_mode(_project(lang="vi")) == "dub"
    assert resolve_project_voice_mode(_project(lang="en")) == "dub"
    assert resolve_project_voice_mode(_project(lang="zh")) == "native"
    assert resolve_project_voice_mode(_project({"voiceMode": "native"}, lang="vi")) == "native"
    assert resolve_project_voice_mode(_project({"voiceMode": "dub"}, lang="zh")) == "dub"
    assert resolve_project_voice_mode(_project({"voiceMode": "bogus"}, lang="zh")) == "native"


def test_dub_production_section_forbids_voice_keeps_lipsync_and_ambient():
    section = build_seedance_production_section(SCRIPT, dub_voice=True, burn_subtitles=False, spoken_lang="vi")
    assert "后期外部 TTS" in section
    assert "禁止生成任何人声" in section
    assert "口型" in section
    assert "环境音与动作音效" in section
    assert "越南语朗读" not in section  # không còn luật "đọc bằng tiếng Việt"


def test_dub_body_keeps_generate_audio_and_skips_spoken_declaration():
    ref = [{"id": 1, "type": "character", "assetType": "image", "name": "Lan",
            "cover": "https://x/lan.png", "url": "https://x/lan.png", "params": {}}]
    body = build_seedance_generate_body({
        "content": SCRIPT, "reference": ref, "aspect_ratio": "9:16", "resolution": "480p",
        "duration_fallback": 8, "spoken_lang": "vi", "dub_voice": True,
    })
    assert body["generate_audio"] is True
    text = next(i["text"] for i in body["content"] if i.get("type") == "text")
    assert "用越南语说" not in text
    assert "禁止生成任何人声" in text


def test_prepared_voice_mode_roundtrip():
    prepared = FragmentVideoPrepared(submit_mode="i2v", image_url="https://x/a.png", voice_mode="dub")
    raw = serialize_fragment_video_prepared(prepared)
    assert raw["voice_mode"] == "dub"
    assert deserialize_fragment_video_prepared(raw).voice_mode == "dub"
    assert deserialize_fragment_video_prepared({"submit_mode": "i2v"}).voice_mode == "native"
