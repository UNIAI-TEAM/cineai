"""Registry adapter theo protocol; import lười để tránh vòng import."""

from __future__ import annotations

from app.services.providers.base import ProviderAdapter, ProviderNotSupported

_CACHE: dict[str, ProviderAdapter] = {}


def get_adapter(protocol: str) -> ProviderAdapter:
    """Trả adapter singleton theo protocol; `auto`/rỗng coi là openai."""
    proto = (protocol or "openai").strip().lower()
    if proto == "auto":
        proto = "openai"
    if proto in _CACHE:
        return _CACHE[proto]
    if proto == "openai":
        from app.services.providers.openai_adapter import OpenAIAdapter as cls
    elif proto == "ark":
        from app.services.providers.ark_adapter import ArkAdapter as cls
    elif proto == "volc_tts":
        from app.services.providers.volc_tts_adapter import VolcTtsAdapter as cls
    else:
        raise ProviderNotSupported(f"protocol không hỗ trợ: {proto}")
    _CACHE[proto] = cls()
    return _CACHE[proto]


def url_needs_auth(url: str) -> bool:
    """URL có cần Bearer khi tải không (hỏi mọi adapter)."""
    return any(get_adapter(p).url_needs_auth(url) for p in ("openai", "ark", "volc_tts"))
