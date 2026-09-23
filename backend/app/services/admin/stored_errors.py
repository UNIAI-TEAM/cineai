"""管理端读取落库错误：原文 + 错误码 + params，供管理端按码翻译成越南语（无码时显示原文）。

漫剧后台任务把错误写在 params 里（`<field>` / `<field>_code` / `<field>_params`，见 services/drama/job_errors.py）；
生图 / 生视频写在 params.generation（`error` / `error_code` / `error_params`）。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AdminStoredErrorOut(BaseModel):
    """一条落库错误：message 原文（老数据可能是中文或上游原文），code / params 供按码翻译。"""

    message: str = ""
    code: str | None = None
    params: dict | None = None


def _build(message: Any, code: Any, params: Any) -> AdminStoredErrorOut | None:
    """组装错误对象；原文与错误码都为空时返回 None。"""
    text = str(message).strip() if message is not None else ""
    code_str = str(code).strip() if isinstance(code, str) else ""
    if not text and not code_str:
        return None
    return AdminStoredErrorOut(
        message=text,
        code=code_str or None,
        params=params if isinstance(params, dict) and params else None,
    )


def param_error(params: Any, field: str) -> AdminStoredErrorOut | None:
    """读取 params[field] + field_code + field_params（剧本 / 分集 / 资产抽取等任务错误）。"""
    if not isinstance(params, dict):
        return None
    return _build(params.get(field), params.get(f"{field}_code"), params.get(f"{field}_params"))


def generation_error(params: Any) -> AdminStoredErrorOut | None:
    """读取 params.generation 的生成失败（仅 status=failed 时返回，避免展示已被重试覆盖的旧错误）。"""
    if not isinstance(params, dict):
        return None
    gen = params.get("generation")
    if not isinstance(gen, dict) or str(gen.get("status") or "") != "failed":
        return None
    return _build(gen.get("error"), gen.get("error_code"), gen.get("error_params"))
