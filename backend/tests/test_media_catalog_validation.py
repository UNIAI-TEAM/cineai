"""项目 image_model / video_model 校验与前台目录一致。"""

from app.services.media_catalog import is_valid_project_media_model


def test_legacy_seedream_names_infer_image():
    """旧项目里的 kie-/ark- 名仍可按能力推断，避免打开项目直接校验失败。"""
    assert is_valid_project_media_model("kie-seedream-5", "image") is True
    assert is_valid_project_media_model("ark-seedream", "image") is True


def test_empty_model_allowed():
    assert is_valid_project_media_model("", "image") is True
    assert is_valid_project_media_model("  ", "video") is True


def test_garbage_model_rejected():
    assert is_valid_project_media_model("not-a-real-model-xyz", "image") is False


def test_tokenfree_style_ids_infer_capability():
    from app.services.model_routing_config import infer_model_capability

    assert infer_model_capability("gpt-image-2-5") == "image"
    assert infer_model_capability("seedance-2-0-mini") == "video"
    assert infer_model_capability("kie-veo3-fast") == "video"
    assert infer_model_capability("kie-seedream-5") == "image"
    assert infer_model_capability("nano-banana-2") == "image"
    assert infer_model_capability("qwen-tts-2025-05-22") == "audio"
    assert infer_model_capability("gemini-3.1-flash-tts") == "audio"
    assert infer_model_capability("elevenlabs/text-to-speech-multilingual-v2") == "audio"
    assert infer_model_capability("elevenlabs-tts") == "audio"


def test_catalog_payload_uses_tokenfree_routing() -> None:
    """catalog_payload() phải suy ra image/video từ function_bindings hiệu lực của snapshot routing."""
    from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
    from app.services.media_catalog import catalog_payload
    from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot

    prev = get_routing_snapshot()
    try:
        channel = SystemModelChannel(
            id="tokenfree",
            name="TokenFree",
            base_url="https://www.tokenfree.com/v1",
            api_key="k",
            has_api_key=True,
            protocol="openai",
            models=["doubao-seedance-2-5-260628"],
            enabled=True,
        )
        bindings = FunctionBindings(
            slots={"video": [ModelBinding(channel_id="tokenfree", model="doubao-seedance-2-5-260628")]}
        )
        _refresh_routing_snapshot([channel], bindings)
        payload = catalog_payload()
        assert payload["defaults"]["video_model"] == "doubao-seedance-2-5-260628"
        assert any(m["id"] == "doubao-seedance-2-5-260628" for m in payload["video_models"])
        assert all(m["provider"] == "tokenfree" for m in payload["video_models"])
        assert not any("kie" in m["id"] for m in payload["video_models"])
        assert not any("方舟" in m["label"] for m in payload["video_models"])
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)
