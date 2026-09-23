# -*- coding: utf-8 -*-
"""项目内容语言：创建 / PATCH 时用户显式选择（科普 + 漫剧），非法值用 AppError 拒绝。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.errors import AppError
from app.services.content_lang import parse_content_lang, project_kepu_lang

from tests.conftest import make_user


def _request(ui_locale: str = "vi") -> Request:
    """带 X-UI-Locale 的最小请求对象（request_lang 只读 headers）。"""
    return Request({"type": "http", "headers": [(b"x-ui-locale", ui_locale.encode())]})


# ---------- 纯函数 ----------


def test_parse_content_lang_accepts_known_and_blank() -> None:
    assert parse_content_lang(None) is None
    assert parse_content_lang("") is None
    assert parse_content_lang("   ") is None
    assert parse_content_lang("vi") == "vi"
    assert parse_content_lang("en-US") == "en"
    assert parse_content_lang("zh_CN") == "zh"


@pytest.mark.parametrize("value", ["fr", "xx", "english", 123])
def test_parse_content_lang_rejects_unknown(value: object) -> None:
    with pytest.raises(AppError) as exc:
        parse_content_lang(value)
    assert exc.value.code == "common.invalid_content_lang"
    assert exc.value.status == 400


def test_project_kepu_lang_locked_beats_text_guess() -> None:
    """显式选择（locked）优先：越南语主题 + 选英文 → en。"""
    locked = SimpleNamespace(source_text="Quang hợp là gì", content_lang="en", content_lang_locked=True)
    assert project_kepu_lang(locked) == "en"


def test_project_kepu_lang_unlocked_keeps_old_rules() -> None:
    """未锁定：沿用 kepu_content_lang（文本含中文 / 越南语字母优先，否则跟随记录的界面语言）。"""
    assert project_kepu_lang(SimpleNamespace(source_text="光合作用", content_lang="vi")) == "zh"
    assert project_kepu_lang(
        SimpleNamespace(source_text="iPhone 15", content_lang="en", content_lang_locked=False)
    ) == "en"
    # 锁定但值损坏 → 回落推断
    assert project_kepu_lang(
        SimpleNamespace(source_text="Quang hợp", content_lang="", content_lang_locked=True)
    ) == "vi"


# ---------- 科普项目（需要 PostgreSQL） ----------


async def _make_template(db: AsyncSession, tid: str):
    from app.models import Template

    tpl = Template(id=tid, name="内容语言测试模板", style_prefix="x")
    db.add(tpl)
    await db.flush()
    return tpl


@pytest.mark.asyncio
async def test_kepu_create_with_explicit_content_lang(db_session: AsyncSession) -> None:
    from app.api.projects import create_project
    from app.schemas import ProjectCreate, ProjectOut

    user = await make_user(db_session)
    tpl = await _make_template(db_session, "tpl-lang-1")
    body = ProjectCreate(template_id=tpl.id, source_text="Quang hợp là gì", content_lang="en")
    project = await create_project(body, _request("vi"), db_session, user)
    assert project.content_lang == "en"
    assert project.content_lang_locked is True
    out = ProjectOut.model_validate(project)
    assert out.effective_content_lang == "en"
    assert out.content_lang_locked is True


@pytest.mark.asyncio
async def test_kepu_create_without_content_lang_uses_ui_locale(db_session: AsyncSession) -> None:
    from app.api.projects import create_project
    from app.schemas import ProjectCreate, ProjectOut

    user = await make_user(db_session)
    tpl = await _make_template(db_session, "tpl-lang-2")
    body = ProjectCreate(template_id=tpl.id, source_text="iPhone 15")
    project = await create_project(body, _request("en"), db_session, user)
    assert project.content_lang == "en"
    assert not project.content_lang_locked
    assert ProjectOut.model_validate(project).effective_content_lang == "en"


@pytest.mark.asyncio
async def test_kepu_create_rejects_invalid_content_lang(db_session: AsyncSession) -> None:
    from app.api.projects import create_project
    from app.schemas import ProjectCreate

    user = await make_user(db_session)
    tpl = await _make_template(db_session, "tpl-lang-3")
    body = ProjectCreate(template_id=tpl.id, source_text="Quang hợp", content_lang="fr")
    with pytest.raises(AppError) as exc:
        await create_project(body, _request("vi"), db_session, user)
    assert exc.value.code == "common.invalid_content_lang"


@pytest.mark.asyncio
async def test_kepu_patch_content_lang(db_session: AsyncSession) -> None:
    from app.api.projects import create_project, update_project
    from app.schemas import ProjectCreate, ProjectUpdate

    user = await make_user(db_session)
    tpl = await _make_template(db_session, "tpl-lang-4")
    project = await create_project(
        ProjectCreate(template_id=tpl.id, source_text="Quang hợp là gì"), _request("vi"), db_session, user
    )
    assert project.effective_content_lang == "vi"

    updated = await update_project(project.id, ProjectUpdate(content_lang="en"), db_session, user)
    assert updated.content_lang == "en"
    assert updated.content_lang_locked is True
    assert updated.effective_content_lang == "en"

    # null 视为不修改
    same = await update_project(project.id, ProjectUpdate(content_lang=None), db_session, user)
    assert same.content_lang == "en"

    with pytest.raises(AppError) as exc:
        await update_project(project.id, ProjectUpdate(content_lang="klingon"), db_session, user)
    assert exc.value.code == "common.invalid_content_lang"


# ---------- 漫剧项目（需要 PostgreSQL） ----------

_SOURCE = "Một cô gái nghèo tình cờ cứu một thiếu gia và cuộc đời cô thay đổi từ đó."


@pytest.mark.asyncio
async def test_drama_create_prefers_body_content_lang(db_session: AsyncSession) -> None:
    from app.api.drama.projects import create_project
    from app.schemas_drama import DramaProjectCreate

    user = await make_user(db_session)
    out = await create_project(
        DramaProjectCreate(source=_SOURCE, content_lang="en", params={"content_lang": "zh"}),
        _request("vi"),
        db_session,
        user,
    )
    assert out.content_lang == "en"
    assert out.params["content_lang"] == "en"


@pytest.mark.asyncio
async def test_drama_create_falls_back_to_params_then_ui_locale(db_session: AsyncSession) -> None:
    from app.api.drama.projects import create_project
    from app.schemas_drama import DramaProjectCreate

    user = await make_user(db_session)
    from_params = await create_project(
        DramaProjectCreate(source=_SOURCE, params={"content_lang": "zh"}), _request("vi"), db_session, user
    )
    assert from_params.content_lang == "zh"
    from_ui = await create_project(DramaProjectCreate(source=_SOURCE), _request("en"), db_session, user)
    assert from_ui.content_lang == "en"


@pytest.mark.asyncio
async def test_drama_create_rejects_invalid_content_lang(db_session: AsyncSession) -> None:
    from app.api.drama.projects import create_project
    from app.schemas_drama import DramaProjectCreate

    user = await make_user(db_session)
    with pytest.raises(AppError) as exc:
        await create_project(
            DramaProjectCreate(source=_SOURCE, content_lang="jp"), _request("vi"), db_session, user
        )
    assert exc.value.code == "common.invalid_content_lang"


@pytest.mark.asyncio
async def test_drama_patch_content_lang(db_session: AsyncSession) -> None:
    from app.api.drama.projects import create_project, update_project
    from app.schemas_drama import DramaProjectCreate, DramaProjectUpdate

    user = await make_user(db_session)
    created = await create_project(DramaProjectCreate(source=_SOURCE), _request("vi"), db_session, user)
    assert created.content_lang == "vi"

    updated = await update_project(created.id, DramaProjectUpdate(content_lang="en"), db_session, user)
    assert updated.content_lang == "en"

    # 整包回写 params（不带 content_lang）保留已选语言
    kept = await update_project(
        created.id, DramaProjectUpdate(params={"aspect_ratio": "9:16"}), db_session, user
    )
    assert kept.content_lang == "en"
    assert kept.params["aspect_ratio"] == "9:16"

    with pytest.raises(AppError) as exc:
        await update_project(created.id, DramaProjectUpdate(content_lang="xx"), db_session, user)
    assert exc.value.code == "common.invalid_content_lang"
    again = await update_project(created.id, DramaProjectUpdate(), db_session, user)
    assert again.content_lang == "en"


@pytest.mark.asyncio
async def test_drama_patch_stale_params_snapshot_cannot_revert_lang(db_session: AsyncSession) -> None:
    """整包回写的旧 params 快照带着旧 content_lang：更新时忽略，只有顶层 content_lang 能改语言。"""
    from app.api.drama.projects import create_project, update_project
    from app.schemas_drama import DramaProjectCreate, DramaProjectUpdate

    user = await make_user(db_session)
    created = await create_project(DramaProjectCreate(source=_SOURCE), _request("vi"), db_session, user)
    stale_params = dict(created.params)
    assert stale_params["content_lang"] == "vi"

    await update_project(created.id, DramaProjectUpdate(content_lang="en"), db_session, user)
    kept = await update_project(
        created.id, DramaProjectUpdate(params={**stale_params, "aspect_ratio": "16:9"}), db_session, user
    )
    assert kept.content_lang == "en"
    assert kept.params["content_lang"] == "en"
    assert kept.params["aspect_ratio"] == "16:9"

    # 同一请求同时带顶层 content_lang：以顶层为准
    both = await update_project(
        created.id, DramaProjectUpdate(params={**stale_params}, content_lang="vi"), db_session, user
    )
    assert both.content_lang == "vi"
