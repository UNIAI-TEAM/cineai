"""Model đã lưu trong dự án khoa học: id cũ không còn được phép thì để slot tự quyết, không raise."""
import pytest

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot
from app.services.pipeline import _effective_project_model


@pytest.fixture
def snap():
    """Chỉ cho phép đúng một model ảnh X cho kepu.image."""
    prev = get_routing_snapshot()
    ch = SystemModelChannel(id="byteplus", name="BytePlus", base_url="https://x", api_key="k", has_api_key=True,
                            protocol="ark", models=["X"], enabled=True)
    _refresh_routing_snapshot([ch], FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="X")]}))
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


def test_legacy_model_degrades_to_slot(snap):
    assert _effective_project_model("kepu.image", "kie-old") is None
    assert _effective_project_model("kepu.image", "ark-seedream") is None


def test_allowed_model_passes_through(snap):
    assert _effective_project_model("kepu.image", "X") == "X"


def test_empty_model_is_none(snap):
    assert _effective_project_model("kepu.image", "") is None
    assert _effective_project_model("kepu.image", None) is None
