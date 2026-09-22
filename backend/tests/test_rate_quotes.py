"""rate_quotes: đơn giá ước tính theo chức năng = model đắt nhất trong slot hiệu lực × provider_rates."""
from __future__ import annotations

from types import SimpleNamespace

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services.billing import rate_quotes as rq
from app.services.model_settings import RoutingSnapshot

S = SimpleNamespace(
    billing_usd_cny=7.0, billing_est_seedream_tokens=45_000, billing_seedream_per_m=8.0,
    billing_seedance_video0=46.0, billing_seedance_video1=28.0, billing_llm_per_m=5.0, billing_tts_per_m=2.0,
    billing_markup=1.0, ark_video_resolution="480p",
    model_llm="gpt-5.6-sol", model_image="dola-seedream-5-0-pro-260628",
    model_video="dreamina-seedance-2-5-260628", model_audio="gpt-4o-mini-tts",
)


def _ch(cid, protocol, models, enabled=True):
    return SystemModelChannel(id=cid, name=cid, base_url="https://x", api_key="k", has_api_key=True,
                              protocol=protocol, models=models, enabled=enabled)


def _snap(slots, channels=None):
    channels = channels or [
        _ch("byteplus", "ark", ["dola-seedream-5-0-pro-260628", "seedream-5-0-260128", "ep-2026-img",
                                "dreamina-seedance-2-5-260628", "dreamina-seedance-2-0-fast-260128"]),
        _ch("openai", "openai", ["gpt-image-2", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-4o-mini-tts"]),
    ]
    return RoutingSnapshot(channels=channels, function_bindings=FunctionBindings(slots={
        cap: [ModelBinding(channel_id=c, model=m) for c, m in items] for cap, items in slots.items()
    }))


def test_video_tokens_formula():
    assert rq.video_tokens(5, "480p") == 48_600
    assert rq.video_tokens(5, "720p") == 108_000
    assert rq.video_tokens(1, "480p") == rq.video_tokens(2, "480p")      # tối thiểu 2 giây


def test_image_unit_takes_max_per_image_in_slot():
    snap = _snap({"image": [("byteplus", "seedream-5-0-260128"), ("byteplus", "dola-seedream-5-0-pro-260628")]})
    assert rq.image_unit_fen("kepu.image", settings=S, snapshot=snap) == 32     # 0.045 USD


def test_image_unit_token_priced_model_uses_output_token_ceiling():
    snap = _snap({"image": [("openai", "gpt-image-2")]})
    assert rq.image_unit_fen("tools.image", settings=S, snapshot=snap) == 132   # 6240 × 30 / 1e6 USD


def test_image_unit_unpriced_model_uses_token_fallback():
    snap = _snap({"image": [("byteplus", "ep-2026-img")]})
    assert rq.image_unit_fen("kepu.image", settings=S, snapshot=snap) == 36     # 45 000 token × 8 元/M


def test_video_fen_by_resolution():
    snap = _snap({"video": [("byteplus", "dreamina-seedance-2-5-260628")]})
    assert rq.video_fen("drama.video", 5, resolution="480p", settings=S, snapshot=snap) == 365
    assert rq.video_fen("drama.video", 5, resolution="720p", settings=S, snapshot=snap) == 809
    assert rq.video_fen("drama.video", 5, resolution="", settings=S, snapshot=snap) == 365      # theo settings 480p
    assert rq.video_fen("drama.video", 5, resolution="4k", settings=S, snapshot=snap) == 365    # lạ → 480p


def test_video_fen_ignores_disabled_provider():
    channels = [
        _ch("off", "ark", ["dreamina-seedance-2-5-260628"], enabled=False),
        _ch("byteplus", "ark", ["dreamina-seedance-2-0-fast-260128"]),
    ]
    snap = _snap({"video": [("off", "dreamina-seedance-2-5-260628"), ("byteplus", "dreamina-seedance-2-0-fast-260128")]},
                 channels)
    assert rq.video_fen("kepu.video", 5, resolution="480p", settings=S, snapshot=snap) == 191   # chỉ giá Fast 5.6


def test_text_fen_takes_priciest_model():
    snap = _snap({"text": [("openai", "gpt-5.6-terra"), ("openai", "gpt-5.6-sol")]})
    assert rq.text_fen("drama.script", 80_000, settings=S, snapshot=snap) == 493


def test_tts_fen_output_tokens():
    snap = _snap({"audio": [("openai", "gpt-4o-mini-tts")]})
    assert rq.tts_fen("drama.tts", 5_000, settings=S, snapshot=snap) == 42


def test_unassigned_slot_falls_back_to_settings_label():
    snap = _snap({})
    assert rq.function_models("kepu.image", settings=S, snapshot=snap) == ["dola-seedream-5-0-pro-260628"]
    assert rq.image_unit_fen("kepu.image", settings=S, snapshot=snap) == 32


def test_override_wins_over_slot():
    snap = _snap({"image": [("byteplus", "dola-seedream-5-0-pro-260628")]})
    snap.function_bindings.overrides["tools.image"] = [ModelBinding(channel_id="openai", model="gpt-image-2")]
    assert rq.function_models("tools.image", settings=S, snapshot=snap) == ["gpt-image-2"]
