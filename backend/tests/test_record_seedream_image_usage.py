"""record_seedream_image_usage: giá/ảnh theo provider_rates, cost_fen sẵn có thắng."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.drama.billing_util import record_seedream_image_usage
from app.services.media_gateway import ImageResult
from tests.conftest import make_user


@pytest.fixture(autouse=True)
def _usd7(monkeypatch):
    """Tỉ giá 7 để so số fen tuyệt đối."""
    monkeypatch.setattr(get_settings(), "billing_usd_cny", 7.0)


async def test_record_seedream_with_upstream_usage(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    image = ImageResult(local_url="/static/x.png", total_tokens=120_000, completion_tokens=120_000,
                        raw_usage={"generated_images": 1, "total_tokens": 120_000})
    ev = await record_seedream_image_usage(db_session, user_id=user.id, model="seedream-5-0-260128",
                                           domain="api", image_result=image)
    await db_session.commit()
    assert ev.estimated is False and ev.total_tokens == 120_000
    assert ev.charge_fen == 25          # 0.035 USD/ảnh, không phải 120k token × giá/M


async def test_record_seedream_empty_usage_token_priced_model(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    image = ImageResult(local_url="/static/x.png", total_tokens=0,
                        raw_usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
    ev = await record_seedream_image_usage(db_session, user_id=user.id, model="gpt-image-2", domain="drama",
                                           image_result=image)
    await db_session.commit()
    assert ev.estimated is True
    assert ev.charge_fen == ev.cost_fen == 132      # trần 6 240 token đầu ra × 30 USD/M


async def test_record_seedream_with_upstream_cost_fen(db_session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "billing_markup", 2.0)
    user = await make_user(db_session)
    image = ImageResult(local_url="/static/x.png", upstream_cost_fen=500, raw_usage={"cost_fen": 500})
    ev = await record_seedream_image_usage(db_session, user_id=user.id, model="seedream-test", domain="studio",
                                           image_result=image)
    await db_session.commit()
    assert ev.estimated is False and ev.cost_fen == 500 and ev.charge_fen == 500


async def test_record_seedream_zero_images_upstream_cost_zero(db_session: AsyncSession) -> None:
    """Adapter trả cost_fen 0 (upstream báo 0 ảnh) → dòng 0 fen, không rơi về ước tính."""
    user = await make_user(db_session)
    image = ImageResult(local_url="/static/x.png", upstream_cost_fen=0, raw_usage={"generated_images": 0},
                        model="dola-seedream-5-0-pro-260628")
    ev = await record_seedream_image_usage(db_session, user_id=user.id, model="nhan-cu", domain="drama",
                                           image_result=image)
    await db_session.commit()
    assert ev.estimated is False and ev.cost_fen == 0 and ev.charge_fen == 0
