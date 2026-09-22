"""Tab tính phí của chi tiết task hiện provider (channel id) của từng dòng usage."""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.tasks import _load_usage_lines
from app.models import UsageEvent
from app.schemas import AdminTaskBriefOut
from app.schemas_tasks import TaskRunBriefOut
from tests.conftest import make_user


def test_task_brief_exposes_provider_channel_id() -> None:
    task = SimpleNamespace(
        id=1, domain="drama", task_type="fragment_video", status="awaiting_poll",
        provider_task_id="cgt-1", provider_channel_id="byteplus",
    )
    assert TaskRunBriefOut.model_validate(task).provider_channel_id == "byteplus"


def test_admin_task_brief_out_exposes_provider_channel_id() -> None:
    brief = AdminTaskBriefOut(
        id=1,
        domain="drama",
        task_type="fragment_video",
        status="awaiting_poll",
        provider_channel_id="byteplus",
    )
    assert brief.provider_channel_id == "byteplus"


async def test_usage_lines_include_provider(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    task_run_id = 987_654_321
    db_session.add(
        UsageEvent(
            user_id=user.id,
            task_run_id=task_run_id,
            domain="tools",
            capability="image",
            billing_key="seedream",
            model="dola-seedream-5-0-pro-260628",
            provider="byteplus",
            charge_fen=32,
        )
    )
    await db_session.flush()

    lines = await _load_usage_lines(db_session, task_run_id)

    assert [line.provider for line in lines] == ["byteplus"]
