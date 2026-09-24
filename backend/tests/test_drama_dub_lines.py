"""Tách câu thoại phân cảnh và chọn speaker TTS cho từng người nói."""
from __future__ import annotations

from app.services.drama.dub_lines import DubLine, extract_dub_lines
from app.services.drama.dub_voices import CharacterVoice, resolve_line_speaker, voice_source_asset_id

CONTENT = "\n".join([
    "@duration:10",
    "00:00-00:03 【画面】Mưa rơi, Lan đứng bên cửa sổ",
    "00:03-00:06 【对白·慢速清晰·同步字幕】Lan（lo lắng）：Anh đi đâu {vậy}?",
    "【对白】@asset:12：Anh đi mua thuốc (cười nhẹ).",
    "00:08-00:10 【旁白】Đêm hôm ấy, không ai ngủ được.",
    "【内心独白】Lan：Mình phải bình tĩnh.",
])


def test_extract_lines_kinds_times_speakers():
    lines = extract_dub_lines(CONTENT, names_by_asset_id={12: "Minh"})
    assert [l.kind for l in lines] == ["dialogue", "dialogue", "narration", "inner"]
    first = lines[0]
    assert first.speaker == "Lan" and first.emotion == "lo lắng"
    assert first.text == "Anh đi đâu vậy?" and first.start_sec == 3.0
    second = lines[1]
    assert second.speaker == "Minh" and second.speaker_asset_id == 12
    assert second.text == "Anh đi mua thuốc." and second.start_sec is None
    assert lines[2].speaker == "" and lines[2].start_sec == 8.0
    assert lines[3].speaker == "Lan"


def test_extract_lines_visual_only_returns_empty():
    assert extract_dub_lines("00:00-00:05 【画面】Toàn cảnh thành phố về đêm") == []
    assert extract_dub_lines("") == []


def test_extract_lines_replaces_asset_mentions_in_text():
    lines = extract_dub_lines("【对白】Lan：Chào @asset:12 nhé.", names_by_asset_id={12: "Minh"})
    assert lines[0].text == "Chào Minh nhé."


def _line(kind="dialogue", speaker="Lan", aid=None):
    return DubLine(kind=kind, speaker=speaker, text="x", start_sec=None, emotion="", speaker_asset_id=aid)


def test_resolve_speaker_by_name_asset_and_narrator():
    chars = [
        CharacterVoice(asset_id=12, names=("Minh",), speaker="vi_male_wumg_uranus_bigtts"),
        CharacterVoice(asset_id=13, names=("Lan", "Nguyễn Lan"), speaker="vi_female_linh_uranus_bigtts"),
    ]
    narrator = "vi_female_ruan_uranus_bigtts"
    assert resolve_line_speaker(_line(speaker="Lan"), chars, lang="vi", narrator=narrator) == "vi_female_linh_uranus_bigtts"
    assert resolve_line_speaker(_line(speaker="", aid=12), chars, lang="vi", narrator=narrator) == "vi_male_wumg_uranus_bigtts"
    assert resolve_line_speaker(_line(kind="narration", speaker=""), chars, lang="vi", narrator=narrator) == narrator


def test_resolve_speaker_unknown_name_is_stable_vietnamese_voice():
    a = resolve_line_speaker(_line(speaker="Bà Tư"), [], lang="vi", narrator="n")
    b = resolve_line_speaker(_line(speaker="Bà Tư"), [], lang="vi", narrator="n")
    assert a == b and a.startswith("vi_")


def test_voice_source_asset_id_reads_binding_or_canvas():
    assert voice_source_asset_id({"voiceAudio": {"sourceAssetId": 5, "url": "u"}}) == 5
    assert voice_source_asset_id({"canvas": {"voiceAudio": {"sourceAssetId": "6"}}}) == 6
    assert voice_source_asset_id({}) is None and voice_source_asset_id(None) is None
