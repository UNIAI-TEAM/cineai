"""Tách câu thoại (对白 / 旁白 / 内心独白) trong nội dung phân cảnh thành các câu để lồng tiếng TTS."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.drama.build_fragments import rewrite_dialogue_action_lines
from app.services.seedance_segments import classify_voice_body, split_spoken_speaker

# [mm:ss-mm:ss ]【对白…】phần thân
_LINE_RE = re.compile(
    r"^\s*(?:(?P<mm>\d{2}):(?P<ss>\d{2})-\d{2}:\d{2}\s*)?"
    r"(?P<cue>【(?:对白|旁白|内心独白)[^】]*】)\s*(?P<body>.+?)\s*$"
)
_MENTION_RE = re.compile(r"@asset:(\d+)")
_PAREN_RE = re.compile(r"\s*[（(]([^）)]*)[）)]\s*")


@dataclass(frozen=True)
class DubLine:
    """Một câu cần lồng tiếng: loại, người nói, lời, mốc bắt đầu (giây) nếu kịch bản có, cảm xúc trong ngoặc."""

    kind: str
    speaker: str
    text: str
    start_sec: float | None
    emotion: str
    speaker_asset_id: int | None


def _replace_mentions(text: str, names: dict[int, str]) -> str:
    """Thay @asset:N bằng tên tư liệu (không có tên thì NV{N}), để dấu ':' trong token không bị hiểu là ranh giới người nói."""
    return _MENTION_RE.sub(lambda m: names.get(int(m.group(1))) or f"NV{m.group(1)}", text)


def _kind_for(cue: str, body: str) -> str | None:
    """Loại câu theo cue và nội dung; None = mô tả hình ảnh, không đọc."""
    kind = classify_voice_body(body)
    if kind == "visual":
        return None
    if cue.startswith("【内心独白"):
        return "inner"
    if cue.startswith("【旁白"):
        return "narration" if kind != "dialogue" else "dialogue"
    return kind if kind in ("dialogue", "inner", "narration") else "dialogue"


def extract_dub_lines(content: str, names_by_asset_id: dict[int, str] | None = None) -> list[DubLine]:
    """Tách các câu thoại theo thứ tự xuất hiện; bỏ dòng hình ảnh / meta; lời bỏ ngoặc kép kiểu {…} và chú thích (…)."""
    names = names_by_asset_id or {}
    out: list[DubLine] = []
    for raw in rewrite_dialogue_action_lines(content or "").replace("\r\n", "\n").split("\n"):
        m = _LINE_RE.match(raw)
        if not m:
            continue
        cue, body = m.group("cue"), m.group("body")
        # Người nói dạng @asset:N：… — nhớ id rồi thay token bằng tên TRƯỚC khi tách "người nói：lời"
        lead = re.match(r"^\s*@asset:(\d+)", body)
        asset_id = int(lead.group(1)) if lead else None
        body = _replace_mentions(body, names)
        kind = _kind_for(cue, body)
        if kind is None:
            continue
        head, text = split_spoken_speaker(cue, body)
        emotion = ""
        paren = _PAREN_RE.search(head)
        if paren:
            emotion = paren.group(1).strip()
            head = _PAREN_RE.sub("", head).strip()
        text = text.replace("{", "").replace("}", "")
        text = re.sub(r"\s+", " ", _PAREN_RE.sub(" ", text)).strip()
        text = re.sub(r"\s+([.,!?…])", r"\1", text)
        if not text:
            continue
        start = int(m.group("mm")) * 60 + int(m.group("ss")) if m.group("mm") else None
        out.append(DubLine(
            kind=kind,
            speaker="" if kind == "narration" else head,
            text=text,
            start_sec=float(start) if start is not None else None,
            emotion=emotion,
            speaker_asset_id=asset_id,
        ))
    return out
