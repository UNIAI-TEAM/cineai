"""Ánh xạ người nói trong câu thoại → speaker TTS (giọng nhân vật đã gắn, lời dẫn, hoặc giọng ổn định theo tên)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.drama.dub_lines import DubLine
from app.services.voice_lang import default_voice_for_lang, lang_voice_pool, stable_pick


@dataclass(frozen=True)
class CharacterVoice:
    """Nhân vật: id tư liệu, các tên dùng để khớp (tên prompt + tên gốc), speaker TTS đã chọn."""

    asset_id: int
    names: tuple[str, ...]
    speaker: str


def voice_source_asset_id(params: dict[str, Any] | None) -> int | None:
    """Id tư liệu giọng đã gắn cho nhân vật (voiceAudio.sourceAssetId hoặc canvas.voiceAudio.sourceAssetId)."""
    if not isinstance(params, dict):
        return None
    for holder in (params, params.get("canvas") if isinstance(params.get("canvas"), dict) else {}):
        binding = holder.get("voiceAudio") if isinstance(holder, dict) else None
        if isinstance(binding, dict):
            try:
                value = int(binding.get("sourceAssetId") or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                return value
    return None


def resolve_line_speaker(line: DubLine, characters: list[CharacterVoice], *, lang: str, narrator: str) -> str:
    """Lời dẫn → giọng dẫn; thoại → nhân vật khớp id, rồi khớp tên đúng tuyệt đối (ưu tiên trước mọi khớp tiền tố),
    rồi khớp tiền tố theo ranh giới từ (chọn tên khớp dài nhất, tránh "Lan" nuốt "Lana"/"Lan Anh"); không khớp →
    giọng cùng ngôn ngữ chọn ổn định theo tên."""
    if line.kind == "narration":
        return narrator
    if line.speaker_asset_id:
        for ch in characters:
            if ch.asset_id == line.speaker_asset_id:
                return ch.speaker
    name = (line.speaker or "").strip()
    if name:
        for ch in characters:
            if any(n and name == n for n in ch.names):
                return ch.speaker
        best: tuple[int, str] | None = None  # (độ dài tên khớp, speaker) — giữ tên khớp tiền tố dài nhất
        for ch in characters:
            for n in ch.names:
                if not n or not name.startswith(n):
                    continue
                if len(name) != len(n) and not name[len(n)].isspace():
                    continue
                if best is None or len(n) > best[0]:
                    best = (len(n), ch.speaker)
        if best is not None:
            return best[1]
    pool = lang_voice_pool(lang)
    return stable_pick(pool, name or "narrator") or default_voice_for_lang(lang) or narrator
