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
    from app.schemas_routing import DefaultModels, LogicalModel, SystemModelChannel
    from app.services.media_catalog import build_media_catalog

    payload = build_media_catalog(
        logical_models=[
            LogicalModel(id="seedream-5.0", name="Seedream 5.0", capability="image", enabled=True),
            LogicalModel(id="seedance-2.5", name="Seedance 2.5", capability="video", enabled=True),
        ],
        channels=[
            SystemModelChannel(
                id="tokenfree",
                name="TokenFree",
                base_url="https://www.tokenfree.com/v1",
                models=["doubao-seedance-2-5-260628"],
                enabled=True,
            )
        ],
        defaults=DefaultModels(image_model="seedream-5.0", video_model="seedance-2.5"),
    )
    assert payload["defaults"]["video_model"] == "seedance-2.5"
    assert any(m["id"] == "seedance-2.5" for m in payload["video_models"])
    assert all(m["provider"] == "tokenfree" for m in payload["video_models"])
    assert not any("kie" in m["id"] for m in payload["video_models"])
    assert not any("方舟" in m["label"] for m in payload["video_models"])
