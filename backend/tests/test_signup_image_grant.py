"""Đóng băng ảnh phải vừa tiền tặng đăng ký; giá/ảnh theo provider_rates, không nhân buffer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.models_tasks import TaskRun
from app.services.billing.estimates import estimate_task_fen


@pytest.fixture
def _billing_settings(monkeypatch):
    """Tỉ giá 7, buffer 1.2 (để chứng minh ảnh không nhân buffer), tặng 500 fen."""
    settings = get_settings()
    monkeypatch.setattr(settings, "billing_usd_cny", 7.0)
    monkeypatch.setattr(settings, "billing_estimate_buffer", 1.2)
    monkeypatch.setattr(settings, "billing_signup_grant_fen", 500)
    return settings


async def test_asset_image_freeze_fits_signup_grant(_billing_settings, priced_routing):
    """Seedream 5.0 Pro 0.045 USD → 32 fen ≤ 500 fen tặng."""
    task = TaskRun(id=1, domain="drama", task_type="asset_image", requested_by=1, payload={})
    fen = await estimate_task_fen(MagicMock(), task, settings=_billing_settings)
    assert fen == 32
    assert fen <= int(_billing_settings.billing_signup_grant_fen)


async def test_tool_image_freeze_skips_estimate_buffer(_billing_settings, priced_routing):
    task = TaskRun(id=2, domain="studio", task_type="tool_image", requested_by=1, payload={})
    assert await estimate_task_fen(MagicMock(), task, settings=_billing_settings) == 32


@pytest.mark.parametrize("payload", [{"resolution": "3K"}, {"size": "1K"}, {"size": "4K"}])
async def test_image_size_does_not_change_per_image_price(_billing_settings, priced_routing, payload):
    """Seedream tính giá theo ảnh, không theo độ phân giải (bỏ bậc 1K/2K/4K kiểu Kie)."""
    task = TaskRun(id=3, domain="studio", task_type="tool_image", requested_by=1, payload=payload)
    assert await estimate_task_fen(MagicMock(), task, settings=_billing_settings) == 32
