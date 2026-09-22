"""I-2: key đã lưu chỉ được dùng lại khi host (scheme+host+port) không đổi."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.schemas_routing import AdminRoutingSettingsPatch, SystemModelChannel, SystemModelChannelIn
from app.services import model_settings as ms
from app.services.providers.host_guard import HOST_CHANGED_MESSAGE, ProviderHostChangedError, same_host
from app.services.upstream_model_catalog import _resolve_channel_credentials

@pytest.fixture(autouse=True)
def _isolate_global_routing_state():
    """PATCH/nạp cache ghi đè overlay + snapshot toàn process; khôi phục sau mỗi test."""
    from app import config as config_module

    saved_overlay = dict(ms._overlay)
    saved_snapshot = ms.get_routing_snapshot()
    yield
    ms._overlay.clear()
    ms._overlay.update(saved_overlay)
    ms._refresh_routing_snapshot(saved_snapshot.channels, saved_snapshot.function_bindings)
    config_module.get_settings.cache_clear()


_STORED = SystemModelChannel(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="sk-stored",
                             has_api_key=True, protocol="openai", models=["gpt-5.6-sol"], enabled=True)


@pytest.fixture
def stored_channel(monkeypatch):
    """Giả lập DB có sẵn provider openai với key đã lưu."""

    async def _fake_load(_db, *, runtime: bool):
        return [_STORED]

    monkeypatch.setattr(ms, "_load_channels", _fake_load)


def test_same_host_normalizes_scheme_host_port():
    assert same_host("https://API.openai.com/v1", "https://api.openai.com:443/other")
    assert not same_host("https://api.openai.com/v1", "http://api.openai.com/v1")
    assert not same_host("https://api.openai.com/v1", "https://attacker.example/v1")
    assert not same_host("https://api.openai.com/v1", "https://api.openai.com:8443/v1")


async def test_changed_host_without_key_is_rejected(stored_channel):
    with pytest.raises(ProviderHostChangedError):
        await _resolve_channel_credentials(object(), channel_id="openai", protocol="openai",
                                           base_url="https://attacker.example/v1", api_key_override=None)


async def test_same_host_reuses_stored_key(stored_channel):
    _, base, key = await _resolve_channel_credentials(object(), channel_id="openai", protocol="openai",
                                                      base_url="https://api.openai.com/v1/", api_key_override=None)
    assert key == "sk-stored" and base == "https://api.openai.com/v1"


async def test_changed_host_with_new_key_is_allowed(stored_channel):
    _, base, key = await _resolve_channel_credentials(object(), channel_id="openai", protocol="openai",
                                                      base_url="https://other.example/v1", api_key_override="sk-new")
    assert key == "sk-new" and base == "https://other.example/v1"


async def test_provider_test_endpoint_returns_400_on_host_change(stored_channel):
    from app.api.admin.settings import AdminProviderTestRequest, AdminUpstreamModelsRequest, admin_list_upstream_models, admin_test_provider

    with pytest.raises(HTTPException) as exc:
        await admin_test_provider(AdminProviderTestRequest(channel_id="openai", protocol="openai", base_url="https://attacker.example/v1"),
                                  _admin=None, db=object())
    assert exc.value.status_code == 400 and exc.value.detail == HOST_CHANGED_MESSAGE
    with pytest.raises(HTTPException) as exc:
        await admin_list_upstream_models(AdminUpstreamModelsRequest(channel_id="openai", protocol="openai", base_url="https://attacker.example/v1"),
                                         _admin=None, db=object())
    assert exc.value.status_code == 400 and exc.value.detail == HOST_CHANGED_MESSAGE


async def test_patch_rejects_host_change_without_new_key(db_session):
    first = AdminRoutingSettingsPatch(providers=[
        SystemModelChannelIn(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="sk-old", protocol="openai", models=["gpt-5.6-sol"]),
    ])
    await ms.patch_admin_routing_settings(db_session, first)
    moved = AdminRoutingSettingsPatch(providers=[
        SystemModelChannelIn(id="openai", name="OpenAI", base_url="https://attacker.example/v1", api_key=None, protocol="openai", models=["gpt-5.6-sol"]),
    ])
    with pytest.raises(ValueError) as exc:
        await ms.patch_admin_routing_settings(db_session, moved)
    assert str(exc.value) == HOST_CHANGED_MESSAGE


def test_api_key_not_in_repr():
    """M-1: repr của route/provider runtime không được lộ API key vào log."""
    from app.schemas_routing import ResolvedModelRoute

    route = ResolvedModelRoute(capability="text", logical_model_id="kepu.script", upstream_model="m", channel_id="openai",
                               channel_name="OpenAI", base_url="https://api.openai.com/v1", api_key="sk-secret-123",
                               protocol="openai", api_format="openai")
    assert "sk-secret-123" not in repr(route) and "sk-secret-123" not in str(route)
    assert "sk-stored" not in repr(_STORED) and "sk-stored" not in str(_STORED)
    assert route.api_key == "sk-secret-123"
