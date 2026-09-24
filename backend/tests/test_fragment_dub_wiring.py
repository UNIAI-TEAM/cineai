"""Nối lồng tiếng: handler đăng ký, ước tính phí có TTS khi dub, mã lỗi có trong danh mục."""
from __future__ import annotations

from types import SimpleNamespace

from app.errors import ERRORS
from app.services.billing import estimates
from app.services.tasks.handlers import get_task_handler


def test_fragment_dub_handler_registered():
    assert get_task_handler("drama", "fragment_dub") is not None


def test_dub_error_codes_registered():
    for code in ("drama.dub_no_video", "drama.dub_not_enabled", "drama.dub_failed", "drama.dub_fragment_generating"):
        assert code in ERRORS


async def test_fragment_video_estimate_adds_tts_when_dub(monkeypatch, priced_routing):
    async def fake_dur(db, task, payload):
        return 8.0

    monkeypatch.setattr(estimates, "_drama_video_duration", fake_dur)
    base_task = dict(domain="drama", task_type="fragment_video", fragment_id=None, project_id=None)
    native = SimpleNamespace(**base_task, payload={"voice_mode": "native"})
    dub = SimpleNamespace(**base_task, payload={"voice_mode": "dub"})
    fen_native = await estimates.estimate_task_fen(None, native)
    fen_dub = await estimates.estimate_task_fen(None, dub)
    assert fen_dub > fen_native


async def test_fragment_dub_estimate_is_tts(priced_routing):
    task = SimpleNamespace(domain="drama", task_type="fragment_dub", payload={}, fragment_id=None, project_id=None)
    assert await estimates.estimate_task_fen(None, task) > 0
