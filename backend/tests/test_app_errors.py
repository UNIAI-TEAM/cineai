# -*- coding: utf-8 -*-
"""AppError / 错误码目录 / 全局处理器 单测（不需要数据库）。"""
from __future__ import annotations

import copy
import pickle
import re
import string
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.errors import ERRORS, AppError, register_app_error_handler
from app.services.billing.http import (
    http_exception_for_billed_value_error,
    http_exception_for_value_error,
)

CODE_RE = re.compile(r"^[a-z_]+\.[a-z_]+$")
MONEY_FIELDS = {"need", "available", "pending"}

LOCALES_DIR = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n" / "locales"
KEY_RE = re.compile(r"^\s*'([a-z_]+\.[a-z_]+)':", re.MULTILINE)


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


def test_app_error_is_copy_and_pickle_safe() -> None:
    """copy.copy / pickle.dumps+loads 后 code/status/params/detail 保持不变。"""
    original = AppError("billing.insufficient_balance", need_fen=100, available_fen=0)

    copied = copy.copy(original)
    assert copied.code == original.code
    assert copied.status == original.status
    assert copied.params == original.params
    assert copied.detail == original.detail

    restored = pickle.loads(pickle.dumps(original))
    assert restored.code == original.code
    assert restored.status == original.status
    assert restored.params == original.params
    assert restored.detail == original.detail


def test_subclass_survives_clone_copy_and_pickle() -> None:
    """clone / copy / pickle 不把 AppError 子类降级成 AppError。"""
    from app.services.profile import ProfileError

    original = ProfileError("auth.username_too_long", max=64)
    for restored in (original.clone(), copy.copy(original), pickle.loads(pickle.dumps(original))):
        assert type(restored) is ProfileError
        assert restored.params == {"max": 64}


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


def test_billed_helper_keeps_app_error_status() -> None:
    """计费入口：校验类 AppError 保持 400 与 code，不再被统一改成 402。"""
    out = http_exception_for_billed_value_error(AppError("tool.unknown"))
    assert isinstance(out, AppError)
    assert out.status == 400
    assert out.code == "tool.unknown"


def test_billed_helper_plain_value_error_stays_402() -> None:
    out = http_exception_for_billed_value_error(ValueError("余额不足：老格式"))
    assert isinstance(out, HTTPException)
    assert out.status_code == 402


def test_task_target_not_found_keeps_legacy_400() -> None:
    assert AppError("task.target_not_found", target="shot").status == 400


async def test_mock_delay_out_of_range_has_bounds() -> None:
    from types import SimpleNamespace

    from app.services.tasks.handlers import _run_tools_mock_delay

    task = SimpleNamespace(payload={"delay_seconds": 9999})
    with pytest.raises(AppError) as exc_info:
        await _run_tools_mock_delay(task)
    assert exc_info.value.code == "task.payload_out_of_range"
    assert exc_info.value.params == {"field": "delay_seconds", "min": 1, "max": 600}


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


@pytest.mark.parametrize("locale", ["zh", "en", "vi"])
def test_frontend_error_translations_match_catalog(locale: str) -> None:
    src = (LOCALES_DIR / locale / "errors.ts").read_text(encoding="utf-8")
    keys = set(KEY_RE.findall(src))
    assert sorted(set(ERRORS) - keys) == [], f"{locale} 缺少翻译"
    assert sorted(keys - set(ERRORS)) == [], f"{locale} 有多余的码"


def test_drama_api_has_no_chinese_http_detail() -> None:
    """api/drama 下不再直接抛中文 detail 的 HTTPException。"""
    drama_dir = Path(__file__).resolve().parents[1].joinpath("app/api/drama")
    offenders = [
        f"{path.name}: {line.strip()}"
        for path in sorted(drama_dir.glob("*.py"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if "detail=" in line and re.search(r"[一-鿿]", line)
    ]
    assert offenders == []


def test_drama_service_errors_keep_chinese_text_and_code() -> None:
    """漫剧 service 抛 AppError：str() 仍为原中文（TaskRun 落库不变），同时带错误码。"""
    from app.services.agent.parse import SkillParseError, parse_skill_markdown
    from app.services.drama.agents import MAX_DRAMA_EPISODES, append_manual_episode
    from app.services.drama.seed import require_confirmable_episode_body

    with pytest.raises(AppError) as exc_info:
        require_confirmable_episode_body({"episodes": []}, 3)
    assert exc_info.value.code == "drama.episode_script_not_found"
    assert exc_info.value.params == {"number": 3}
    assert str(exc_info.value) == "找不到第 3 集剧本"

    with pytest.raises(AppError) as exc_info:
        append_manual_episode([{"episodeNumber": MAX_DRAMA_EPISODES, "title": "终章", "body": ""}])
    assert exc_info.value.code == "drama.max_episodes"

    with pytest.raises(SkillParseError) as skill_exc:
        parse_skill_markdown("   ")
    assert skill_exc.value.code == "drama.skill_empty"
    assert skill_exc.value.status == 400
