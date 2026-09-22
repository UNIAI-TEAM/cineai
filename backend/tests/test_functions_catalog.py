"""Danh mục chức năng cố định: 10 mục, đúng năng lực."""
from app.services import functions


def test_catalog_has_ten_functions_in_spec_order():
    ids = [f.id for f in functions.FUNCTIONS]
    assert ids == ["kepu.script", "drama.script", "kepu.image", "drama.asset_image", "tools.image",
                   "kepu.video", "drama.video", "tools.video", "kepu.tts", "drama.tts"]


def test_capabilities():
    assert functions.function_capability("kepu.image") == "image"
    assert functions.function_capability("drama.tts") == "audio"
    assert functions.function_capability("tools.video") == "video"
    assert functions.function_capability("drama.script") == "text"


def test_payload_has_labels():
    row = functions.function_catalog_payload()[0]
    assert row["id"] == "kepu.script" and row["label"] and row["capability"] == "text"
