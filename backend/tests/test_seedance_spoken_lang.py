"""Seedance lời thoại vi/en: khai báo ngôn ngữ trước lời thoại (docs/SEEDANCE_2_5.md §4.3), zh giữ nguyên."""
from __future__ import annotations

from app.services.drama.build_seedance_generate_body import (
    build_seedance_generate_body,
    build_seedance_prompt_text,
)
from app.services.seedance_segments import (
    build_seedance_production_section,
    declare_spoken_language,
)

SCRIPT = "\n".join(
    [
        "@duration:4",
        "【画面·无配音仅环境音】Bobo looks at the moon.",
        "【对白·慢速清晰·同步字幕】波波：Xin chào, mình là Bobo.",
        "【旁白·慢速清晰·同步字幕】Remember: the moon changes.",
        "【旁白·慢速清晰·同步字幕】旁白（VO）：Ngày xưa…",
        "【内心独白·同步字幕】Minh（os，lo lắng）：Mình phải cố lên.",
        "00:04-00:08 【对白·慢速清晰】Anna Lee: Let's go {now}!",
    ]
)


def test_declare_vi_rewrites_only_voice_lines():
    out = declare_spoken_language(SCRIPT, "vi").split("\n")
    assert out[0] == "@duration:4"
    assert out[1] == "【画面·无配音仅环境音】Bobo looks at the moon."
    assert out[2] == "【对白·慢速清晰·同步字幕】波波用越南语说：{Xin chào, mình là Bobo.}"
    # Dấu hai chấm giữa câu lời dẫn không bị coi là tên người nói
    assert out[3] == "【旁白·慢速清晰·同步字幕】用越南语说：{Remember: the moon changes.}"
    assert out[4] == "【旁白·慢速清晰·同步字幕】旁白（VO）用越南语说：{Ngày xưa…}"
    assert out[5] == "【内心独白·同步字幕】Minh（os，lo lắng）用越南语说：{Mình phải cố lên.}"
    # Giữ mốc thời gian, tên có dấu cách; bỏ ngoặc nhọn thừa trong lời thoại
    assert out[6] == "00:04-00:08 【对白·慢速清晰】Anna Lee用越南语说：{Let's go now!}"


def test_declare_en_is_idempotent_and_zh_identity():
    once = declare_spoken_language(SCRIPT, "en")
    assert "Lee用英语说：{" in once
    assert declare_spoken_language(once, "en") == once
    assert declare_spoken_language(SCRIPT, "zh") == SCRIPT
    assert declare_spoken_language(SCRIPT, None) == SCRIPT
    assert declare_spoken_language("", "vi") == ""


def test_production_section_adds_language_rule_for_vi_only():
    zh = build_seedance_production_section(SCRIPT)
    vi = build_seedance_production_section(SCRIPT, spoken_lang="vi")
    assert "口播语言" not in zh
    assert "口播语言：所有旁白、对白、内心独白一律用越南语朗读" in vi
    # Phụ đề cháy vào hình dùng đúng ngôn ngữ dự án
    assert "烧录越南语字幕" in vi
    en = build_seedance_production_section(SCRIPT, spoken_lang="en", burn_subtitles=False)
    assert "一律用英语朗读" in en


def test_prompt_text_declares_language_in_body():
    text = build_seedance_prompt_text(SCRIPT, [], spoken_lang="en")
    assert "波波用英语说：{Xin chào, mình là Bobo.}" in text
    assert "一律用英语朗读" in text
    plain = build_seedance_prompt_text(SCRIPT, [])
    assert "用英语说" not in plain and "口播语言" not in plain


def test_generate_body_threads_spoken_lang():
    body = build_seedance_generate_body({"content": SCRIPT, "reference": [], "spoken_lang": "vi"})
    text = body["content"][0]["text"]
    assert "波波用越南语说：{Xin chào, mình là Bobo.}" in text
    body_zh = build_seedance_generate_body({"content": SCRIPT, "reference": []})
    assert "用越南语说" not in body_zh["content"][0]["text"]
