"""fragment_video: đóng băng theo thời lượng (payload / nội dung phân cảnh) × độ phân giải × giá Seedance."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import get_settings
from app.models_tasks import TaskRun
from app.services.billing.estimates import estimate_task_fen


@pytest.fixture
def _settings(monkeypatch):
    """Tỉ giá 7, buffer 1.0 để so số tuyệt đối."""
    settings = get_settings()
    monkeypatch.setattr(settings, "billing_usd_cny", 7.0)
    monkeypatch.setattr(settings, "billing_estimate_buffer", 1.0)
    return settings


def _task(payload: dict, fragment_id: int = 9, task_id: int = 4) -> TaskRun:
    return TaskRun(id=task_id, domain="drama", task_type="fragment_video", requested_by=1,
                   payload=payload, fragment_id=fragment_id)


async def test_fragment_video_estimate_uses_payload_duration_sec(_settings, priced_routing):
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    fen8 = await estimate_task_fen(db, _task({"duration_sec": 8, "resolution": "720p"}), settings=_settings)
    fen16 = await estimate_task_fen(db, _task({"duration_sec": 16, "resolution": "720p"}), settings=_settings)
    assert fen16 > fen8


async def test_fragment_video_estimate_by_resolution(_settings, priced_routing):
    """Seedance 2.5 5 giây: 480p 365 fen, 720p 809 fen; cộng nửa giá ảnh (32 // 2 = 16); mặc định 720p."""
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    fen_480 = await estimate_task_fen(db, _task({"duration_sec": 5, "resolution": "480p"}), settings=_settings)
    fen_720 = await estimate_task_fen(db, _task({"duration_sec": 5, "resolution": "720p"}), settings=_settings)
    fen_default = await estimate_task_fen(db, _task({"duration_sec": 5}), settings=_settings)
    assert fen_480 == 365 + 16
    assert fen_720 == 809 + 16
    assert fen_default == fen_720


async def test_fragment_video_estimate_reads_fragment_content(_settings, priced_routing):
    """Không có thời lượng trong payload → đọc @duration trong nội dung phân cảnh.

    Seedance 2.5 720p 12 giây: 259 200 token → 1942 fen; cộng nửa giá ảnh (32 // 2 = 16) → 1958 fen.
    """
    frag = SimpleNamespace(content="@duration:12 thoại", duration_sec=8)
    db = MagicMock()
    db.get = AsyncMock(return_value=frag)
    fen = await estimate_task_fen(db, _task({"fragment_ids": [11]}, fragment_id=11), settings=_settings)
    assert fen == 1958
    db.get.assert_awaited()
