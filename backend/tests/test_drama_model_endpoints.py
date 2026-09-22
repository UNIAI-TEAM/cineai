"""Resolver model ảnh/video phim ngắn: id được phép giữ nguyên, id lạ/rỗng rơi về model của slot."""
import pytest

from app.config import get_settings
from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services.drama.build_seedance_generate_body import resolve_seedance_model_endpoint
from app.services.drama.seedream_options import resolve_seedream_model_endpoint
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot

_CHANNEL = SystemModelChannel(id="byteplus", name="BytePlus", base_url="https://x", api_key="k", has_api_key=True,
                              protocol="ark", models=["img-a", "img-b", "vid-a", "vid-b"], enabled=True)


def _bind(image_models, video_models):
    """Gán slot ảnh/video theo danh sách model cho trước."""
    return FunctionBindings(slots={
        "image": [ModelBinding(channel_id="byteplus", model=m) for m in image_models],
        "video": [ModelBinding(channel_id="byteplus", model=m) for m in video_models],
    })


@pytest.fixture
def multi_snap():
    """Mỗi slot hai model: đủ để kiểm tra id user chọn được ưu tiên."""
    prev = get_routing_snapshot()
    _refresh_routing_snapshot([_CHANNEL], _bind(["img-a", "img-b"], ["vid-a", "vid-b"]))
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


@pytest.fixture
def single_snap():
    """Mỗi slot đúng một model: model mặc định của slot là xác định."""
    prev = get_routing_snapshot()
    _refresh_routing_snapshot([_CHANNEL], _bind(["img-a"], ["vid-a"]))
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


@pytest.fixture
def empty_snap():
    """Chưa gán binding nào."""
    prev = get_routing_snapshot()
    _refresh_routing_snapshot([], FunctionBindings())
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


def test_seedream_allowed_id_passes_through(multi_snap):
    assert resolve_seedream_model_endpoint("img-b") == "img-b"
    assert resolve_seedream_model_endpoint(" img-a ") == "img-a"


def test_seedream_empty_uses_slot_default(single_snap):
    assert resolve_seedream_model_endpoint("") == "img-a"
    assert resolve_seedream_model_endpoint(None) == "img-a"


def test_seedream_not_allowed_falls_back_without_raising(single_snap):
    assert resolve_seedream_model_endpoint("seedream-4.5") == "img-a"


def test_seedream_without_bindings_uses_settings(empty_snap):
    assert resolve_seedream_model_endpoint("") == get_settings().model_image
    # Chưa gán slot thì id user chọn được giữ nguyên cho upstream tự phán
    assert resolve_seedream_model_endpoint("anything") == "anything"


def test_seedance_allowed_id_passes_through(multi_snap):
    assert resolve_seedance_model_endpoint("vid-b") == "vid-b"


def test_seedance_empty_uses_slot_default(single_snap):
    assert resolve_seedance_model_endpoint("") == "vid-a"


def test_seedance_not_allowed_falls_back_without_raising(single_snap):
    assert resolve_seedance_model_endpoint("seedance-2") == "vid-a"


def test_seedance_without_bindings_uses_settings(empty_snap):
    assert resolve_seedance_model_endpoint("") == get_settings().model_video
