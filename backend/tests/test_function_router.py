"""function_router: lọc provider hỏng, weight ngẫu nhiên, validate model user chọn, failover."""
import random
from types import SimpleNamespace

import pytest

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import function_router as fr


def _ch(cid, protocol, models, key="k", enabled=True):
    return SystemModelChannel(id=cid, name=cid, base_url="https://x", api_key=key, has_api_key=bool(key),
                              protocol=protocol, models=list(models), enabled=enabled)


def _snap(bindings, channels):
    return SimpleNamespace(channels=channels, function_bindings=bindings)


BYTE = _ch("byteplus", "ark", ["dola-seedream-5-0-pro-260628", "dreamina-seedance-2-5-260628"])
OAI = _ch("openai", "openai", ["gpt-image-2.5-sunburst", "gpt-5.6-sol"])


def test_route_fields():
    snap = _snap(FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")]}), [BYTE])
    r = fr.resolve_function_route("kepu.image", snapshot=snap)
    assert r and r.channel_id == "byteplus" and r.protocol == "ark" and r.api_format == "ark"
    assert r.upstream_model == "dola-seedream-5-0-pro-260628" and r.logical_model_id == "kepu.image" and r.api_key == "k"


def test_disabled_or_keyless_provider_filtered():
    snap = _snap(FunctionBindings(slots={"image": [ModelBinding(channel_id="openai", model="gpt-image-2.5-sunburst")]}),
                 [_ch("openai", "openai", ["gpt-image-2.5-sunburst"], key="")])
    assert fr.allowed_bindings("kepu.image", snapshot=snap) == []
    assert fr.resolve_function_route("kepu.image", snapshot=snap) is None


def test_model_not_in_provider_list_filtered():
    snap = _snap(FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="removed")]}), [BYTE])
    assert fr.allowed_bindings("kepu.image", snapshot=snap) == []


def test_requested_model_must_be_allowed():
    snap = _snap(FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")]}), [BYTE, OAI])
    assert fr.is_model_allowed("kepu.image", "DOLA-Seedream-5-0-Pro-260628", snapshot=snap)
    assert not fr.is_model_allowed("kepu.image", "gpt-image-2.5-sunburst", snapshot=snap)
    with pytest.raises(fr.ModelNotAllowed):
        fr.resolve_function_candidates("kepu.image", "gpt-image-2.5-sunburst", snapshot=snap)


def test_requested_model_goes_first_then_others():
    b = FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628"),
                                          ModelBinding(channel_id="openai", model="gpt-image-2.5-sunburst")]})
    cands = fr.resolve_function_candidates("kepu.image", "gpt-image-2.5-sunburst", snapshot=_snap(b, [BYTE, OAI]))
    assert [c.upstream_model for c in cands] == ["gpt-image-2.5-sunburst", "dola-seedream-5-0-pro-260628"]


def test_weighted_pick_is_random_but_seeded():
    b = FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628", weight=1),
                                          ModelBinding(channel_id="openai", model="gpt-image-2.5-sunburst", weight=99)]})
    snap = _snap(b, [BYTE, OAI])
    firsts = {fr.resolve_function_route("kepu.image", snapshot=snap, rng=random.Random(i)).upstream_model for i in range(30)}
    assert "gpt-image-2.5-sunburst" in firsts          # weight 99 thắng đa số
    counts = sum(1 for i in range(200) if fr.resolve_function_route("kepu.image", snapshot=snap, rng=random.Random(i)).upstream_model == "gpt-image-2.5-sunburst")
    assert counts > 150


def test_override_beats_slot():
    b = FunctionBindings(slots={"image": [ModelBinding(channel_id="byteplus", model="dola-seedream-5-0-pro-260628")]},
                         overrides={"tools.image": [ModelBinding(channel_id="openai", model="gpt-image-2.5-sunburst")]})
    snap = _snap(b, [BYTE, OAI])
    assert fr.resolve_function_route("tools.image", snapshot=snap).channel_id == "openai"
    assert fr.resolve_function_route("kepu.image", snapshot=snap).channel_id == "byteplus"


def test_route_for_channel():
    snap = _snap(FunctionBindings(), [BYTE])
    r = fr.route_for_channel("byteplus", "dreamina-seedance-2-5-260628", "video", snapshot=snap)
    assert r and r.protocol == "ark"
    assert fr.route_for_channel("nope", "m", "video", snapshot=snap) is None


def test_openai_ark_provider_without_base_url_filtered():
    """openai/ark thiếu base URL thì không dùng được dù có key; volc_tts chỉ cần key."""
    no_base = SystemModelChannel(id="openai", name="openai", base_url="", api_key="k", has_api_key=True,
                                 protocol="openai", models=["gpt-5.6-sol"], enabled=True)
    assert not fr._channel_ok(no_base)
    volc = SystemModelChannel(id="volc", name="volc", base_url="", api_key="k", has_api_key=True,
                              protocol="volc_tts", models=["seed-tts-2.0"], enabled=True)
    assert fr._channel_ok(volc)
