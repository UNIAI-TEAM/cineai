"""Resolver model ảnh/video phim ngắn.

`resolve_*_model_endpoint` xác định (binding đầu) chỉ dùng để tính size/tham số; model gửi tới gateway
chỉ là model user chọn tường minh (`explicit_*_model`), không chọn thì None để slot xoay theo weight.
"""
import pytest

from app.config import get_settings
from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services.drama.build_seedance_generate_body import (
    build_seedance_generate_body,
    explicit_seedance_model,
)
from app.services.drama.seedream_options import explicit_seedream_model, resolve_seedream_model_endpoint
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot

_CHANNEL = SystemModelChannel(id="byteplus", name="BytePlus", base_url="https://x", api_key="k", has_api_key=True,
                              protocol="ark", models=["img-a", "img-b", "vid-a", "vid-b"], enabled=True)


@pytest.fixture
def snap():
    """Mỗi slot hai binding; binding đầu (img-a / vid-a) là mặc định phải luôn được chọn."""
    prev = get_routing_snapshot()
    _refresh_routing_snapshot([_CHANNEL], FunctionBindings(slots={
        "image": [ModelBinding(channel_id="byteplus", model="img-a"), ModelBinding(channel_id="byteplus", model="img-b")],
        "video": [ModelBinding(channel_id="byteplus", model="vid-a"), ModelBinding(channel_id="byteplus", model="vid-b")],
    }))
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


@pytest.fixture
def empty_snap():
    """Chưa gán binding nào."""
    prev = get_routing_snapshot()
    _refresh_routing_snapshot([], FunctionBindings())
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


def test_seedream_allowed_id_passes_through(snap):
    assert resolve_seedream_model_endpoint("img-b") == "img-b"
    assert resolve_seedream_model_endpoint(" img-a ") == "img-a"


def test_seedream_default_branch_is_deterministic(snap):
    """Chỉ dùng tính size: rỗng / id không được phép đều ra binding đầu, không xáo theo weight."""
    assert [resolve_seedream_model_endpoint("") for _ in range(20)] == ["img-a"] * 20
    assert [resolve_seedream_model_endpoint(None) for _ in range(20)] == ["img-a"] * 20
    assert [resolve_seedream_model_endpoint("seedream-4.5") for _ in range(20)] == ["img-a"] * 20


def test_seedream_without_bindings_uses_settings(empty_snap):
    """Chưa gán slot: cả id rỗng lẫn id user chọn đều rơi về mặc định trong settings."""
    assert resolve_seedream_model_endpoint("") == get_settings().model_image
    assert resolve_seedream_model_endpoint("anything") == get_settings().model_image


def test_explicit_model_is_none_when_user_chose_nothing(snap):
    """I-3: model chuyển tới gateway là None khi user không chọn (hoặc chọn id không được phép)."""
    assert explicit_seedream_model(None) is None
    assert explicit_seedream_model("") is None
    assert explicit_seedream_model("seedream-4.5") is None
    assert explicit_seedream_model(" img-b ") == "img-b"
    assert explicit_seedance_model(None) is None
    assert explicit_seedance_model("seedance-2") is None
    assert explicit_seedance_model("vid-b") == "vid-b"


def test_seedance_body_has_model_only_when_user_chose(snap):
    """Body Seedance chỉ mang `model` khi user chọn tường minh."""
    auto = build_seedance_generate_body({"content": "một cảnh", "reference": [], "model_id": None})
    assert "model" not in auto
    picked = build_seedance_generate_body({"content": "một cảnh", "reference": [], "model_id": "vid-b"})
    assert picked["model"] == "vid-b"


async def test_weighted_video_slot_is_not_pinned(snap, monkeypatch):
    """Không chọn model: gateway xoay theo weight giữa vid-a / vid-b, không luôn ghim binding đầu."""
    from app.services import media_gateway

    used: list[str] = []

    class _FakeAdapter:
        """Adapter giả: ghi lại model được gọi, trả task id."""

        async def create_video(self, route, req):
            used.append(route.upstream_model)
            return f"task-{len(used)}"

        def is_transient_error(self, exc):
            return False

    monkeypatch.setattr(media_gateway, "get_adapter", lambda _proto: _FakeAdapter())
    monkeypatch.setattr(get_settings(), "ark_mock", False)
    gw = media_gateway.MediaGateway()
    for _ in range(40):
        body = build_seedance_generate_body({"content": "một cảnh", "reference": [], "model_id": None})
        await gw.gen_video_seedance_body(body, function_id="drama.video")
    assert set(used) == {"vid-a", "vid-b"}
