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
    assert "禁止出现任何人声" in section
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
    assert "禁止出现任何人声" in text
    assert "Anh đi đâu vậy" not in text
    assert "【画面·角色无声口型】Lan开口" in text


def test_prepared_voice_mode_roundtrip():
    prepared = FragmentVideoPrepared(submit_mode="i2v", image_url="https://x/a.png", voice_mode="dub")
    raw = serialize_fragment_video_prepared(prepared)
    assert raw["voice_mode"] == "dub"
    assert deserialize_fragment_video_prepared(raw).voice_mode == "dub"
    assert deserialize_fragment_video_prepared({"submit_mode": "i2v"}).voice_mode == "native"


# --- Dub: prompt gửi Seedance không còn chữ thoại nào để model "đọc" ---

REAL_SCRIPT = "\n".join([
    "【字幕：底部居中·越南语·逐句轮换·与口播同步】",
    "【BGM：贴合剧情氛围的轻量配乐，情绪随画面起伏；音量低于人声】",
    "@duration:4",
    "【画面·无配音仅环境音】△ Linh kéo tay Hùng, bước lên chiếc xe hơi đen.",
    "@duration:5",
    "【对白·慢速清晰·同步字幕】Tài xế（kính cẩn）：Cậu chủ, tôi đến đón cậu.",
    "@duration:3",
    "【旁白·慢速清晰】Ba năm sau, mọi thứ đã khác.",
    "@duration:3",
    "【内心独白】Mèo：Mình phải quay lại.",
])


def _dub_text(script=REAL_SCRIPT, burn_subtitles=True):
    body = build_seedance_generate_body({
        "content": script, "reference": [], "aspect_ratio": "9:16", "resolution": "480p",
        "duration_fallback": 15, "spoken_lang": "vi", "dub_voice": True, "burn_subtitles": burn_subtitles,
    })
    return next(i["text"] for i in body["content"] if i.get("type") == "text")


def test_dub_prompt_contains_no_spoken_words():
    text = _dub_text()
    for spoken in ("Cậu chủ, tôi đến đón cậu", "Ba năm sau", "Mình phải quay lại"):
        assert spoken not in text
    assert "【对白" not in text and "【旁白" not in text and "【内心独白" not in text


def test_dub_prompt_keeps_lip_sync_acting_for_the_speaker_in_its_slot():
    text = _dub_text()
    assert "00:04-00:09" in text
    line = next(l for l in text.split("\n") if l.startswith("【画面·角色无声口型】"))
    assert "Tài xế" in line and "无声" in line
    assert "kính cẩn" in text  # thái độ tách thành dòng hình ảnh ngay trước, vẫn được diễn


def test_dub_prompt_ambient_only_no_bgm_no_model_subtitles():
    text = _dub_text(burn_subtitles=True)
    assert "【字幕" not in text and "【BGM" not in text
    assert "烧录越南语字幕" not in text
    assert "禁止任何 BGM" in text or "禁止任何背景音乐" in text
    assert "环境音" in text


def test_native_mode_asset_speaker_token_is_not_split_at_its_own_colon():
    from app.services.seedance_segments import declare_spoken_language

    out = declare_spoken_language("【对白·慢速清晰】@asset:12（giận dữ）：Anh đi đi!", "vi")
    assert out == "【对白·慢速清晰】@asset:12（giận dữ）用越南语说：{Anh đi đi!}"


def test_time_prefixed_voice_line_keeps_its_time_and_cue():
    from app.services.seedance_segments import rewrite_misclassified_visual_voice_lines

    line = "00:00-00:04 【对白·慢速清晰】Lan：Anh đi đâu vậy?"
    assert rewrite_misclassified_visual_voice_lines(line) == line
