"""M-7: map task→kênh có giới hạn LRU; M-9: id provider dài quá 64 ký tự bị từ chối ở schema."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas_routing import SystemModelChannelIn
from app.services import media_gateway


def test_task_channel_map_is_lru_capped(monkeypatch):
    monkeypatch.setattr(media_gateway, "TASK_CHANNELS_MAX", 3)
    gw = media_gateway.MediaGateway()
    for i in range(3):
        gw._remember_task_channel(f"t{i}", "byteplus")
    assert gw.channel_for_task("t0") == "byteplus"          # t0 vừa dùng → thành mới nhất
    gw._remember_task_channel("t3", "byteplus")
    assert gw.channel_for_task("t1") is None                 # cũ nhất bị loại
    assert {gw.channel_for_task(t) for t in ("t0", "t2", "t3")} == {"byteplus"}
    assert len(gw._task_channels) == 3


def test_default_task_channel_cap_is_10000():
    assert media_gateway.TASK_CHANNELS_MAX == 10000


def test_provider_id_max_length_64():
    SystemModelChannelIn(id="a" * 64, name="ok")
    with pytest.raises(ValidationError):
        SystemModelChannelIn(id="a" * 65, name="too long")
