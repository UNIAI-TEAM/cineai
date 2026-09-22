"""Preset provider cho admin: điền sẵn protocol/base URL và cách lấy danh sách model."""

from __future__ import annotations

from app.schemas_routing import ProviderPreset
from app.services.providers.ark_adapter import ARK_DEFAULT_BASE_URL, ARK_STATIC_MODELS
from app.services.providers.openai_adapter import OPENAI_DEFAULT_BASE_URL
from app.services.providers.volc_tts_adapter import BYTEPLUS_TTS_URL, VOLC_TTS_STATIC_MODELS

PROVIDER_PRESETS: list[ProviderPreset] = [
    ProviderPreset(id="openai", name="OpenAI", protocol="openai", base_url=OPENAI_DEFAULT_BASE_URL, catalog="remote"),
    ProviderPreset(id="byteplus", name="BytePlus ModelArk", protocol="ark", base_url=ARK_DEFAULT_BASE_URL, catalog="static", models=ARK_STATIC_MODELS),
    ProviderPreset(id="openrouter", name="OpenRouter", protocol="openai", base_url="https://openrouter.ai/api/v1", catalog="remote"),
    ProviderPreset(id="volc_tts", name="BytePlus Seed Speech", protocol="volc_tts", base_url=BYTEPLUS_TTS_URL, catalog="static", models=VOLC_TTS_STATIC_MODELS),
    ProviderPreset(id="custom_openai", name="OpenAI-compatible tuỳ chỉnh", protocol="openai", base_url="", catalog="remote"),
]


def preset_by_id(pid: str) -> ProviderPreset | None:
    """Tra preset theo id."""
    return next((p for p in PROVIDER_PRESETS if p.id == pid), None)
