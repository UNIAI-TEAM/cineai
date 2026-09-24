"""Chế độ tiếng thoại phim truyện: dub = Seedance chỉ tiếng môi trường + TTS lồng tiếng hậu kỳ; native = Seedance tự nói."""

from __future__ import annotations

from typing import Any

from app.services.content_lang import project_content_lang

VOICE_MODES = ("dub", "native")


def resolve_project_voice_mode(project: Any) -> str:
    """Đọc params.voiceMode của dự án; chưa đặt thì vi/en → dub, còn lại (zh) → native."""
    params = project.params if isinstance(getattr(project, "params", None), dict) else {}
    raw = str(params.get("voiceMode") or "").strip()
    if raw in VOICE_MODES:
        return raw
    return "dub" if project_content_lang(project) in ("vi", "en") else "native"
