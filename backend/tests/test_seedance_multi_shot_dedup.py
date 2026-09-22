"""Seedance 视频用量去重：一个 TaskRun 内多镜各记一行，同一上游任务重复收尾只记一行。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Shot, Template, UsageEvent
from app.services.billing.context import billing_scope
from app.services.drama.billing_util import record_seedance_video_usage
from app.services.providers.base import TaskResult
from tests.conftest import make_task, make_user

SEEDANCE_20 = "dreamina-seedance-2-0-260128"


def _result(pid: str | None) -> TaskResult:
    """构造一条 108 000 token 的成功视频任务结果。"""
    return TaskResult(status="succeeded", total_tokens=108_000, completion_tokens=108_000,
                      raw_usage={"total_tokens": 108_000}, model=SEEDANCE_20, provider_task_id=pid)


async def _record(db: AsyncSession, user_id: int, pid: str | None, **kw) -> UsageEvent:
    """以 kepu 视频参数写一次 Seedance 用量。"""
    return await record_seedance_video_usage(
        db, user_id=user_id, billing_key="seedance2:video0", model=SEEDANCE_20, domain="kepu",
        task_result=_result(pid), provider_task_id=pid, **kw,
    )


async def _rows(db: AsyncSession, **where) -> list[UsageEvent]:
    """按条件列出用量行（id 升序）。"""
    stmt = select(UsageEvent).order_by(UsageEvent.id.asc())
    for key, value in where.items():
        stmt = stmt.where(getattr(UsageEvent, key) == value)
    return list((await db.execute(stmt)).scalars().all())


async def _two_shots(db: AsyncSession, user_id: int) -> tuple[int, int, int]:
    """建项目与两个分镜，返回 (project_id, shot1_id, shot2_id)。"""
    tpl = Template(id=f"tpl-ms-{uuid.uuid4().hex[:8]}", name="多镜模板", style_prefix="x")
    db.add(tpl)
    project = Project(user_id=user_id, template_id=tpl.id, source_text="x", title="多镜项目")
    db.add(project)
    await db.flush()
    s1 = Shot(project_id=project.id, shot_no=1)
    s2 = Shot(project_id=project.id, shot_no=2)
    db.add_all([s1, s2])
    await db.flush()
    return int(project.id), int(s1.id), int(s2.id)


async def test_two_kepu_shots_in_one_task_both_billed(db_session: AsyncSession) -> None:
    """同一 TaskRun 内两个镜头（不同上游任务）各记一行，都按 530 分计费。"""
    user = await make_user(db_session, balance_fen=10_000)
    task = await make_task(db_session, user, domain="kepu", task_type="project_pipeline")
    await db_session.commit()
    async with billing_scope(task.id):
        await _record(db_session, user.id, f"cgt-a-{task.id}")
        await _record(db_session, user.id, f"cgt-b-{task.id}")
    rows = await _rows(db_session, task_run_id=task.id)
    assert [r.charge_fen for r in rows] == [530, 530]


async def test_same_provider_task_recorded_once_in_scope(db_session: AsyncSession) -> None:
    """同一上游任务在同一 TaskRun 内重复收尾（重试/重复轮询）只记一行。"""
    user = await make_user(db_session)
    task = await make_task(db_session, user, domain="drama", task_type="fragment_video")
    await db_session.commit()
    pid = f"cgt-same-{task.id}"
    async with billing_scope(task.id):
        first = await _record(db_session, user.id, pid)
        second = await _record(db_session, user.id, pid)
    assert second.id == first.id
    assert len(await _rows(db_session, task_run_id=task.id)) == 1


async def test_same_provider_task_recorded_once_across_task_runs(db_session: AsyncSession) -> None:
    """同一上游任务被另一个 TaskRun（恢复/重派）再次收尾，仍只记一行。"""
    user = await make_user(db_session)
    t1 = await make_task(db_session, user, domain="drama", task_type="fragment_video")
    t2 = await make_task(db_session, user, domain="drama", task_type="fragment_video")
    await db_session.commit()
    pid = f"cgt-cross-{t1.id}"
    async with billing_scope(t1.id):
        await _record(db_session, user.id, pid)
    async with billing_scope(t2.id):
        await _record(db_session, user.id, pid)
    assert len(await _rows(db_session, user_id=user.id)) == 1


async def test_without_provider_id_each_shot_billed_once(db_session: AsyncSession) -> None:
    """无上游任务 ID（如 mock）时按 TaskRun+计费键+分镜去重：两镜两行，同镜重复一行。"""
    user = await make_user(db_session)
    project_id, s1, s2 = await _two_shots(db_session, user.id)
    task = await make_task(db_session, user, domain="kepu", task_type="project_pipeline")
    await db_session.commit()
    async with billing_scope(task.id):
        await _record(db_session, user.id, None, project_id=project_id, shot_id=s1)
        await _record(db_session, user.id, None, project_id=project_id, shot_id=s2)
        await _record(db_session, user.id, None, project_id=project_id, shot_id=s1)
    rows = await _rows(db_session, task_run_id=task.id)
    assert sorted(r.shot_id for r in rows) == sorted([s1, s2])


async def test_without_provider_id_or_shot_dedupes_by_task(db_session: AsyncSession) -> None:
    """无上游任务 ID 且无分镜时保持 TaskRun+计费键 幂等。"""
    user = await make_user(db_session)
    task = await make_task(db_session, user, domain="drama", task_type="asset_video")
    await db_session.commit()
    async with billing_scope(task.id):
        await _record(db_session, user.id, None)
        await _record(db_session, user.id, None)
    assert len(await _rows(db_session, task_run_id=task.id)) == 1


async def test_deferred_video_poll_settles_once(db_session: AsyncSession) -> None:
    """开放 API 延迟轮询重复收尾同一上游任务只记一行。"""
    from app.services.billing.ephemeral import settle_deferred_video_poll
    from app.services.billing.settlement import freeze_for_task

    user = await make_user(db_session, balance_fen=50_000)
    pid = f"cgt-poll-{uuid.uuid4().hex[:8]}"
    task = await make_task(db_session, user, domain="api", task_type="v1_video", status="awaiting_poll",
                           billing_status="none", provider_task_id=pid)
    await freeze_for_task(db_session, task)
    task.status = "awaiting_poll"
    await db_session.commit()
    for _ in range(2):
        await settle_deferred_video_poll(
            db_session, user, provider_task_id=pid, poll_status="succeeded", billing_task_id=task.id,
            usage_tokens=108_000, completion_tokens=108_000, raw_usage={"total_tokens": 108_000},
            model=SEEDANCE_20,
        )
        await db_session.commit()
    assert len(await _rows(db_session, task_run_id=task.id)) == 1
