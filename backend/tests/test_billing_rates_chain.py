# backend/tests/test_billing_rates_chain.py
"""Chuỗi freeze → usage → settle dùng provider_rates; dòng LLM ước tính gắn model của slot."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import UsageEvent
from app.services.billing.context import billing_scope
from app.services.billing.settlement import freeze_for_task, settle_task
from app.services.billing.usage import record_line
from app.services.drama.billing_util import record_seedream_image_usage
from app.services.media_gateway import ImageResult
from tests.conftest import make_task, make_user


@pytest.fixture
def _usd7(monkeypatch):
    """Tỉ giá 7, token LLM ước tính 80 000."""
    s = get_settings()
    monkeypatch.setattr(s, "billing_usd_cny", 7.0)
    monkeypatch.setattr(s, "billing_est_llm_tokens", 80_000)


async def _asset_image_chain(db: AsyncSession, image: ImageResult) -> tuple[int, dict, object]:
    """Đóng băng một tác vụ asset_image, ghi dòng ảnh trong scope rồi quyết toán; trả (need, kết quả, user)."""
    user = await make_user(db, balance_fen=1_000)
    task = await make_task(db, user, domain="drama", task_type="asset_image")
    await db.commit()
    need = await freeze_for_task(db, task)
    async with billing_scope(task.id):
        await record_seedream_image_usage(db, user_id=user.id, model="nhan-cu", domain="drama", image_result=image)
    await db.commit()
    result = await settle_task(db, task.id)
    await db.commit()
    return need, result, user


async def test_asset_image_freeze_equals_settle(db_session: AsyncSession, priced_routing, _usd7) -> None:
    need, result, user = await _asset_image_chain(db_session, ImageResult(
        local_url="/static/a.png", raw_usage={"generated_images": 1},
        channel_id="byteplus", model="dola-seedream-5-0-pro-260628"))
    assert need == 32
    assert result == {"charged": 32, "refunded": 0}
    assert user.balance_fen == 1_000 - 32 and user.frozen_fen == 0


async def test_asset_image_zero_images_refunds_everything(db_session: AsyncSession, priced_routing, _usd7) -> None:
    need, result, user = await _asset_image_chain(db_session, ImageResult(
        local_url="/static/a.png", raw_usage={"generated_images": 0}, upstream_cost_fen=0,
        channel_id="byteplus", model="dola-seedream-5-0-pro-260628"))
    assert need == 32
    assert result == {"charged": 0, "refunded": 32}
    assert user.balance_fen == 1_000 and user.frozen_fen == 0


async def test_asset_image_unpriced_model_charges_fallback(db_session: AsyncSession, priced_routing, _usd7) -> None:
    need, result, user = await _asset_image_chain(db_session, ImageResult(
        local_url="/static/a.png", raw_usage={"generated_images": 1}, channel_id="byteplus", model="ep-2026-img"))
    # 45 000 token × 8 元/M = 36 fen > 32 đã đóng băng: quyết toán vẫn tính đủ, không bao giờ 0
    assert result == {"charged": 36, "refunded": 0}
    assert user.balance_fen == 1_000 - 36 and user.frozen_fen == 0


async def test_estimated_llm_line_uses_slot_model(db_session: AsyncSession, priced_routing, _usd7) -> None:
    user = await make_user(db_session)
    ev = await record_line(db_session, user_id=user.id, billing_key="llm_chat",
                           model=get_settings().model_llm, estimated=True, domain="drama")
    assert ev.model == "gpt-5.6-sol" and ev.charge_fen == 493 and ev.estimated is True
    kept = await record_line(db_session, user_id=user.id, billing_key="llm_chat", model="test-llm",
                             tokens=1000, estimated=True, domain="drama")
    assert kept.model == "test-llm"   # model caller đặt rõ ràng thì giữ nguyên


async def test_video_line_priced_by_task_model(db_session: AsyncSession, priced_routing, _usd7) -> None:
    from app.services.drama.billing_util import record_seedance_video_usage
    from app.services.providers.base import TaskResult

    user = await make_user(db_session)
    await record_seedance_video_usage(
        db_session, user_id=user.id, billing_key="seedance2:video0", model="nhan-cu", domain="drama",
        task_result=TaskResult(status="succeeded", total_tokens=108_000, completion_tokens=108_000,
                               raw_usage={"total_tokens": 108_000}, model="dreamina-seedance-2-5-260628"),
        drama_project_id=1,
    )
    await db_session.commit()
    ev = (await db_session.execute(select(UsageEvent).where(UsageEvent.user_id == user.id))).scalar_one()
    assert ev.cost_fen == 809 and ev.model == "dreamina-seedance-2-5-260628"
