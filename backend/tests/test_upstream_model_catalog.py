"""list_upstream_models: bắt buộc key với ark/volc_tts, bọc lỗi mạng thành RuntimeError dễ đọc."""
from __future__ import annotations

import httpx
import pytest

from app.services.providers import openai_adapter
from app.services.upstream_model_catalog import list_upstream_models


async def test_ark_requires_api_key():
    with pytest.raises(RuntimeError, match="API key"):
        await list_upstream_models(None, protocol="ark", base_url="https://x", api_key_override="")


async def test_ark_with_key_returns_static_list():
    models = await list_upstream_models(None, protocol="ark", base_url="https://x", api_key_override="ak")
    assert models
    assert any(m["capability"] == "image" for m in models)


async def test_volc_tts_requires_api_key_without_legacy_pair(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "volc_tts_app_id", "")
    monkeypatch.setattr(settings, "volc_tts_access_key", "")
    with pytest.raises(RuntimeError, match="API key"):
        await list_upstream_models(None, protocol="volc_tts", base_url="https://x", api_key_override="")


async def test_volc_tts_accepts_legacy_app_id_access_key_pair(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "volc_tts_app_id", "app")
    monkeypatch.setattr(settings, "volc_tts_access_key", "ak")
    models = await list_upstream_models(None, protocol="volc_tts", base_url="https://x", api_key_override="")
    assert models


async def test_network_error_wrapped_as_runtime_error(monkeypatch):
    """httpx.ConnectError/TimeoutException/ValueError từ adapter không được lọt ra ngoài thành 500."""

    class _RaisingClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(openai_adapter.httpx, "AsyncClient", _RaisingClient)
    with pytest.raises(RuntimeError, match="Không kết nối được"):
        await list_upstream_models(None, protocol="openai", base_url="https://x", api_key_override="k")
