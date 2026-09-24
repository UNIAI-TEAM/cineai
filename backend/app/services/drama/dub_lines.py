"""Tách câu thoại (对白 / 旁白 / 内心独白) trong nội dung phân cảnh thành các câu để lồng tiếng TTS."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.drama.build_fragments import rewrite_dialogue_action_lines
from app.services.seedance_segments import (
    GENERIC_NARRATOR_NAMES,
    classify_voice_body,
    paren_voice_kind,
    split_spoken_speaker,
)

# [mm:ss-mm:ss ]【对白…】phần thân
_LINE_RE = re.compile(
    r"^\s*(?:(?P<mm>\d{2}):(?P<ss>\d{2})-(?P<em>\d{2}):(?P<es>\d{2})\s*)?"
    r"(?P<cue>【(?:对白|旁白|内心独白)[^】]*】)\s*(?P<body>.+?)\s*$"
)
# Mốc khối thời gian của phân cảnh: "@duration:N" hoặc dòng chỉ có "mm:ss-mm:ss"
_DURATION_RE = re.compile(r"^\s*@duration:(\d+(?:\.\d+)?)\s*$")
_RANGE_ONLY_RE = re.compile(r"^\s*(\d{2}):(\d{2})-(\d{2}):(\d{2})\s*$")
_MENTION_RE = re.compile(r"@asset:(\d+)")
_PAREN_RE = re.compile(r"\s*[（(]([^）)]*)[）)]\s*")
# Ngoặc chú thích (0..n) rồi dấu hai chấm, sau tên người nói
_PARENS = r"(?P<paren>(?:[（(][^）)]*[）)]\s*)*)"
_ASSET_HEAD_RE = re.compile(rf"^\s*@asset:(?P<id>\d+)\s*{_PARENS}[：:]\s*(?P<text>.+)$")
_AFTER_NAME_RE = re.compile(rf"^\s*{_PARENS}[：:]\s*(?P<text>.+)$")
# "người nói：lời" chung cho 对白 / 内心独白 (tên ≤40 ký tự, không chứa ngoặc nhọn)
_GENERIC_HEAD_RE = re.compile(r"^(?P<head>[^：:\n{}]{1,40}?)\s*[：:]\s*(?P<text>.+)$")
# Dấu chấm viết tắt trong tên (Dr. Lâm, Mr. Tom, Th.S Hà): từ ≤4 chữ cái + "." + khoảng trắng/chữ
_ABBREV_DOT_RE = re.compile(r"(?<![^\s.])([^\W\d_]{1,4})\.(?=\s|[^\W\d_])")
_SENTENCE_PUNCT_RE = re.compile(r"[，,。.!！?？;；]")
# Chú thích trong ngoặc không phải cảm xúc (kiểu đọc), không đưa vào gợi ý cảm xúc TTS
_NON_EMOTION_TOKENS = {"vo", "os", "v.o.", "o.s.", "v.o", "o.s", "旁白", "画外音"}


@dataclass(frozen=True)
class DubLine:
    """Một câu cần lồng tiếng: loại, người nói, lời, mốc bắt đầu / hết khối (giây) theo kịch bản, cảm xúc trong ngoặc.

    start_sec: mốc kịch bản của câu (None = đọc nối sau câu trước).
    end_sec: giây kết thúc khối thời gian chứa câu (None = không rõ) — dùng để co giãn lời cho vừa khẩu hình.
    """

    kind: str
    speaker: str
    text: str
    start_sec: float | None
    emotion: str
    speaker_asset_id: int | None
    end_sec: float | None = None


def _replace_mentions(text: str, names: dict[int, str]) -> str:
    """Thay @asset:N bằng tên tư liệu (không có tên thì NV{N}), để dấu ':' trong token không bị hiểu là ranh giới người nói."""
    return _MENTION_RE.sub(lambda m: names.get(int(m.group(1))) or f"NV{m.group(1)}", text)


def _emotion_from(paren: str) -> str:
    """Gộp các ngoặc chú thích thành gợi ý cảm xúc, bỏ các nhãn kiểu đọc (vo/os/旁白)."""
    tokens: list[str] = []
    for inner in _PAREN_RE.findall(paren or ""):
        for part in re.split(r"[,，、/;；]", inner):
            token = part.strip()
            if token and token.lower() not in _NON_EMOTION_TOKENS:
                tokens.append(token)
    return ", ".join(tokens)


def _plausible_speaker(head: str) -> bool:
    """Đoạn trước dấu hai chấm có giống tên người nói không (cho phép dấu chấm viết tắt như 'Dr. Lâm')."""
    base = _PAREN_RE.sub("", head).strip()
    if not base:
        return False
    return not _SENTENCE_PUNCT_RE.search(_ABBREV_DOT_RE.sub(r"\1", base))


def _split_speaker(cue: str, body: str, known_names: list[str]) -> tuple[str, str, str]:
    """Tách (người nói, ngoặc chú thích, lời). Không tách được thì người nói rỗng và lời = cả thân câu.

    Thứ tự: tên đã biết (nhân vật gắn phân cảnh + nhãn lời dẫn) → luật chung; dòng 旁白 chỉ tách theo
    luật chặt (split_spoken_speaker) để dấu hai chấm giữa câu dẫn chuyện không bị hiểu là người nói.
    """
    lowered = body.lower()
    for name in known_names:
        if lowered.startswith(name.lower()):
            m = _AFTER_NAME_RE.match(body[len(name):])
            if m:
                return body[: len(name)].strip(), m.group("paren"), m.group("text").strip()
    if cue.startswith("【旁白"):
        head, text = split_spoken_speaker(cue, body)
        if not head:
            return "", "", body
        return _PAREN_RE.sub("", head).strip(), "".join(f"({p})" for p in _PAREN_RE.findall(head)), text
    m = _GENERIC_HEAD_RE.match(body)
    if not m or not _plausible_speaker(m.group("head")):
        return "", "", body
    head = m.group("head")
    parens = "".join(f"({p})" for p in _PAREN_RE.findall(head))
    return _PAREN_RE.sub("", head).strip(), parens, m.group("text").strip()


def _kind_for(cue: str, body: str, speaker: str, paren: str) -> str | None:
    """Loại câu theo cue, nội dung và người nói đã tách; None = mô tả hình ảnh, không đọc."""
    if classify_voice_body(body) == "visual":
        return None
    if speaker and speaker.lower() in GENERIC_NARRATOR_NAMES:
        return "narration"
    if cue.startswith("【内心独白") or paren_voice_kind(_PAREN_RE.sub(r"\1,", paren)) == "os":
        return "inner"
    if cue.startswith("【旁白"):
        # Nhân vật đọc lời dẫn (vo) vẫn dùng giọng nhân vật
        return "dialogue" if speaker else "narration"
    return "dialogue"


def _clean_text(text: str, names: dict[int, str]) -> str:
    """Lời để TTS đọc: thay @asset:N, bỏ ngoặc nhọn {…} và chú thích (…), gọn khoảng trắng."""
    text = _replace_mentions(text, names).replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", _PAREN_RE.sub(" ", text)).strip()
    return re.sub(r"\s+([.,!?…])", r"\1", text)


def _mmss(mm: str, ss: str) -> float:
    """"mm","ss" → giây."""
    return float(int(mm) * 60 + int(ss))


def extract_dub_lines(content: str, names_by_asset_id: dict[int, str] | None = None) -> list[DubLine]:
    """Tách các câu thoại theo thứ tự xuất hiện kèm mốc thời gian kịch bản; bỏ dòng hình ảnh / meta.

    Mốc: dòng có "mm:ss-mm:ss" dùng đúng mốc đó; phân cảnh viết theo khối "@duration:N" thì câu thoại
    đầu tiên của khối bắt đầu ở đầu khối (cộng dồn các khối trước), các câu sau trong cùng khối đọc nối tiếp.
    Người nói (kể cả @asset:N, tên có dấu phẩy/chấm, nhãn "Người dẫn chuyện") luôn được tách khỏi lời.
    """
    names = names_by_asset_id or {}
    known = sorted(
        {n.strip() for n in names.values() if n and n.strip()} | set(GENERIC_NARRATOR_NAMES),
        key=len,
        reverse=True,
    )
    out: list[DubLine] = []
    cursor = 0.0  # tổng giây của các khối @duration đã qua
    block_start: float | None = None
    block_end: float | None = None
    block_used = False  # khối hiện tại đã có câu nào nhận mốc chưa
    for raw in rewrite_dialogue_action_lines(content or "").replace("\r\n", "\n").split("\n"):
        dur = _DURATION_RE.match(raw)
        if dur:
            block_start, cursor = cursor, cursor + float(dur.group(1))
            block_end, block_used = cursor, False
            continue
        rng = _RANGE_ONLY_RE.match(raw)
        if rng:
            block_start, block_end = _mmss(rng.group(1), rng.group(2)), _mmss(rng.group(3), rng.group(4))
            block_used = False
            continue
        m = _LINE_RE.match(raw)
        if not m:
            continue
        cue, body = m.group("cue"), m.group("body")
        lead = _ASSET_HEAD_RE.match(body)
        if lead:
            asset_id = int(lead.group("id"))
            speaker, paren, text = names.get(asset_id) or f"NV{asset_id}", lead.group("paren"), lead.group("text")
        else:
            asset_id = None
            speaker, paren, text = _split_speaker(cue, _replace_mentions(body, names), known)
        kind = _kind_for(cue, _replace_mentions(body, names), speaker, paren)
        if kind is None:
            continue
        text = _clean_text(text, names)
        if not text:
            continue
        if m.group("mm"):
            start: float | None = _mmss(m.group("mm"), m.group("ss"))
            end: float | None = _mmss(m.group("em"), m.group("es"))
            block_used = True
        else:
            start = block_start if (block_start is not None and not block_used) else None
            end = block_end
            block_used = block_used or start is not None
        out.append(DubLine(
            kind=kind,
            speaker="" if kind == "narration" else speaker,
            text=text,
            start_sec=start,
            emotion=_emotion_from(paren),
            speaker_asset_id=asset_id,
            end_sec=end,
        ))
    return out
