"""I-7: /api/health báo trạng thái model theo slot routing, không phải nhãn MODEL_* trong env."""
from __future__ import annotations

import pytest

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import model_settings as ms


@pytest.fixture
def text_only_snapshot():
    """Chỉ gán slot text; các slot khác chưa gán."""
    prev = ms.get_routing_snapshot()
    ch = SystemModelChannel(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="k", has_api_key=True,
                            protocol="openai", models=["gpt-5.6-sol"], enabled=True)
    ms._refresh_routing_snapshot([ch], FunctionBindings(slots={"text": [ModelBinding(channel_id="openai", model="gpt-5.6-sol")]}))
    yield
    ms._refresh_routing_snapshot(prev.channels, prev.function_bindings)


async def test_health_models_follow_routing_slots(text_only_snapshot):
    from app.main import health

    out = await health()
    models = out["models"]
    assert models["text"] == {"status": "ready", "model": "gpt-5.6-sol"}
    for cap in ("image", "video", "audio"):
        assert models[cap]["status"] == "not_configured"


async def test_health_models_unknown_on_error(text_only_snapshot, monkeypatch):
    from app.main import health

    def _boom(*_a, **_k):
        raise RuntimeError("x")

    monkeypatch.setattr(ms, "_build_readiness", _boom)
    out = await health()
    assert out["models"] == {cap: {"status": "unknown", "model": ""} for cap in ("text", "image", "video", "audio")}
