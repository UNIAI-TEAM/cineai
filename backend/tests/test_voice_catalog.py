"""Danh mục giọng BytePlus vi/en: đủ dữ liệu, giọng mới không vào pool tự động, catalog theo ngôn ngữ."""

from app.services import voices
from app.services.voice_lang import default_voice_for_lang, lang_voice_pool, voice_supports_lang


def _by_lang(lang):
    return [p for p in voices.VOICE_PRESETS if lang in p["languages"]]


def test_catalog_counts():
    assert len(voices.catalog_voices("vi")) == 7
    assert len(voices.catalog_voices("en")) == 68
    assert voices.catalog_voices("fr") == []
    assert voices.catalog_voices(None) == []


def test_catalog_item_shape_and_order():
    first = voices.catalog_voices("vi")[0]
    assert first == {
        "id": "vi_female_ruan_uranus_bigtts",
        "speaker": "vi_female_ruan_uranus_bigtts",
        "name": "Ruan",
        "gender": "female",
        "scenario": "General",
        "description": first["description"],
        "sample_url": first["sample_url"],
    }
    assert first["description"] and first["sample_url"].startswith("https://")


def test_new_voices_excluded_from_auto_pool_and_list_voices():
    assert lang_voice_pool("en") == [
        "en_female_hayley_uranus_bigtts",
        "en_male_tim_uranus_bigtts",
        "en_female_skye_uranus_bigtts",
        "en_female_jenny_uranus_bigtts",
        "en_male_kevin_uranus_bigtts",
        "en_male_marcus_uranus_bigtts",
    ]
    assert default_voice_for_lang("en", "male") == "en_male_tim_uranus_bigtts"
    listed = {v["id"] for v in voices.list_voices()}
    assert "en_male_bruce_uranus_bigtts" not in listed
    assert "en_male_tim_uranus_bigtts" in listed


def test_new_voices_still_known_for_language_checks():
    assert voice_supports_lang("en_male_bruce_uranus_bigtts", "en")
    assert not voice_supports_lang("en_male_bruce_uranus_bigtts", "vi")


def test_all_vi_en_presets_have_catalog_fields():
    for p in _by_lang("vi") + _by_lang("en"):
        for key in ("name", "scenario", "description", "sample_url", "auto_pool", "label_i18n"):
            assert key in p, (p["id"], key)
