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


def test_resolve_speaker_exact_name_match_wins_over_prefix_regardless_of_order():
    # "Lan" đứng trước "Lana" trong danh sách: khớp đúng tuyệt đối phải thắng, không được để "Lan" nuốt "Lana"
    chars = [
        CharacterVoice(asset_id=1, names=("Lan",), speaker="VOICE_LAN"),
        CharacterVoice(asset_id=2, names=("Lana",), speaker="VOICE_LANA"),
    ]
    assert resolve_line_speaker(_line(speaker="Lana"), chars, lang="vi", narrator="n") == "VOICE_LANA"
    # Đảo thứ tự danh sách: kết quả phải như nhau
    reversed_chars = [chars[1], chars[0]]
    assert resolve_line_speaker(_line(speaker="Lana"), reversed_chars, lang="vi", narrator="n") == "VOICE_LANA"


def test_resolve_speaker_exact_match_picks_longer_name_over_shorter_prefix():
    chars = [
        CharacterVoice(asset_id=1, names=("Lan",), speaker="VOICE_LAN"),
        CharacterVoice(asset_id=2, names=("Lan Anh",), speaker="VOICE_LAN_ANH"),
    ]
    assert resolve_line_speaker(_line(speaker="Lan Anh"), chars, lang="vi", narrator="n") == "VOICE_LAN_ANH"


def test_resolve_speaker_prefix_match_requires_word_boundary():
    chars = [CharacterVoice(asset_id=1, names=("Lan",), speaker="VOICE_LAN")]
    # "Lan Anh" bắt đầu bằng "Lan" và ký tự tiếp theo là khoảng trắng → khớp tiền tố hợp lệ
    assert resolve_line_speaker(_line(speaker="Lan Anh"), chars, lang="vi", narrator="n") == "VOICE_LAN"
    # "Lanh" bắt đầu bằng "Lan" nhưng ký tự tiếp theo "h" không phải ranh giới từ → KHÔNG được khớp "Lan"
    result = resolve_line_speaker(_line(speaker="Lanh"), chars, lang="vi", narrator="n")
    assert result != "VOICE_LAN" and result.startswith("vi_")


# --- Không đọc tên người nói, đúng mốc @duration ---

def test_asset_speaker_token_stripped_even_when_name_has_punctuation():
    lines = extract_dub_lines(
        "【对白·慢速清晰·同步字幕】@asset:12（giận dữ）：Anh đi đi!",
        names_by_asset_id={12: "Nguyễn Văn A, CEO"},
    )
    assert lines[0].text == "Anh đi đi!"
    assert lines[0].speaker == "Nguyễn Văn A, CEO" and lines[0].speaker_asset_id == 12
    assert lines[0].emotion == "giận dữ"


def test_asset_speaker_token_with_space_and_ascii_colon():
    lines = extract_dub_lines("【对白】@asset:12 : Đi thôi.", names_by_asset_id={12: "Minh"})
    assert lines[0].text == "Đi thôi." and lines[0].speaker == "Minh"


def test_speaker_name_with_abbreviation_dot_is_not_read():
    lines = extract_dub_lines("【对白·慢速清晰·同步字幕】Dr. Lâm：Xin chào.")
    assert lines[0].speaker == "Dr. Lâm" and lines[0].text == "Xin chào."


def test_known_character_name_with_comma_is_not_read():
    lines = extract_dub_lines(
        "【对白·慢速清晰·同步字幕】Nguyễn Văn A, CEO：Họp thôi.",
        names_by_asset_id={3: "Nguyễn Văn A, CEO"},
    )
    assert lines[0].speaker == "Nguyễn Văn A, CEO" and lines[0].text == "Họp thôi."


def test_vietnamese_and_english_narrator_labels_are_not_read():
    vi = extract_dub_lines("【旁白·慢速清晰】Người dẫn chuyện：Ba năm sau.")
    en = extract_dub_lines("【旁白】Narrator: Three years later.")
    assert vi[0].kind == "narration" and vi[0].text == "Ba năm sau."
    assert en[0].kind == "narration" and en[0].text == "Three years later."


def test_colon_inside_narration_sentence_is_kept():
    lines = extract_dub_lines("【旁白】Anh ấy nói rằng: cuộc đời thật khó.")
    assert lines[0].text == "Anh ấy nói rằng: cuộc đời thật khó."


def test_vo_os_markers_are_not_passed_as_emotion():
    lines = extract_dub_lines("【内心独白】Lan（os，buồn bã）：Mình sai rồi.")
    assert lines[0].emotion == "buồn bã" and lines[0].text == "Mình sai rồi."


def test_duration_blocks_give_script_start_and_slot_end():
    content = "\n".join([
        "【字幕：底部居中·越南语·逐句轮换·与口播同步】",
        "@duration:4",
        "【画面·无配音仅环境音】△ Linh kéo tay Hùng lên xe.",
        "@duration:3",
        "【画面·无配音仅环境音】Tài xế（kính cẩn）。",
        "@duration:5",
        "【对白·慢速清晰·同步字幕】Tài xế：Cậu chủ, tôi đến đón cậu.",
        "【对白·慢速清晰·同步字幕】Mèo：Ừ.",
        "@duration:3",
        "【对白·慢速清晰·同步字幕】Mèo（thở dài）：Về thôi.",
    ])
    lines = extract_dub_lines(content)
    assert [l.text for l in lines] == ["Cậu chủ, tôi đến đón cậu.", "Ừ.", "Về thôi."]
    assert [l.start_sec for l in lines] == [7.0, None, 12.0]
    assert [l.end_sec for l in lines] == [12.0, 12.0, 15.0]
