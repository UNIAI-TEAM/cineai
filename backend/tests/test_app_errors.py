# -*- coding: utf-8 -*-
"""AppError / 错误码目录 / 全局处理器 单测（不需要数据库）。"""
from __future__ import annotations

import re
import string

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.errors import ERRORS, AppError, register_app_error_handler
from app.services.billing.http import http_exception_for_value_error

CODE_RE = re.compile(r"^[a-z_]+\.[a-z_]+$")
MONEY_FIELDS = {"need", "available", "pending"}


def _sample_params(template: str) -> dict[str, object]:
    """按模板占位符造参数：金额字段给 *_fen，其余给普通值。"""
    params: dict[str, object] = {}
    for _, field, _, _ in string.Formatter().parse(template):
        if not field:
            continue
        if field in MONEY_FIELDS:
            params[f"{field}_fen"] = 1234
        else:
            params[field] = 7
    return params


@pytest.mark.parametrize("code", sorted(ERRORS))
def test_every_code_is_well_formed_and_renders(code: str) -> None:
    status, template = ERRORS[code]
    assert CODE_RE.match(code), code
    assert 400 <= status <= 599
    exc = AppError(code, **_sample_params(template))
    assert exc.detail and "{" not in exc.detail
    assert str(exc) == exc.detail


def test_unknown_code_raises_key_error() -> None:
    with pytest.raises(KeyError):
        AppError("nope.not_registered")


def test_app_error_is_value_error_and_keeps_params() -> None:
    exc = AppError("project.download_limit", max=50)
    assert isinstance(exc, ValueError)
    assert exc.status == 400
    assert exc.params == {"max": 50}
    assert exc.to_payload() == {"detail": "一次最多打包 50 个", "code": "project.download_limit", "params": {"max": 50}}


def test_status_override() -> None:
    assert AppError("project.not_found", status=410).status == 410


def test_money_detail_has_no_yuan_sign() -> None:
    exc = AppError("billing.insufficient_balance", need_fen=1200, available_fen=300)
    assert exc.status == 402
    assert "¥" not in exc.detail
    assert exc.detail.startswith("余额不足")
    assert exc.params == {"need_fen": 1200, "available_fen": 300}


def test_handler_returns_code_and_params() -> None:
    app = FastAPI()
    register_app_error_handler(app)

    @app.get("/boom")
    async def boom() -> None:
        raise AppError("project.download_limit", max=50)

    res = TestClient(app).get("/boom")
    assert res.status_code == 400
    assert res.json() == {"detail": "一次最多打包 50 个", "code": "project.download_limit", "params": {"max": 50}}


def test_http_helper_passes_app_error_through() -> None:
    original = AppError("billing.insufficient_balance", need_fen=100, available_fen=0)
    out = http_exception_for_value_error(original)
    assert isinstance(out, AppError)
    assert out.code == "billing.insufficient_balance"
    assert out.status == 402
    assert out.params == original.params


def test_http_helper_plain_value_error_is_400() -> None:
    out = http_exception_for_value_error(ValueError("余额不足：老格式"))
    assert isinstance(out, HTTPException)
    assert out.status_code == 400


def test_task_payload_missing_field_has_code() -> None:
    from app.services.tasks.handlers import _require_int

    with pytest.raises(AppError) as exc_info:
        _require_int(None, "project_id")
    assert exc_info.value.code == "task.invalid_payload"
    assert exc_info.value.params == {"field": "project_id"}


def test_tool_router_maps_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """工具入口：参数错误 400 带码；未知异常 500 且不回传原始报错。"""
    from app.api import tools as tools_api
    from app.database import get_db
    from app.deps import get_current_user

    app = FastAPI()
    register_app_error_handler(app)
    app.include_router(tools_api.router, prefix="/api")

    class _User:
        id = 1

    async def _fake_db():
        class _Db:
            async def commit(self) -> None: ...
        yield _Db()

    app.dependency_overrides[get_current_user] = lambda: _User()
    app.dependency_overrides[get_db] = _fake_db

    async def _prompt_missing(*_a, **_k):
        raise AppError("tool.prompt_required")

    monkeypatch.setattr(tools_api, "enqueue_image_tool", _prompt_missing)
    client = TestClient(app)
    res = client.post("/api/tools/run", data={"tool_id": "t2i"})
    assert res.status_code == 400
    assert res.json()["code"] == "tool.prompt_required"

    async def _boom(*_a, **_k):
        raise RuntimeError("upstream secret stack")

    monkeypatch.setattr(tools_api, "enqueue_image_tool", _boom)
    res = client.post("/api/tools/run", data={"tool_id": "t2i"})
    assert res.status_code == 500
    assert res.json()["code"] == "tool.run_failed"
    assert "secret" not in res.text


def test_projects_api_has_no_chinese_http_detail() -> None:
    """projects.py 不再直接抛中文 detail 的 HTTPException。"""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1].joinpath("app/api/projects.py").read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in src.splitlines()
        if "detail=" in line and re.search(r"[一-鿿]", line)
    ]
    assert offenders == []
