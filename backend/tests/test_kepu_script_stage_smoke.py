# -*- coding: utf-8 -*-
"""科普 SCRIPTING 阶段冒烟：_script_stage 必须跑完并落库分镜。

回归点：facade 换成 MediaGateway 后 `ark._sanitize_seedream_prompt` 曾不存在，
整个 SCRIPTING 阶段会 AttributeError 而单测覆盖不到。
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, ProjectStatus, Shot, Template
from app.services import pipeline
from app.services.kepu_text import ShotPlan, StoryboardResult

from tests.conftest import make_user


@asynccontextmanager
async def _same_session(db: AsyncSession):
    """把 pipeline 内自开 session 钉到用例事务。"""
    yield db


def _plan(no: int) -> ShotPlan:
    """一个最简分镜计划（img_prompt 含需要 sanitize 的品牌词）。"""
    return ShotPlan(
        shot=no,
        duration=5.0,
        text=f"第 {no} 段口播",
        img_prompt=f"SpaceX 的猎鹰9 在发射台，镜头 {no}",
        video_prompt=f"轻微推镜 {no}",
        camera="push",
        bgm="轻快专业",
    )


async def test_script_stage_persists_shots(db_session: AsyncSession) -> None:
    """chat_storyboard 返回 2 镜时：阶段跑完、状态 SCRIPT_READY、分镜落库且提示词已净化。"""
    user = await make_user(db_session)
    tpl = Template(
        id="tpl-script-smoke",
        name="冒烟模板",
        style_prefix="写实纪录片风格",
        shot_duration_min=3,
        shot_duration_max=8,
    )
    db_session.add(tpl)
    await db_session.flush()
    project = Project(
        user_id=user.id,
        template_id=tpl.id,
        source_text="讲讲可回收火箭",
        status=ProjectStatus.DRAFT,
    )
    db_session.add(project)
    await db_session.flush()

    fake_ark = SimpleNamespace(
        chat_storyboard=AsyncMock(
            return_value=StoryboardResult(
                shots=[_plan(1), _plan(2)],
                character_bible="解说员：中性声线",
                bgm_lock="轻快专业",
            )
        )
    )
    with (
        patch.object(pipeline, "AsyncSessionLocal", lambda: _same_session(db_session)),
        patch.object(pipeline, "get_ark", return_value=fake_ark),
        patch.object(pipeline, "publish_progress", AsyncMock()),
        patch.object(pipeline, "_record_usage_est", AsyncMock()),
    ):
        # Không được ném AttributeError vì facade thiếu helper
        await pipeline._script_stage(project.id)

    await db_session.refresh(project)
    assert project.status == ProjectStatus.SCRIPT_READY
    assert project.progress == 15
    shots = (
        (await db_session.execute(select(Shot).where(Shot.project_id == project.id).order_by(Shot.shot_no)))
        .scalars()
        .all()
    )
    assert [s.shot_no for s in shots] == [1, 2]
    # sanitize_seedream_prompt đã thay tên thương hiệu bị Seedream chặn
    assert all("SpaceX" not in (s.img_prompt or "") for s in shots)
    assert all("猎鹰9" not in (s.img_prompt or "") for s in shots)
