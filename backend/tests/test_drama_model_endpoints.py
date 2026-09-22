"""Resolver model ảnh/video phim ngắn: id được phép giữ nguyên, id lạ/rỗng rơi về binding đầu của slot."""
import pytest

from app.config import get_settings
from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services.drama.build_seedance_generate_body import resolve_seedance_model_endpoint
from app.services.drama.seedream_options import resolve_seedream_model_endpoint
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
    """Rỗng / id không được phép đều phải ra binding đầu, không xáo theo weight."""
    assert [resolve_seedream_model_endpoint("") for _ in range(20)] == ["img-a"] * 20
    assert [resolve_seedream_model_endpoint(None) for _ in range(20)] == ["img-a"] * 20
    assert [resolve_seedream_model_endpoint("seedream-4.5") for _ in range(20)] == ["img-a"] * 20


def test_seedream_without_bindings_uses_settings(empty_snap):
    """Chưa gán slot: cả id rỗng lẫn id user chọn đều rơi về mặc định trong settings."""
    assert resolve_seedream_model_endpoint("") == get_settings().model_image
    assert resolve_seedream_model_endpoint("anything") == get_settings().model_image


def test_seedance_allowed_id_passes_through(snap):
    assert resolve_seedance_model_endpoint("vid-b") == "vid-b"


def test_seedance_default_branch_is_deterministic(snap):
    """Rỗng / id không được phép đều phải ra binding đầu, không xáo theo weight."""
    assert [resolve_seedance_model_endpoint("") for _ in range(20)] == ["vid-a"] * 20
    assert [resolve_seedance_model_endpoint("seedance-2") for _ in range(20)] == ["vid-a"] * 20


def test_seedance_without_bindings_uses_settings(empty_snap):
    """Chưa gán slot: cả id rỗng lẫn id user chọn đều rơi về mặc định trong settings."""
    assert resolve_seedance_model_endpoint("") == get_settings().model_video
    assert resolve_seedance_model_endpoint("seedance-2") == get_settings().model_video
