# -*- coding: utf-8 -*-
"""整片连贯配音新合成后必须复查近静音，拒绝产出无声成片。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.errors import AppRuntimeError
from app.services import pipeline


async def test_synthesize_rejects_near_silent_tts(tmp_path, monkeypatch) -> None:
    """TTS 返回近静音音频时抛错收敛，不继续按时长分配与合成。"""
    src = tmp_path / "tts_raw.mp3"
    src.write_bytes(b"x" * 4000)
    monkeypatch.setattr(
        "app.services.storage.local_path_from_url", lambda url: src
    )
    monkeypatch.setattr("app.services.storage.project_dir", lambda _pid: tmp_path)
    ark = SimpleNamespace(tts=AsyncMock(return_value="/static/p1/tts_raw.mp3"))
    with (
        patch.object(pipeline, "get_ark", return_value=ark),
        patch.object(pipeline, "_record_usage_est", AsyncMock()),
        patch.object(pipeline, "is_near_silent_audio", return_value=True),
        patch.object(pipeline, "probe_duration", AsyncMock(side_effect=AssertionError("不应继续探测时长"))),
    ):
        with pytest.raises(AppRuntimeError, match="近静音") as exc_info:
            await pipeline._synthesize_continuous_audio(
                1,
                voice="zh-F1",
                shot_rows=[SimpleNamespace(id=1, duration=4.0, narration="你好")],
                force=True,
            )
    assert exc_info.value.code == "project.narration_audio_silent"
    ark.tts.assert_awaited_once()


async def test_synthesize_passes_project_lang_to_tts(tmp_path, monkeypatch) -> None:
    """整片配音必须把项目内容语言传给 TTS：越南语旁白里夹一个汉字也不能被猜成中文音色。"""
    src = tmp_path / "tts_raw.mp3"
    src.write_bytes(b"x" * 4000)
    monkeypatch.setattr("app.services.storage.local_path_from_url", lambda url: src)
    monkeypatch.setattr("app.services.storage.project_dir", lambda _pid: tmp_path)
    ark = SimpleNamespace(tts=AsyncMock(return_value="/static/p1/tts_raw.mp3"))
    with (
        patch.object(pipeline, "get_ark", return_value=ark),
        patch.object(pipeline, "_record_usage_est", AsyncMock()),
        patch.object(pipeline, "is_near_silent_audio", return_value=True),
    ):
        with pytest.raises(AppRuntimeError):
            await pipeline._synthesize_continuous_audio(
                1,
                voice="vi-F1",
                shot_rows=[SimpleNamespace(id=1, duration=4.0, narration="Chữ 水 nghĩa là nước")],
                force=True,
                lang="vi",
            )
    assert ark.tts.await_args.kwargs.get("lang") == "vi"
