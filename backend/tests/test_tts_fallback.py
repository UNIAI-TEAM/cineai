"""TTS: slot audio lỗi → edge-tts; adapter đầu OK thì dừng; tất cả hỏng → raise, không ghi im lặng."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas_routing import FunctionBindings, ModelBinding, SystemModelChannel
from app.services import tts_service as ts
from app.services.model_settings import _refresh_routing_snapshot, get_routing_snapshot
from app.services.providers import base

MP3 = b"ID3" + b"\x00" * 3000


@pytest.fixture
def audio_snapshot():
    prev = get_routing_snapshot()
    ch = SystemModelChannel(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="k", has_api_key=True,
                            protocol="openai", models=["gpt-4o-mini-tts"], enabled=True)
    _refresh_routing_snapshot([ch], FunctionBindings(slots={"audio": [ModelBinding(channel_id="openai", model="gpt-4o-mini-tts")]}))
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


def _svc(monkeypatch, tmp_path, adapter):
    monkeypatch.setattr(ts, "get_adapter", lambda proto: adapter)
    monkeypatch.setattr(ts.storage, "project_dir", lambda pid: tmp_path)
    monkeypatch.setattr(ts.storage, "publish_local", lambda p, sync=False: f"/static/{p.name}")
    monkeypatch.setattr(ts, "is_near_silent_audio", lambda p: False)
    return ts.TtsService(SimpleNamespace(ffmpeg_path="ffmpeg", volc_tts_speaker="zh_female_cancan_uranus_bigtts"), mock=False)


async def test_slot_adapter_ok_no_edge(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(return_value=MP3), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    edge = AsyncMock(); monkeypatch.setattr(svc, "_tts_edge", edge)
    url = await svc.synthesize("大家好", "narrator_calm", function_id="kepu.tts", project_id=1, shot_no=3)
    assert url == "/static/shot_003_tts.mp3" and edge.await_count == 0
    req = adapter.tts.await_args.args[1]
    # Alias giọng đọc được quy đổi trước khi dựng TtsRequest
    assert isinstance(req, base.TtsRequest) and req.voice == "zh_female_cancan_uranus_bigtts"


async def test_adapter_error_falls_back_to_edge(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(side_effect=RuntimeError("boom")), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    async def edge(text, dest: Path, voice_hint="", lang=None): dest.write_bytes(MP3)
    monkeypatch.setattr(svc, "_tts_edge", edge)
    assert (await svc.synthesize("a", "v", project_id=1, shot_no=1)).endswith("shot_001_tts.mp3")


async def test_no_audio_slot_goes_straight_to_edge(monkeypatch, tmp_path):
    prev = get_routing_snapshot(); _refresh_routing_snapshot([], FunctionBindings())
    try:
        svc = _svc(monkeypatch, tmp_path, SimpleNamespace(tts=AsyncMock()))
        async def edge(text, dest: Path, voice_hint="", lang=None): dest.write_bytes(MP3)
        monkeypatch.setattr(svc, "_tts_edge", edge)
        assert await svc.synthesize("a", "v", project_id=1, shot_no=1)
    finally:
        _refresh_routing_snapshot(prev.channels, prev.function_bindings)


async def test_all_fail_raises_and_no_file(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(side_effect=RuntimeError("x")), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    monkeypatch.setattr(svc, "_tts_edge", AsyncMock(side_effect=RuntimeError("edge down")))
    with pytest.raises(RuntimeError):
        await svc.synthesize("a", "v", project_id=1, shot_no=2)
    assert not (tmp_path / "shot_002_tts.mp3").exists()


async def test_near_silent_output_rejected(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(return_value=MP3), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    monkeypatch.setattr(ts, "is_near_silent_audio", lambda p: True)
    monkeypatch.setattr(svc, "_tts_edge", AsyncMock(side_effect=RuntimeError("edge down")))
    with pytest.raises(RuntimeError):
        await svc.synthesize("a", "v", project_id=1, shot_no=2)


# ---- I-8: giọng clone S_* / giọng Volc luôn ưu tiên provider volc_tts nếu slot có ----

@pytest.fixture
def mixed_audio_snapshot():
    """Slot audio có cả OpenAI (đứng đầu, weight cao) lẫn Volc TTS."""
    prev = get_routing_snapshot()
    chans = [
        SystemModelChannel(id="openai", name="OpenAI", base_url="https://api.openai.com/v1", api_key="k", has_api_key=True,
                           protocol="openai", models=["gpt-4o-mini-tts"], enabled=True),
        SystemModelChannel(id="volc_tts", name="Volc", base_url="https://voice.example/tts", api_key="v", has_api_key=True,
                           protocol="volc_tts", models=["seed-tts-2.0"], enabled=True),
    ]
    _refresh_routing_snapshot(chans, FunctionBindings(slots={"audio": [
        ModelBinding(channel_id="openai", model="gpt-4o-mini-tts", weight=100),
        ModelBinding(channel_id="volc_tts", model="seed-tts-2.0", weight=1),
    ]}))
    yield
    _refresh_routing_snapshot(prev.channels, prev.function_bindings)


def _recording_svc(monkeypatch, tmp_path, calls):
    """Adapter giả ghi lại protocol được gọi, luôn lỗi để thấy toàn bộ thứ tự thử."""
    async def _tts(route, req):
        calls.append(route.protocol)
        raise RuntimeError("down")

    svc = _svc(monkeypatch, tmp_path, SimpleNamespace(tts=_tts, is_transient_error=lambda e: False))
    monkeypatch.setattr(svc, "_tts_edge", AsyncMock(side_effect=RuntimeError("edge down")))
    return svc


@pytest.mark.parametrize("voice", ["S_abc123", "zh_male_shaonianzixin_uranus_bigtts", "narrator_calm", "en_female_x_bigtts"])
async def test_volc_speaker_prefers_volc_provider(monkeypatch, tmp_path, mixed_audio_snapshot, voice):
    for _ in range(10):
        calls: list[str] = []
        svc = _recording_svc(monkeypatch, tmp_path, calls)
        with pytest.raises(RuntimeError):
            await svc.synthesize("a", voice, function_id="drama.tts", project_id=1, shot_no=1)
        assert calls[0] == "volc_tts"


async def test_openai_voice_keeps_slot_order(monkeypatch, tmp_path, mixed_audio_snapshot):
    """Giọng không phải kiểu Volc (vd. alloy) không bị ép sang Volc."""
    seen: set[str] = set()
    for _ in range(30):
        calls: list[str] = []
        svc = _recording_svc(monkeypatch, tmp_path, calls)
        with pytest.raises(RuntimeError):
            await svc.synthesize("a", "alloy", function_id="drama.tts", project_id=1, shot_no=1)
        seen.add(calls[0])
    assert "openai" in seen
