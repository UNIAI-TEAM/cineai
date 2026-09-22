"""TaskRun.provider_channel_id: submit ghi kênh, poll drama/ephemeral truyền đúng kênh đó vào fetch_task_once."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UsageEvent
from app.services import ark as ark_module
from app.services.providers.base import TaskResult

from tests.conftest import make_task, make_user


@pytest.mark.asyncio
async def test_column_exists(db_session: AsyncSession) -> None:
    """Cột provider_channel_id phải tồn tại trên task_runs (schema patch additive)."""
    cols = (
        await db_session.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name='task_runs'")
        )
    ).scalars().all()
    assert "provider_channel_id" in cols


@pytest.mark.asyncio
async def test_ephemeral_deferred_stores_channel(db_session: AsyncSession) -> None:
    """run_billed_ephemeral_deferred phải ghi provider_channel_id từ channel_for_task sau khi có provider_task_id."""
    from app.services.billing.ephemeral import run_billed_ephemeral_deferred

    user = await make_user(db_session)
    gw = ark_module.get_ark()
    gw._task_channels["cgt-77"] = "byteplus"

    async def exec_() -> dict:
        return {"task_id": "cgt-77"}

    task, _ = await run_billed_ephemeral_deferred(
        db_session,
        user,
        domain="studio",
        task_type="tool_video",
        executor=exec_,
        payload={"duration": 5},
        commit=False,
    )
    assert task.provider_task_id == "cgt-77"
    assert task.provider_channel_id == "byteplus"


@pytest.mark.asyncio
async def test_ephemeral_poll_passes_channel(db_session: AsyncSession, monkeypatch) -> None:
    """_poll_ephemeral_with_session phải truyền task.provider_channel_id vào poll_video_task."""
    from app.services.tasks import poller

    user = await make_user(db_session)
    task = await make_task(
        db_session,
        user,
        domain="studio",
        task_type="tool_video",
        status="awaiting_poll",
        provider_task_id="cgt-1",
        billing_status="frozen",
    )
    task.provider_channel_id = "byteplus"
    await db_session.flush()

    seen: dict = {}

    async def fake_poll(u, tid, *, channel_id=None):
        seen["channel"] = channel_id
        return {"status": "running", "kind": "video", "urls": [], "usage": {}}

    monkeypatch.setattr("app.services.studio_tools.poll_video_task", fake_poll)

    await poller._poll_ephemeral_with_session(
        db_session, task, now=datetime.now(UTC), timeout_sec=900
    )
    assert seen["channel"] == "byteplus"


@pytest.mark.asyncio
async def test_fetch_task_once_receives_channel(monkeypatch) -> None:
    """studio_tools.poll_video_task phải chuyển tiếp channel_id sang MediaGateway.fetch_task_once."""
    gw = ark_module.get_ark()
    spy = AsyncMock(return_value=TaskResult(status="running"))
    monkeypatch.setattr(gw, "fetch_task_once", spy)
    from app.services.studio_tools import poll_video_task
    from types import SimpleNamespace

    await poll_video_task(SimpleNamespace(id=1), "cgt-5", channel_id="byteplus")
    assert spy.await_args.kwargs["channel_id"] == "byteplus"


@pytest.mark.asyncio
async def test_record_seedream_image_usage_provider_from_channel(db_session: AsyncSession) -> None:
    """record_seedream_image_usage phải ghi provider = image_result.channel_id khi có."""
    from app.services.drama.billing_util import record_seedream_image_usage
    from app.services.media_gateway import ImageResult

    user = await make_user(db_session)
    image = ImageResult(local_url="/static/x.png", channel_id="byteplus", model="m")
    ev = await record_seedream_image_usage(
        db_session,
        user_id=user.id,
        model="m",
        domain="studio",
        image_result=image,
    )
    await db_session.commit()
    assert ev.provider == "byteplus"


@pytest.mark.asyncio
async def test_settle_deferred_video_poll_usage_row_provider_matches_task_channel(
    db_session: AsyncSession,
) -> None:
    """settle_deferred_video_poll phải ghi usage.provider = task.provider_channel_id (nhánh usage_tokens > 0,
    TaskResult được construct tay không tự set channel_id)."""
    from app.services.billing.ephemeral import settle_deferred_video_poll
    from app.services.billing.settlement import freeze_for_task

    user = await make_user(db_session, balance_fen=50_000)
    task = await make_task(
        db_session,
        user,
        domain="api",
        task_type="v1_video",
        status="awaiting_poll",
        billing_status="none",
        provider_task_id="upstream-chan-1",
    )
    task.provider_channel_id = "byteplus"
    await freeze_for_task(db_session, task)
    task.status = "awaiting_poll"
    await db_session.commit()

    await settle_deferred_video_poll(
        db_session,
        user,
        provider_task_id="upstream-chan-1",
        poll_status="succeeded",
        billing_task_id=task.id,
        usage_tokens=120_000,
        completion_tokens=120_000,
    )
    await db_session.commit()

    ev = (
        await db_session.execute(select(UsageEvent).where(UsageEvent.task_run_id == task.id))
    ).scalar_one()
    assert ev.provider == "byteplus"


@pytest.mark.asyncio
async def test_settle_deferred_video_poll_refetch_passes_task_channel(
    db_session: AsyncSession, monkeypatch
) -> None:
    """Nhánh usage_tokens == 0: settle_deferred_video_poll phải truyền task.provider_channel_id
    vào fetch_task_once re-fetch (không rơi về None/_task_channels/"ark")."""
    from app.services.billing.ephemeral import settle_deferred_video_poll
    from app.services.billing.settlement import freeze_for_task

    user = await make_user(db_session, balance_fen=50_000)
    task = await make_task(
        db_session,
        user,
        domain="api",
        task_type="v1_video",
        status="awaiting_poll",
        billing_status="none",
        provider_task_id="upstream-chan-2",
    )
    task.provider_channel_id = "byteplus"
    await freeze_for_task(db_session, task)
    task.status = "awaiting_poll"
    await db_session.commit()

    gw = ark_module.get_ark()
    spy = AsyncMock(
        return_value=TaskResult(status="succeeded", total_tokens=90_000, completion_tokens=90_000)
    )
    monkeypatch.setattr(gw, "fetch_task_once", spy)

    await settle_deferred_video_poll(
        db_session,
        user,
        provider_task_id="upstream-chan-2",
        poll_status="succeeded",
        billing_task_id=task.id,
        usage_tokens=0,
    )
    await db_session.commit()

    assert spy.await_args.kwargs["channel_id"] == "byteplus"
    ev = (
        await db_session.execute(select(UsageEvent).where(UsageEvent.task_run_id == task.id))
    ).scalar_one()
    assert ev.provider == "byteplus"
