"""Seed provider từ env, readiness theo slot, migration bỏ tokenfree/logical_models."""
from app.config import Settings
from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import model_settings as ms


def test_bootstrap_from_env_creates_openai_and_byteplus():
    s = Settings(openai_api_key="sk", openai_base_url="https://api.openai.com/v1", ark_api_key="ak",
                 ark_base_url="https://ark.ap-southeast.bytepluses.com/api/v3", model_llm="gpt-5.6-sol",
                 model_image="dola-seedream-5-0-pro-260628", model_video="dreamina-seedance-2-5-260628",
                 model_audio="gpt-4o-mini-tts", volc_tts_api_key="")
    chans = {c.id: c for c in ms._bootstrap_channels_from_env(s)}
    assert set(chans) == {"openai", "byteplus"}
    assert chans["openai"].protocol == "openai" and "gpt-5.6-sol" in chans["openai"].models and "gpt-4o-mini-tts" in chans["openai"].models
    assert chans["byteplus"].protocol == "ark" and chans["byteplus"].base_url.endswith("/api/v3")
    assert {"dola-seedream-5-0-pro-260628", "dreamina-seedance-2-5-260628"} <= set(chans["byteplus"].models)


def test_bootstrap_from_env_without_keys_is_empty():
    assert ms._bootstrap_channels_from_env(Settings(openai_api_key="", ark_api_key="", volc_tts_api_key="", volc_tts_app_id="")) == []


def test_bootstrap_bindings_from_env_channels():
    s = Settings(openai_api_key="sk", openai_base_url="https://api.openai.com/v1", ark_api_key="ak", model_llm="gpt-5.6-sol", model_image="dola-seedream-5-0-pro-260628",
                 model_video="dreamina-seedance-2-5-260628", model_audio="gpt-4o-mini-tts")
    b = ms._bootstrap_bindings_from_env(s, ms._bootstrap_channels_from_env(s))
    assert b.slots["text"][0].channel_id == "openai" and b.slots["image"][0].channel_id == "byteplus"
    assert b.slots["video"][0].model == "dreamina-seedance-2-5-260628" and b.slots["audio"][0].model == "gpt-4o-mini-tts"


def test_readiness_marks_unassigned_slots():
    ch = SystemModelChannel(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="k", has_api_key=True,
                            protocol="openai", models=["gpt-5.6-sol"], enabled=True)
    b = FunctionBindings(slots={"text": [ModelBinding(channel_id="openai", model="gpt-5.6-sol")]})
    rows = {r.capability: r for r in ms._build_readiness(b, [ch])}
    assert rows["text"].ready and rows["text"].model == "gpt-5.6-sol"
    assert not rows["image"].ready and "Chưa gán" in rows["image"].message


def test_migrate_legacy_config_drops_logical_models():
    cfg = {"flat": {}, "logical_models": [{"id": "x"}], "default_models": {"imageModel": "seedream-5.0"}}
    out, changed = ms._migrate_legacy_config(cfg)
    assert changed and "logical_models" not in out and "default_models" not in out and out["function_bindings"] == {"slots": {}, "overrides": {}}


def test_migrate_legacy_config_scrubs_tokenfree_flat_values():
    """flat còn sót base_url tokenfree.com / alias model chết từ bản TokenFree cũ phải bị dọn."""
    cfg = {
        "flat": {
            "ark_base_url": "https://www.tokenfree.com/v1",
            "openai_base_url": "https://www.tokenfree.com/v1",
            "model_image": "seedream-5.0",
            "model_video": "seedance-2.5",
            "model_llm": "kimi-k2.6",
        }
    }
    out, changed = ms._migrate_legacy_config(cfg)
    flat = out["flat"]
    assert changed
    assert "ark_base_url" not in flat
    assert "openai_base_url" not in flat
    assert "model_image" not in flat
    assert "model_video" not in flat
    assert flat["model_llm"] == "kimi-k2.6"


def test_bootstrap_skips_provider_pointing_at_tokenfree():
    """OPENAI_BASE_URL còn trỏ tokenfree.com thì không seed provider openai (tránh gửi key tới host chết)."""
    s = Settings(openai_api_key="tf", openai_base_url="https://www.tokenfree.com/v1", ark_api_key="",
                 ark_base_url="https://www.tokenfree.com/v1", volc_tts_api_key="", volc_tts_app_id="")
    assert ms._bootstrap_channels_from_env(s) == []
