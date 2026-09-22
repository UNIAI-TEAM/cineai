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
