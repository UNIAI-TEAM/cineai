# -*- coding: utf-8 -*-
"""落库错误码（Đợt 2A）：项目 / 工具记录 / 任务存 error_code + params；401 与开放 API 返回错误码、不回传上游原文。"""
from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.errors import AppError, AppRuntimeError, register_app_error_handler
from app.services.exc_format import stored_error_fields
from app.services.project_errors import project_error_fields
from app.services.providers.base import TransientUpstreamError, UpstreamError, reraise_upstream_timeout


# ---- 异常 → 错误码 ----


def test_stored_error_fields_classifies_upstream() -> None:
    """AppError 原样；上游超时 / 连不上 / 审核拦截 / 其他失败分别归类；普通异常用默认码。"""
    assert stored_error_fields(AppError("project.narration_empty")) == ("project.narration_empty", None)
    assert stored_error_fields(AppRuntimeError("project.storyboard_not_ready", phase="assets")) == (
        "project.storyboard_not_ready",
        {"phase": "assets"},
    )
    assert stored_error_fields(RuntimeError("boom")) == ("task.execution_failed", None)
    assert stored_error_fields(RuntimeError("boom"), "tool.run_failed") == ("tool.run_failed", None)

    for raw, expected in (
        (httpx.ReadTimeout("slow"), "provider.timeout"),
        (httpx.ConnectError("down"), "provider.network_error"),
    ):
        try:
            reraise_upstream_timeout(raw, kind="生图", read_sec=30)
        except Exception as exc:  # noqa: BLE001
            assert stored_error_fields(exc)[0] == expected

    assert stored_error_fields(httpx.ConnectError("x"))[0] == "provider.network_error"
    assert stored_error_fields(UpstreamError("Seedream error 400: bad"))[0] == "provider.failed"
    assert stored_error_fields(TransientUpstreamError("HTTP 503"))[0] == "provider.failed"
    assert stored_error_fields(UpstreamError("InputTextSensitiveContentDetected"))[0] == "provider.content_rejected"
    # params 不含上游原文
    assert stored_error_fields(UpstreamError("secret upstream text"))[1] is None


def test_wrapped_upstream_error_keeps_category() -> None:
    """gateway 用 `raise UpstreamError(str(last)) from last` 包装后仍能按原异常归类。"""
    try:
        try:
            raise httpx.ReadTimeout("slow")
        except httpx.ReadTimeout as inner:
            raise UpstreamError(str(inner)) from inner
    except UpstreamError as exc:
        assert stored_error_fields(exc)[0] == "provider.timeout"


def test_project_error_fields_ffmpeg_interrupted() -> None:
    msg, code, params = project_error_fields(RuntimeError("ffmpeg exiting normally, received signal 15"))
    assert code == "project.ffmpeg_interrupted"
    assert params is None
    assert msg

    msg, code, _ = project_error_fields(RuntimeError("ffmpeg filter error"), "project.compose_failed")
    assert (msg, code) == ("ffmpeg filter error", "project.compose_failed")


# ---- 科普流水线：失败 / 取消写入 error_code ----


def _fake_session_factory(project: SimpleNamespace):
    """AsyncSessionLocal 替身：db.get 返回同一个 project 对象。"""

    class _Db:
        async def get(self, _model, _pk):
            return project

        async def commit(self) -> None: ...

    @asynccontextmanager
    async def _factory():
        yield _Db()

    return _factory


async def test_pipeline_failure_stores_error_code() -> None:
    from app.models import ProjectStatus
    from app.services import pipeline

    project = SimpleNamespace(status=ProjectStatus.SCRIPTING, error_msg=None, error_code=None, error_params=None)
    with (
        patch.object(pipeline, "AsyncSessionLocal", _fake_session_factory(project)),
        patch.object(pipeline, "_ensure_not_cancelled", AsyncMock()),
        patch.object(pipeline, "_resume_plan", AsyncMock(side_effect=UpstreamError("上游原文 500"))),
        patch.object(pipeline, "publish_progress", AsyncMock()) as progress,
    ):
        with pytest.raises(UpstreamError):
            await pipeline.run_pipeline(1)

    assert project.status == ProjectStatus.FAILED
    assert project.error_code == "provider.failed"
    assert project.error_params is None
    assert "上游原文" in project.error_msg
    event = progress.await_args.args[1]
    assert event["error_code"] == "provider.failed"


async def test_pipeline_cancel_stores_cancelled_code() -> None:
    from app.models import ProjectStatus
    from app.services import pipeline

    project = SimpleNamespace(status=ProjectStatus.IMAGING, error_msg=None, error_code=None, error_params=None)
    with (
        patch.object(pipeline, "AsyncSessionLocal", _fake_session_factory(project)),
        patch.object(pipeline, "_ensure_not_cancelled", AsyncMock(side_effect=pipeline.PipelineCancelled("x"))),
        patch.object(pipeline, "publish_progress", AsyncMock()),
    ):
        with pytest.raises(pipeline.PipelineCancelled):
            await pipeline.run_pipeline(1)

    assert project.status == ProjectStatus.CANCELLED
    assert project.error_code == "project.cancelled"
    assert project.error_msg == "用户取消"


async def test_compose_failure_defaults_to_compose_code() -> None:
    from app.models import ProjectStatus
    from app.services import pipeline

    project = SimpleNamespace(status=ProjectStatus.COMPOSING, error_msg=None, error_code=None, error_params=None)
    with (
        patch.object(pipeline, "AsyncSessionLocal", _fake_session_factory(project)),
        patch.object(pipeline, "publish_progress", AsyncMock()),
    ):
        await pipeline._fail_project_compose(1, RuntimeError("ffmpeg: invalid filter"))

    assert project.status == ProjectStatus.FAILED
    assert project.error_code == "project.compose_failed"


def test_project_runtime_view_prefers_task_error_code() -> None:
    from app.api.projects import _project_runtime_view

    task = SimpleNamespace(
        task_type="project_pipeline",
        status="failed",
        progress_percent=30,
        error_message="网络错误（ReadTimeout）：...",
        error_code="provider.timeout",
        error_params=None,
    )
    project = SimpleNamespace(
        status="FAILED", progress=30, error_msg="旧错误", error_code="project.cancelled", error_params=None,
        active_tasks=[task],
    )
    view = _project_runtime_view(project)
    assert (view.status, view.error_code) == ("FAILED", "provider.timeout")

    project.active_tasks = []
    view = _project_runtime_view(project)
    assert (view.error_msg, view.error_code) == ("旧错误", "project.cancelled")


# ---- 工具记录 ----


def _tool_session_factory(row, user):
    class _Db:
        async def get(self, model, _pk):
            from app.models import ToolRun

            return row if model is ToolRun else user

        async def commit(self) -> None: ...

    @asynccontextmanager
    async def _factory():
        yield _Db()

    return _factory


async def test_tool_run_failure_stores_error_code() -> None:
    from app.services import studio_tools

    row = SimpleNamespace(
        id=5, user_id=1, tool_id="t2i", status="queued", urls=None, params={}, prompt="p",
        error=None, error_code=None, error_params=None, kind="image", preview_url=None,
    )
    user = SimpleNamespace(id=1)
    with (
        patch("app.database.AsyncSessionLocal", _tool_session_factory(row, user)),
        patch.object(studio_tools, "run_billed_ephemeral", AsyncMock(side_effect=UpstreamError("secret"))),
    ):
        out = await studio_tools.execute_image_tool_run(5)

    assert out["ok"] is False
    assert row.status == "failed"
    assert row.error_code == "provider.failed"
    assert row.error == "secret"

    row.status = "queued"
    with (
        patch("app.database.AsyncSessionLocal", _tool_session_factory(row, None)),
    ):
        await studio_tools.execute_image_tool_run(5)
    assert row.error_code == "common.user_not_found"


async def test_poll_image_tool_task_returns_codes() -> None:
    from app.services import studio_tools

    class _Result:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class _Db:
        def __init__(self, value):
            self._value = value

        async def execute(self, _stmt):
            return _Result(self._value)

    user = SimpleNamespace(id=1)
    missing = await studio_tools.poll_image_tool_task(_Db(None), user, "local-1")
    assert missing["error_code"] == "task.not_found"

    failed_row = SimpleNamespace(status="failed", error="原文", error_code=None, error_params=None)
    failed = await studio_tools.poll_image_tool_task(_Db(failed_row), user, "local-1")
    assert failed["error_code"] == "tool.run_failed"


# ---- 401 ----


def test_unauthenticated_requests_return_error_codes() -> None:
    from app.database import get_db
    from app.deps import get_current_user

    app = FastAPI()
    register_app_error_handler(app)

    async def _no_db():
        yield None

    @app.get("/me")
    async def me(user=Depends(get_current_user)) -> dict:  # noqa: B008
        return {"id": user.id}

    app.dependency_overrides[get_db] = _no_db
    client = TestClient(app)

    res = client.get("/me")
    assert res.status_code == 401
    assert res.json()["code"] == "auth.login_required"

    res = client.get("/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401
    assert res.json()["code"] == "auth.session_expired"


def test_api_key_missing_returns_error_code() -> None:
    from app.api.v1 import generation
    from app.database import get_db

    app = FastAPI()
    register_app_error_handler(app)
    app.include_router(generation.router, prefix="/api")

    async def _no_db():
        yield None

    app.dependency_overrides[get_db] = _no_db
    res = TestClient(app).get("/api/v1/tasks/abc")
    assert res.status_code == 401
    assert res.json()["code"] == "auth.api_key_missing"


# ---- 开放 API：上游失败不回传原文 ----


def test_v1_upstream_failure_hides_provider_text(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.v1 import generation
    from app.database import get_db

    app = FastAPI()
    register_app_error_handler(app)
    app.include_router(generation.router, prefix="/api")

    async def _no_db():
        yield None

    async def _fake_billed(_db, _user, *, executor, **_kwargs):
        return SimpleNamespace(id=1), await executor()

    fake_ark = SimpleNamespace(gen_image=AsyncMock(side_effect=UpstreamError("secret upstream body 上游原文")))
    monkeypatch.setattr(generation, "run_billed_ephemeral", _fake_billed)
    monkeypatch.setattr(generation, "get_ark", lambda: fake_ark)
    app.dependency_overrides[get_db] = _no_db
    app.dependency_overrides[generation._resolve_api_user] = lambda: SimpleNamespace(id=1)

    res = TestClient(app).post("/api/v1/images/generations", json={"prompt": "a cat on the moon"})
    assert res.status_code == 502
    body = res.json()
    assert body["code"] == "api.upstream_failed"
    assert body["params"] == {}
    assert "secret" not in res.text and "上游原文" not in res.text


def test_v1_seedance_empty_content_has_code() -> None:
    from app.api.v1 import generation
    from app.database import get_db

    app = FastAPI()
    register_app_error_handler(app)
    app.include_router(generation.router, prefix="/api")

    async def _no_db():
        yield None

    app.dependency_overrides[get_db] = _no_db
    app.dependency_overrides[generation._resolve_api_user] = lambda: SimpleNamespace(id=1)
    res = TestClient(app).post("/api/v1/seedance/tasks", json={"content": []})
    assert res.status_code == 400
    assert res.json()["code"] == "api.content_required"


# ---- 找回密码邮件按语言 ----


def test_reset_email_follows_ui_language() -> None:
    from app.services.password_reset import reset_email_content

    subject, body = reset_email_content("https://x/auth?token=t", "vi")
    assert "Đặt lại mật khẩu" in subject and "https://x/auth?token=t" in body
    subject, body = reset_email_content("https://x", "en")
    assert subject.startswith("Reset")
    subject, _ = reset_email_content("https://x", None)
    assert "Đặt lại" in subject


def test_v1_task_status_hides_provider_error_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /v1/tasks/{id} 失败时只返回固定英文短句 + error_code，不透传上游原文。"""
    from app.api.v1 import generation
    from app.database import get_db

    app = FastAPI()
    register_app_error_handler(app)
    app.include_router(generation.router, prefix="/api")

    class _Result:
        def first(self):
            return SimpleNamespace(id=9, provider_channel_id=None)

    class _Db:
        async def execute(self, _stmt):
            return _Result()

        async def commit(self):
            return None

    async def _db():
        yield _Db()

    async def _poll(_user, _tid, channel_id=None):
        return {"status": "failed", "error": "secret upstream body 上游原文", "urls": []}

    async def _settle(*_a, **_k):
        return None

    monkeypatch.setattr(generation, "poll_video_task", _poll)
    monkeypatch.setattr(generation, "settle_deferred_video_poll", _settle)
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[generation._resolve_api_user] = lambda: SimpleNamespace(id=1)

    res = TestClient(app).get("/api/v1/tasks/cgt-123")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "failed"
    assert body["error_code"] == "api.upstream_failed"
    assert "secret" not in res.text and "上游原文" not in res.text
