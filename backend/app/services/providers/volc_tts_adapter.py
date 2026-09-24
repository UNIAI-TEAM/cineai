"""Volcengine/BytePlus Seed Speech (openspeech) adapter: NDJSON → bytes, speaker + emotion."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from app.schemas_routing import ResolvedModelRoute
from app.services.providers.base import ProviderNotSupported, TtsRequest, UpstreamError
from app.services.providers.host_guard import same_host

VOLC_TTS_DEFAULT_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
BYTEPLUS_TTS_URL = "https://voice.ap-southeast-1.bytepluses.com/api/v3/tts/unidirectional"

SPEAKER_ALIASES: dict[str, str] = {
    "narrator_calm": "zh_female_cancan_uranus_bigtts",
    "warm_storyteller": "zh_female_tianmeixiaoyuan_uranus_bigtts",
    "teacher_clear": "zh_male_shaonianzixin_uranus_bigtts",
    "urban_editorial": "zh_female_shuangkuaisisi_uranus_bigtts",
    "retro_host": "zh_male_shaonianzixin_uranus_bigtts",
    "guqin_narrator": "zh_female_vv_uranus_bigtts",
}

VOLC_TTS_STATIC_MODELS: list[dict[str, str]] = [
    {"id": "seed-tts-2.0", "label": "Seed TTS 2.0", "capability": "audio"},
    {"id": "seed-tts-1.0", "label": "Seed TTS 1.0", "capability": "audio"},
    {"id": "seed-icl-2.0", "label": "Voice clone (S_*)", "capability": "audio"},
]

# Header cố định theo tài liệu BytePlus TTS v3
BYTEPLUS_APP_KEY = "aGjiRDfUWi"
# Mỗi request tối đa ngần này ký tự (tránh 40402003 TTSExceededTextLimit); văn bản dài cắt theo câu
MAX_TTS_CHUNK_CHARS = 300
# Ngôn ngữ nội dung → additions.explicit_language (zh để trống: mặc định đọc lẫn Trung-Anh)
_EXPLICIT_LANG = {"vi": "vi", "en": "en"}
# Câu gợi ý cảm xúc (context_texts, TTS 2.0) theo ngôn ngữ nội dung
_EMOTION_TEMPLATES = {
    "zh": "用「{hint}」的语气朗读",
    "vi": "Hãy đọc với giọng {hint}",
    "en": "Read this in a {hint} tone",
}
_SPEAKER_LANG_RE = re.compile(r"^(zh|en|vi)_")
_SENTENCE_RE = re.compile(r"[^.!?。！？…\n]+[.!?。！？…]*\s*|\n+")
# Mã lỗi openspeech coi là tạm thời (đổi kênh / thử lại được)
_TRANSIENT_CODES = {55000000}


class OpenspeechError(UpstreamError):
    """Lỗi openspeech có mã nghiệp vụ (code) hoặc HTTP status."""

    def __init__(self, message: str, *, code: int | None = None, status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def speaker_lang(speaker: str) -> str | None:
    """Ngôn ngữ suy từ tiền tố speaker (vi_/en_/zh_); không suy được trả None."""
    m = _SPEAKER_LANG_RE.match((speaker or "").strip())
    return m.group(1) if m else None


def split_tts_text(text: str, max_chars: int | None = None) -> list[str]:
    """Cắt văn bản thành các đoạn ≤ max_chars theo ranh giới câu; câu quá dài cắt theo khoảng trắng."""
    limit = max_chars or MAX_TTS_CHUNK_CHARS
    clean = (text or "").strip()
    if len(clean) <= limit:
        return [clean] if clean else []
    sentences = [s.strip() for s in _SENTENCE_RE.findall(clean) if s.strip()]
    pieces: list[str] = []
    for sentence in sentences:
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit + 1)
            cut = cut if cut > 0 else limit
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            pieces.append(sentence)
    chunks: list[str] = []
    for piece in pieces:
        if chunks and len(chunks[-1]) + 1 + len(piece) <= limit:
            chunks[-1] = f"{chunks[-1]} {piece}"
        else:
            chunks.append(piece)
    return chunks


def resolve_volc_speaker(voice: str, default: str) -> str:
    """Resolve voice name to speaker using SPEAKER_ALIASES or fallback to default."""
    return SPEAKER_ALIASES.get(voice, voice) or default


# Speaker id kiểu Volc/BytePlus: zh_/en_/ja_/multi_… (vd. zh_female_cancan_uranus_bigtts)
_VOLC_SPEAKER_RE = re.compile(r"^(zh|en|vi|ja|es|id|pt|multi)_[a-z0-9]+_")


def is_volc_speaker(speaker: str) -> bool:
    """Speaker chỉ Volc phục vụ được: giọng clone S_*, *_bigtts, hoặc id kiểu zh_/en_… của Volc."""
    sp = (speaker or "").strip()
    if not sp:
        return False
    return sp.startswith("S_") or sp.endswith("_bigtts") or bool(_VOLC_SPEAKER_RE.match(sp))


def resource_id_for_speaker(speaker: str, default: str) -> str:
    """Determine API resource ID based on speaker name patterns."""
    if speaker.startswith("S_"):
        return "seed-icl-2.0"
    if "_uranus_" in speaker or speaker.startswith("saturn_"):
        return default
    return "seed-tts-1.0"


def build_tts_additions(speaker: str, emotion_hint: str | None, lang: str | None = None) -> str | None:
    """Ghép additions openspeech: model_type cho giọng clone S_, explicit_language vi/en, context_texts theo ngôn ngữ."""
    additions: dict[str, Any] = {}
    if speaker.startswith("S_"):
        additions["model_type"] = 4
    eff_lang = lang or speaker_lang(speaker)
    explicit = _EXPLICIT_LANG.get(eff_lang or "")
    if explicit:
        additions["explicit_language"] = explicit
    hint = (emotion_hint or "").strip()
    if hint:
        template = _EMOTION_TEMPLATES.get(eff_lang or "", _EMOTION_TEMPLATES["zh"])
        additions["context_texts"] = [template.format(hint=hint)]
    if not additions:
        return None
    return json.dumps(additions, ensure_ascii=False)


def parse_openspeech_ndjson(raw: bytes) -> bytes:
    """Ghép các chunk base64 tới khi gặp 20000000; gặp mã lỗi khác thì raise OpenspeechError."""
    chunks: list[bytes] = []
    text = raw.decode("utf-8", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        code = obj.get("code")
        if code == 0 and obj.get("data"):
            chunks.append(base64.b64decode(obj["data"]))
        elif code in {20000000, 20000001}:
            break
        elif isinstance(code, int) and code != 0:
            raise OpenspeechError(f"openspeech {code}: {str(obj.get('message') or '')[:200]}", code=code)
    return b"".join(chunks)


class VolcTtsAdapter:
    """Volcengine/BytePlus Seed Speech: NDJSON audio chunks, speaker aliases, emotion context."""

    protocol = "volc_tts"

    async def list_models(self, route: ResolvedModelRoute, capability: str = "all") -> list[dict[str, str]]:
        """Return Volc TTS static models filtered by capability."""
        return [m for m in VOLC_TTS_STATIC_MODELS if capability in ("all", m["capability"])]

    async def gen_image(self, route: ResolvedModelRoute, req: Any) -> Any:
        """Volc TTS does not support image generation."""
        raise ProviderNotSupported("Volcengine TTS không hỗ trợ tạo ảnh")

    async def create_video(self, route: ResolvedModelRoute, req: Any) -> str:
        """Volc TTS does not support video creation."""
        raise ProviderNotSupported("Volcengine TTS không hỗ trợ tạo video")

    async def fetch_video(self, route: ResolvedModelRoute, task_id: str) -> Any:
        """Volc TTS does not support video creation."""
        raise ProviderNotSupported("Volcengine TTS không hỗ trợ tạo video")

    async def tts(self, route: ResolvedModelRoute, req: TtsRequest) -> bytes:
        """Chuyển văn bản thành giọng qua openspeech; văn bản dài cắt nhiều request rồi nối MP3."""
        from app.config import get_settings

        settings = get_settings()
        speaker = resolve_volc_speaker(req.voice, settings.volc_tts_speaker or "zh_female_cancan_uranus_bigtts")
        resource = resource_id_for_speaker(speaker, settings.volc_tts_resource_id or "seed-tts-2.0")
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-Api-Resource-Id": resource,
            "X-Api-App-Key": BYTEPLUS_APP_KEY,
        }
        url = route.base_url or settings.volc_tts_url or VOLC_TTS_DEFAULT_URL
        api_key = (route.api_key or "").strip()
        if api_key:
            headers["X-Api-Key"] = api_key
        else:
            # Cặp app-id/access-key toàn cục chỉ gửi tới host đã cấu hình trong env, không gửi tới base URL lạ
            if not same_host(url, settings.volc_tts_url or VOLC_TTS_DEFAULT_URL):
                raise UpstreamError("Máy chủ TTS tuỳ chỉnh cần API key riêng")
            headers["X-Api-App-Id"] = settings.volc_tts_app_id
            headers["X-Api-Access-Key"] = settings.volc_tts_access_key

        audio_params: dict[str, Any] = {"format": "mp3", "sample_rate": 24000}
        if req.speech_rate:
            audio_params["speech_rate"] = max(-50, min(100, int(req.speech_rate)))
        additions = build_tts_additions(speaker, req.emotion_hint, req.lang)
        parts: list[bytes] = []
        async with httpx.AsyncClient(timeout=120.0) as client:
            for chunk in split_tts_text(req.text) or [req.text]:
                body: dict[str, Any] = {
                    "user": {"uid": "framecut"},
                    "req_params": {"text": chunk, "speaker": speaker, "audio_params": audio_params},
                }
                if additions:
                    body["req_params"]["additions"] = additions
                resp = await client.post(url, headers=headers, json=body)
                if resp.status_code >= 400:
                    raise OpenspeechError(
                        f"openspeech HTTP {resp.status_code}: {resp.text[:300]}", status=resp.status_code
                    )
                piece = parse_openspeech_ndjson(resp.content)
                if not piece:
                    raise UpstreamError("openspeech trả về âm thanh rỗng")
                parts.append(piece)
        return b"".join(parts)

    def cost_fen(self, model: str, raw_usage: dict[str, Any] | None) -> int | None:
        """Chi phí fen theo provider_rates; openspeech không trả usage nên thực tế luôn None."""
        from app.services.billing.provider_rates import provider_cost_fen

        return provider_cost_fen(model, raw_usage)

    def url_needs_auth(self, url: str) -> bool:
        """URLs from Volc TTS do not need authentication."""
        return False

    def is_transient_error(self, exc: BaseException) -> bool:
        """Lỗi mạng, HTTP 429/5xx, mã 55000000 hoặc vượt quota concurrency là tạm thời."""
        if isinstance(exc, httpx.TransportError):
            return True
        if isinstance(exc, OpenspeechError):
            if exc.code in _TRANSIENT_CODES:
                return True
            if exc.status is not None and (exc.status == 429 or exc.status >= 500):
                return True
            return "quota exceeded" in str(exc).lower()
        return False
