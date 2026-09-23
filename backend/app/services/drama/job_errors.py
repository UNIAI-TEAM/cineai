"""漫剧后台任务落库错误：短文案 + 错误码 / params（前端按界面语言翻译）。

- 剧本 / 分集 / 分镜规划等任务：`user_job_error` 把异常归类为业务码，`set_job_error` / `clear_job_error`
  按 `<field>` + `<field>_code` + `<field>_params` 写入 params（与 seed.set_seed_error 同一模式）；
- 生图 / 生视频：`gen_error_fields` 只给能确定的分类码，其余返回 None，前端继续按原文细分（审核、音频过短等）；
- 生成进度文案：`gen_progress` 在中文 message 之外附带 message_key / message_params。

原始上游报错只写服务端日志（logger.exception 在调用处），不回传请求 id / JSON / 堆栈。
"""

from __future__ import annotations

import re
from typing import Any

from app.errors import AppError
from app.services.exc_format import transport_error_category
from app.services.llm_client import LlmUnavailableError

# USER_ERROR_LIMIT: 落库文案最大长度
USER_ERROR_LIMIT = 200

# "LLM error 401: {...}" (llm_client) 和 "HTTP 401" / "status 401"
_STATUS_RE = re.compile(r"(?:LLM error|HTTP|status(?:_code)?)[\s:=]*([1-5]\d\d)\b", re.IGNORECASE)


def _upstream_status(exc: BaseException) -> int | None:
    """上游 HTTP 状态码：status_code / response.status_code 属性，或从报错文案中读取。"""
    for obj in (exc, getattr(exc, "response", None)):
        code = getattr(obj, "status_code", None)
        if isinstance(code, int) and 100 <= code <= 599:
            return code
    m = _STATUS_RE.search(str(exc))
    return int(m.group(1)) if m else None


def _coded(code: str, **params: Any) -> tuple[str, str, dict[str, Any] | None]:
    """按错误码生成 (中文文案, code, params)。"""
    err = AppError(code, **params)
    return err.detail[:USER_ERROR_LIMIT], code, (dict(params) or None)


def user_job_error(exc: BaseException) -> tuple[str, str, dict[str, Any] | None]:
    """把后台任务异常转成 (短文案, 错误码, params)。

    - AppError：保留自身 code / params；
    - 文字模型未配置：model.slot_not_configured；
    - 上游网络 / 鉴权 / 限流 / 故障 / 拒绝：drama.upstream_*；
    - 其余：drama.gen_failed（原始报错只进日志）。
    """
    if isinstance(exc, AppError):
        return str(exc).strip()[:USER_ERROR_LIMIT], exc.code, (dict(exc.params) or None)
    if isinstance(exc, LlmUnavailableError):
        return _coded("model.slot_not_configured")
    if transport_error_category(exc) is not None:
        return _coded("drama.upstream_network")
    status = _upstream_status(exc)
    if status in (401, 403):
        return _coded("drama.upstream_auth")
    if status == 429:
        return _coded("drama.upstream_rate_limit")
    if status is not None and status >= 500:
        return _coded("drama.upstream_server")
    if status is not None and status >= 400:
        return _coded("drama.upstream_rejected")
    return _coded("drama.gen_failed")


def set_job_error(params: dict[str, Any], field: str, exc: BaseException) -> str:
    """记录任务失败：params[field] 文案 + field_code / field_params；返回文案。"""
    text, code, err_params = user_job_error(exc)
    set_job_error_code(params, field, code, err_params, text=text)
    return text


def set_job_error_code(
    params: dict[str, Any],
    field: str,
    code: str,
    err_params: dict[str, Any] | None = None,
    *,
    text: str | None = None,
) -> None:
    """按错误码记录任务失败（文案默认取错误码的中文模板）。"""
    params[field] = text if text is not None else AppError(code, **(err_params or {})).detail
    params[f"{field}_code"] = code
    if err_params:
        params[f"{field}_params"] = err_params
    else:
        params.pop(f"{field}_params", None)


def clear_job_error(params: dict[str, Any], field: str, *, keep_key: bool = False) -> None:
    """清除任务失败记录；keep_key=True 时文案字段保留为 None（兼容旧接口的显式 null）。"""
    if keep_key:
        params[field] = None
    else:
        params.pop(field, None)
    params.pop(f"{field}_code", None)
    params.pop(f"{field}_params", None)


def gen_error_fields(exc: BaseException) -> tuple[str | None, dict[str, Any] | None]:
    """生图 / 生视频失败的错误码：AppError 自身码，超时 / 网络归类，其余 None（前端按原文细分）。"""
    if isinstance(exc, AppError):
        return exc.code, (dict(exc.params) or None)
    category = transport_error_category(exc)
    if category == "timeout":
        return "drama.gen_timeout", None
    if category == "network":
        return "drama.gen_network", None
    return None, None


def with_error_code(
    gen: dict[str, Any], code: str | None, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """给 params.generation 附上 error_code / error_params（code 为空时清除旧值）。"""
    if code:
        gen["error_code"] = code
        if params:
            gen["error_params"] = params
        else:
            gen.pop("error_params", None)
    else:
        gen.pop("error_code", None)
        gen.pop("error_params", None)
    return gen


def gen_progress(key: str, text: str, **params: Any) -> dict[str, Any]:
    """生成进度文案：中文 message（兼容旧前端 / 日志）+ message_key / message_params（前端翻译）。"""
    out: dict[str, Any] = {"message": text, "message_key": key}
    if params:
        out["message_params"] = params
    return out
