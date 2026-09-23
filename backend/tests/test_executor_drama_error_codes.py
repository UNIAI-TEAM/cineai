# -*- coding: utf-8 -*-
"""executor 失败收尾：漫剧资产 / 分镜 generation 保留已登记错误码（不需要数据库）。"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.tasks import executor


class _FakeDb:
    def __init__(self, obj):
        self.obj = obj

    async def get(self, _model, _id):
        return self.obj


def _task(**kw):
    base = dict(domain="drama", asset_id=5, task_type="asset_image", error_code=None, error_params=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_registered_error_fields_ignores_exception_class_names() -> None:
    assert executor._registered_error_fields(_task(error_code="RuntimeError", error_params={"x": 1})) == (None, None)
    assert executor._registered_error_fields(_task(error_code="drama.gen_timeout", error_params={})) == (
        "drama.gen_timeout",
        {},
    )


async def test_asset_generation_keeps_existing_coded_failure() -> None:
    gen = {"status": "failed", "error": "x", "error_code": "drama.gen_no_image_url"}
    asset = SimpleNamespace(params={"generation": dict(gen)})
    await executor._fail_drama_asset_generation_if_needed(_FakeDb(asset), _task(), "RuntimeError: boom")
    assert asset.params["generation"] == gen


async def test_asset_generation_writes_registered_code() -> None:
    asset = SimpleNamespace(params={"generation": {"status": "running"}})
    task = _task(error_code="billing.insufficient_balance", error_params={"need_fen": 10, "available_fen": 0})
    await executor._fail_drama_asset_generation_if_needed(_FakeDb(asset), task, "余额不足")
    gen = asset.params["generation"]
    assert gen["status"] == "failed"
    assert gen["error_code"] == "billing.insufficient_balance"
    assert gen["error_params"] == {"need_fen": 10, "available_fen": 0}


async def test_asset_generation_without_code_keeps_text_only() -> None:
    asset = SimpleNamespace(params={})
    await executor._fail_drama_asset_generation_if_needed(_FakeDb(asset), _task(error_code="ValueError"), "boom")
    assert asset.params["generation"] == {"status": "failed", "error": "boom"}
