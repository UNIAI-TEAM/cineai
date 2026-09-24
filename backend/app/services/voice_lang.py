"""音色 × 内容语言：判断音色能读哪些语言、每种语言的默认音色、按项目语言自动换音色。

规则（前端 lib/voiceLang.ts 实现同一套；共用测试向量 tests/fixtures/voice_lang_vectors.json）：
- 音色支持的语言以 voices.VOICE_PRESETS 的 `languages` 为准；目录外的官方音色按 id 语种前缀
  （zh_/en_/vi_…）推断；edge-tts 音色名按 locale 推断；复刻音色 S_* 等无法判断 → 不干预
- 每种语言在目录中排在最前的音色为默认音色（用户未选音色时用）；需要保持性别时取该语言同性别的第一个
- 音色不支持内容语言时，在该语言同性别音色（目录顺序）里按原音色 speaker 的 FNV-1a 32 位哈希取模挑一个
  （同一原音色 → 同一替换；不同原音色 → 分散，避免所有角色同一个声音）并记日志，避免读错口音或合成失败
- Preset auto_pool=false（giọng chỉ chọn tay trong phim truyện）không tham gia giọng mặc định / pool tự động,
  nhưng vẫn được nhận diện ngôn ngữ / giới tính.
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


def voice_gender(speaker: str | None) -> str | None:
    """音色性别：目录优先，否则按 speaker id（zh_female_… / vi_male_…）推断；无法判断返回 None。"""
    sp = (speaker or "").strip()
    if not sp:
        return None
    preset = _preset_for(sp)
    return (preset or {}).get("gender") or infer_speaker_gender(VOICE_ALIASES.get(sp, sp))


def voice_supports_lang(speaker: str | None, lang: str | None) -> bool:
    """音色是否能读该语言；语言未知或音色语言无法判断时视为支持（不干预）。"""
    if lang not in SUPPORTED_VOICE_LANGS:
        return True
    langs = voice_languages(speaker)
    return langs is None or lang in langs


def default_voice_for_lang(lang: str | None, gender: str | None = None) -> str | None:
    """该语言默认音色 speaker：同性别的第一个，没有同性别则取该语言第一个；目录无该语言返回 None。"""
    candidates = [p for p in VOICE_PRESETS if lang in (p.get("languages") or []) and p.get("auto_pool", True)]
    if not candidates:
        return None
    if gender in ("female", "male"):
        same = [p for p in candidates if p.get("gender") == gender]
        if same:
            return str(same[0]["speaker"])
    return str(candidates[0]["speaker"])


def lang_voice_pool(lang: str | None, gender: str | None = None) -> list[str]:
    """该语言的目录音色 speaker（目录顺序）；指定性别时只取同性别，没有同性别则返回该语言全部。"""
    candidates = [p for p in VOICE_PRESETS if lang in (p.get("languages") or []) and p.get("auto_pool", True)]
    if gender in ("female", "male"):
        same = [p for p in candidates if p.get("gender") == gender]
        if same:
            candidates = same
    return [str(p["speaker"]) for p in candidates]


def fnv1a32(key: str) -> int:
    """FNV-1a 32 位哈希（输入按 UTF-8 字节）；与前端 lib/voiceLang.ts fnv1a32 逐位一致。"""
    h = 0x811C9DC5
    for byte in key.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def stable_pick(pool: list[str], key: str) -> str | None:
    """按 key 的 FNV-1a 32 位哈希在 pool 中稳定挑一个：pool[fnv1a32(key) % len(pool)]；pool 为空返回 None。"""
    if not pool:
        return None
    return pool[fnv1a32(key) % len(pool)]


def voice_for_lang(speaker: str, lang: str | None) -> str:
    """音色不支持内容语言时换成该语言同性别音色（按原音色 id 稳定分散），并记日志；否则原样返回。"""
    if voice_supports_lang(speaker, lang):
        return speaker
    preset = _preset_for(speaker)
    gender = (preset or {}).get("gender") or infer_speaker_gender(VOICE_ALIASES.get(speaker, speaker))
    replacement = stable_pick(lang_voice_pool(lang, gender), VOICE_ALIASES.get(speaker, speaker))
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
