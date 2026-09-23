"""将异常格式化为可展示、非空的错误文案。"""

from __future__ import annotations

from typing import Any

# 已建连、等响应超时（不是连不上）
_READ_TIMEOUT_EXC_NAMES = frozenset({"ReadTimeout"})
# 已建连、发请求体超时
_WRITE_TIMEOUT_EXC_NAMES = frozenset({"WriteTimeout"})
# 建连失败 / 代理不可达（含未细分的 TimeoutException）
_CONNECT_EXC_NAMES = frozenset(
    {
        "ConnectError",
        "ConnectTimeout",
        "PoolTimeout",
        "TimeoutException",
        "NetworkError",
        "ProxyError",
    }
)


def format_exception_message(
    exc: BaseException,
    *,
    fallback: str = "未知错误",
    limit: int = 500,
) -> str:
    """生成带类型名的错误文案；ConnectError 等空 message 时补上可读说明。"""
    name = type(exc).__name__
    detail = str(exc).strip()
    if name in _READ_TIMEOUT_EXC_NAMES:
        tip = detail or "上游已连通但响应超时（图片/视频生成可能超过等待上限）"
        return f"网络错误（{name}）：{tip}"[:limit]
    if name in _WRITE_TIMEOUT_EXC_NAMES:
        tip = detail or "上游已连通但发送请求超时"
        return f"网络错误（{name}）：{tip}"[:limit]
    if name in _CONNECT_EXC_NAMES:
        tip = detail or "无法连接上游服务（请检查网络、代理或上游模型服务是否可达）"
        return f"网络错误（{name}）：{tip}"[:limit]
    if not detail:
        return f"{name}：{fallback}"[:limit]
    if detail.startswith(name):
        return detail[:limit]
    return f"{name}: {detail}"[:limit]


# 内容审核 / 真人拦截类上游报错关键词（原文只进日志，前端按 provider.content_rejected 翻译）
_CONTENT_REJECT_MARKERS = (
    "InputTextSensitive",
    "InputImageSensitive",
    "SensitiveContent",
    "PrivacyInformation",
    "OutputVideoSensitive",
    "OutputImageSensitive",
    "内容审核",
    "疑似真人",
)


def _exc_chain(exc: BaseException) -> list[BaseException]:
    """异常及其 __cause__ / __context__ 链（去重，防环）。"""
    out: list[BaseException] = []
    cur: BaseException | None = exc
    while cur is not None and cur not in out and len(out) < 8:
        out.append(cur)
        cur = cur.__cause__ or cur.__context__
    return out


def stored_error_fields(
    exc: BaseException, default_code: str = "task.execution_failed"
) -> tuple[str, dict[str, Any] | None]:
    """落库用的错误码与参数（任务 / 项目 / 工具记录）：

    - AppError：自身 code / params；
    - 上游（providers.* 抛出的 UpstreamError、httpx 网络异常）：provider.timeout / provider.network_error /
      provider.content_rejected / provider.failed，params 不含上游原文；
    - 文字模型未配置：model.slot_not_configured；
    - 其余：default_code。
    """
    from app.errors import AppError
    from app.services.llm_client import LlmUnavailableError
    from app.services.providers.base import (
        TransientUpstreamError,
        UpstreamError,
        UpstreamNetworkError,
        UpstreamTimeoutError,
    )

    if isinstance(exc, AppError):
        return exc.code, (dict(exc.params) or None)
    chain = _exc_chain(exc)
    text = " ".join(str(e) for e in chain)
    names = {type(e).__name__ for e in chain}
    if any(isinstance(e, LlmUnavailableError) for e in chain):
        return "model.slot_not_configured", None
    if any(marker in text for marker in _CONTENT_REJECT_MARKERS):
        return "provider.content_rejected", None
    if any(isinstance(e, UpstreamTimeoutError) for e in chain) or names & (
        _READ_TIMEOUT_EXC_NAMES | _WRITE_TIMEOUT_EXC_NAMES
    ):
        return "provider.timeout", None
    if any(isinstance(e, UpstreamNetworkError) for e in chain) or names & _CONNECT_EXC_NAMES:
        return "provider.network_error", None
    if any(isinstance(e, (UpstreamError, TransientUpstreamError)) for e in chain):
        return "provider.failed", None
    return default_code, None
