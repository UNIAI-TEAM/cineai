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
    url = await svc.synthesize("xin chào", "narrator_calm", function_id="kepu.tts", project_id=1, shot_no=3)
    assert url == "/static/shot_003_tts.mp3" and edge.await_count == 0
    req = adapter.tts.await_args.args[1]
    assert isinstance(req, base.TtsRequest) and req.voice == "narrator_calm"


async def test_adapter_error_falls_back_to_edge(monkeypatch, tmp_path, audio_snapshot):
    adapter = SimpleNamespace(tts=AsyncMock(side_effect=RuntimeError("boom")), is_transient_error=lambda e: False)
    svc = _svc(monkeypatch, tmp_path, adapter)
    async def edge(text, dest: Path, voice_hint=""): dest.write_bytes(MP3)
    monkeypatch.setattr(svc, "_tts_edge", edge)
    assert (await svc.synthesize("a", "v", project_id=1, shot_no=1)).endswith("shot_001_tts.mp3")


async def test_no_audio_slot_goes_straight_to_edge(monkeypatch, tmp_path):
    prev = get_routing_snapshot(); _refresh_routing_snapshot([], FunctionBindings())
    try:
        svc = _svc(monkeypatch, tmp_path, SimpleNamespace(tts=AsyncMock()))
        async def edge(text, dest: Path, voice_hint=""): dest.write_bytes(MP3)
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
