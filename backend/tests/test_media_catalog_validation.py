"""Catalog phía user lấy từ slot/override; scope kepu/drama/tools; validate model dự án."""
import pytest

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import media_catalog
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot


@pytest.fixture
def snap():
    """Snapshot routing: slot ảnh/video của BytePlus, override tools.image sang OpenAI."""
    prev = get_routing_snapshot()
    byte = SystemModelChannel(id="byteplus", name="BytePlus", base_url="https://x", api_key="k", has_api_key=True, protocol="ark",
                              models=["dola-seedream-5-0-pro-260628", "dreamina-seedance-2-5-260628"], enabled=True)
    oai = SystemModelChannel(id="openai", name="OpenAI", base_url="https://x", api_key="k", has_api_key=True, protocol="openai", models=["gpt-image-2"], enabled=True)
    b = FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")],
                                "video": [ModelBinding(channel_id="byteplus", model="dreamina-seedance-2-5-260628")]},
                         overrides={"tools.image": [ModelBinding(channel_id="openai", model="gpt-image-2")]})
    _refresh_routing_snapshot([byte, oai], b)
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


def test_scope_kepu_lists_slot_models(snap):
    cat = media_catalog.catalog_payload("kepu")
    assert [m["id"] for m in cat["image_models"]] == ["dola-seedream-5-0-pro-260628"]
    assert cat["image_models"][0]["provider"] == "byteplus" and cat["image_models"][0]["recommended"]
    assert cat["defaults"] == {"image_model": "dola-seedream-5-0-pro-260628", "video_model": "dreamina-seedance-2-5-260628"}


def test_scope_tools_uses_override(snap):
    cat = media_catalog.catalog_payload("tools")
    assert [m["id"] for m in cat["image_models"]] == ["gpt-image-2"]


def test_no_scope_is_union(snap):
    ids = {m["id"] for m in media_catalog.catalog_payload()["image_models"]}
    assert ids == {"dola-seedream-5-0-pro-260628", "gpt-image-2"}


def test_project_model_validation(snap):
    assert media_catalog.is_valid_project_media_model("", "image")
    assert media_catalog.is_valid_project_media_model("dola-seedream-5-0-pro-260628", "image")
    assert not media_catalog.is_valid_project_media_model("gpt-image-2", "image")     # chỉ override tools
    assert not media_catalog.is_valid_project_media_model("garbage", "video")


def test_empty_config_gives_empty_lists():
    prev = get_routing_snapshot(); _refresh_routing_snapshot([], FunctionBindings())
    try:
        cat = media_catalog.catalog_payload("drama")
        assert cat["image_models"] == [] and cat["defaults"]["image_model"] == ""
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)
