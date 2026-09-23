"""音色 × 内容语言：判断音色能读哪些语言、每种语言的默认音色、按项目语言自动换音色。

规则（与前端 lib/voiceLang.ts 一致）：
- 音色支持的语言以 voices.VOICE_PRESETS 的 `languages` 为准；目录外的官方音色按 id 语种前缀
  （zh_/en_/vi_…）推断；edge-tts 音色名按 locale 推断；复刻音色 S_* 等无法判断 → 不干预
- 每种语言在目录中排在最前的音色为默认音色；需要保持性别时取该语言同性别的第一个
- 音色不支持内容语言时换成该语言默认音色（同性别优先）并记日志，避免读错口音或合成失败
"""

from __future__ import annotations

import logging
import re

from app.services.voices import VOICE_ALIASES, VOICE_PRESETS, infer_speaker_gender, is_edge_voice_name

logger = logging.getLogger(__name__)

SUPPORTED_VOICE_LANGS = ("zh", "vi", "en")
# 官方音色 id 的语种前缀：zh_female_… / en_male_… / vi_female_…
_SPEAKER_LANG_PREFIX_RE = re.compile(r"^([a-z]{2})_(?:female|male)_")


def _preset_for(speaker: str) -> dict | None:
    """按 id / speaker 在目录中查找音色（模板别名先换成 speaker）。"""
    raw = VOICE_ALIASES.get(speaker, speaker)
    for preset in VOICE_PRESETS:
        if preset["id"] == raw or preset["speaker"] == raw:
            return preset
    return None


def voice_languages(speaker: str | None) -> list[str] | None:
    """音色能正确朗读的语言列表；无法判断（复刻音色 S_*、自定义 id）返回 None。"""
    sp = (speaker or "").strip()
    if not sp:
        return None
    preset = _preset_for(sp)
    if preset is not None:
        return list(preset.get("languages") or []) or None
    if is_edge_voice_name(sp):
        return [sp.split("-", 1)[0].lower()]
    m = _SPEAKER_LANG_PREFIX_RE.match(sp.lower())
    if m:
        return [m.group(1)]
    return None


def voice_supports_lang(speaker: str | None, lang: str | None) -> bool:
    """音色是否能读该语言；语言未知或音色语言无法判断时视为支持（不干预）。"""
    if lang not in SUPPORTED_VOICE_LANGS:
        return True
    langs = voice_languages(speaker)
    return langs is None or lang in langs


def default_voice_for_lang(lang: str | None, gender: str | None = None) -> str | None:
    """该语言默认音色 speaker：同性别的第一个，没有同性别则取该语言第一个；目录无该语言返回 None。"""
    candidates = [p for p in VOICE_PRESETS if lang in (p.get("languages") or [])]
    if not candidates:
        return None
    if gender in ("female", "male"):
        same = [p for p in candidates if p.get("gender") == gender]
        if same:
            return str(same[0]["speaker"])
    return str(candidates[0]["speaker"])


def voice_for_lang(speaker: str, lang: str | None) -> str:
    """音色不支持内容语言时换成该语言默认音色（尽量保持性别），并记日志；否则原样返回。"""
    if voice_supports_lang(speaker, lang):
        return speaker
    preset = _preset_for(speaker)
    gender = (preset or {}).get("gender") or infer_speaker_gender(VOICE_ALIASES.get(speaker, speaker))
    replacement = default_voice_for_lang(lang, gender)
    if not replacement:
        return speaker
    logger.info("TTS 音色 %s 不支持语言 %s，改用 %s", speaker, lang, replacement)
    return replacement


def preview_lang_for_voice(speaker: str, ui_lang: str | None) -> str:
    """试听句语言：音色支持界面语言则用界面语言，否则用音色支持的第一种语言。"""
    langs = voice_languages(speaker)
    lang = ui_lang if ui_lang in SUPPORTED_VOICE_LANGS else "vi"
    if langs is None or lang in langs:
        return lang
    return next((l for l in langs if l in SUPPORTED_VOICE_LANGS), lang)
