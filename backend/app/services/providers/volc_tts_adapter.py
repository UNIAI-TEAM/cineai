"""Volcengine/BytePlus Seed Speech (openspeech) adapter: NDJSON → bytes, speaker + emotion."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

from app.schemas_routing import ResolvedModelRoute
from app.services.providers.base import ProviderNotSupported, TtsRequest, UpstreamError

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


def resolve_volc_speaker(voice: str, default: str) -> str:
    """Resolve voice name to speaker using SPEAKER_ALIASES or fallback to default."""
    return SPEAKER_ALIASES.get(voice, voice) or default


# Speaker id kiểu Volc/BytePlus: zh_/en_/ja_/multi_… (vd. zh_female_cancan_uranus_bigtts)
_VOLC_SPEAKER_RE = re.compile(r"^(zh|en|ja|es|id|pt|multi)_[a-z0-9]+_")


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


def build_tts_additions(speaker: str, emotion_hint: str | None) -> str | None:
    """Assemble openspeech additions (S_ clone + emotion context_texts)."""
    additions: dict[str, Any] = {}
    if speaker.startswith("S_"):
        additions["model_type"] = 4
    hint = (emotion_hint or "").strip()
    if hint:
        additions["context_texts"] = [f"用「{hint}」的语气朗读"]
    if not additions:
        return None
    return json.dumps(additions, ensure_ascii=False)


def parse_openspeech_ndjson(raw: bytes) -> bytes:
    """Parse openspeech NDJSON response: concatenate base64-decoded chunks until code 20000000."""
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
        """Convert text to speech via openspeech, return audio bytes."""
        from app.config import get_settings

        settings = get_settings()
        speaker = resolve_volc_speaker(req.voice, settings.volc_tts_speaker or "zh_female_cancan_uranus_bigtts")
        resource = resource_id_for_speaker(speaker, settings.volc_tts_resource_id or "seed-tts-2.0")
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-Api-Resource-Id": resource,
        }
        api_key = (route.api_key or "").strip()
        if api_key:
            headers["X-Api-Key"] = api_key
        else:
            headers["X-Api-App-Id"] = settings.volc_tts_app_id
            headers["X-Api-Access-Key"] = settings.volc_tts_access_key

        body: dict[str, Any] = {
            "user": {"uid": "framecut"},
            "req_params": {
                "text": req.text,
                "speaker": speaker,
                "audio_params": {"format": "mp3", "sample_rate": 24000},
            },
        }
        additions = build_tts_additions(speaker, req.emotion_hint)
        if additions:
            body["req_params"]["additions"] = additions

        url = route.base_url or settings.volc_tts_url or VOLC_TTS_DEFAULT_URL
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            raise UpstreamError(f"openspeech HTTP {resp.status_code}: {resp.text[:300]}")
        audio = parse_openspeech_ndjson(resp.content)
        if not audio:
            raise UpstreamError("openspeech trả về âm thanh rỗng")
        return audio

    def cost_fen(self, model: str, raw_usage: dict[str, Any] | None) -> int | None:
        """Chi phí fen theo provider_rates; openspeech không trả usage nên thực tế luôn None."""
        from app.services.billing.provider_rates import provider_cost_fen

        return provider_cost_fen(model, raw_usage)

    def url_needs_auth(self, url: str) -> bool:
        """URLs from Volc TTS do not need authentication."""
        return False

    def is_transient_error(self, exc: BaseException) -> bool:
        """Check if error is transient (network/transport error)."""
        return isinstance(exc, httpx.TransportError)
