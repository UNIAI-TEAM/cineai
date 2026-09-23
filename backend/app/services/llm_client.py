"""OpenAI 兼容文字模型客户端（任意兼容上游：Kimi / DeepSeek / OpenAI 等）。"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.services.function_router import resolve_function_candidates
from app.services.providers.base import TransientUpstreamError, is_failover_safe_error, is_transient_http_status
from app.services.providers.openai_adapter import is_official_openai

logger = logging.getLogger(__name__)

# DEFAULT_MAX_TOKENS 分集正文等结构化输出需要足够 completion 空间
DEFAULT_MAX_TOKENS = 32768


class LlmUnavailableError(RuntimeError):
    """文字 LLM 未配置或不可用。"""


# kimi / deepseek-v4 默认 thinking 会占满 token、content 常为空；结构化产出统一关闭
def _llm_extra_body(model: str) -> dict[str, Any]:
    mid = (model or "").strip().lower()
    if mid.startswith("kimi") or mid.startswith("deepseek"):
        return {"thinking": {"type": "disabled"}}
    return {}


# 从 chat/completions 响应提取正文
def _message_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if content:
        return str(content)
    # 部分兼容网关把结果放在 reasoning_content
    reasoning = message.get("reasoning_content")
    return str(reasoning or "")


# 调用 OpenAI 兼容 chat/completions
async def chat_completions(
    system: str,
    user: str,
    *,
    function_id: str = "drama.script",
    temperature: float = 0.6,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = 300.0,
    response_format: dict[str, Any] | None = None,
) -> str:
    """Gọi chat/completions theo route của chức năng; lỗi tạm thời (429/5xx/chưa kết nối) thì thử model kế tiếp."""
    candidates = [r for r in resolve_function_candidates(function_id) if r.upstream_model]
    if not candidates:
        raise LlmUnavailableError("Chưa gán model văn bản. Vào Admin → Cài đặt → Mô hình để cấu hình.")
    last: Exception | None = None
    for route in candidates:
        try:
            model, data = await _post_chat(
                route, system, user, temperature=temperature, max_tokens=max_tokens,
                timeout=timeout, response_format=response_format,
            )
            break
        except Exception as exc:  # noqa: BLE001
            if not is_failover_safe_error(exc):
                raise
            logger.warning("文字 LLM 渠道 %s 暂时不可用（%s），尝试下一个模型", route.channel_id, exc)
            last = exc
    else:
        raise RuntimeError(str(last))
    # Import lười: gói billing nạp nặng và import ngược các module drama/kepu đang dùng llm_client
    from app.services.billing.context import note_llm_usage

    note_llm_usage(model, data.get("usage") if isinstance(data, dict) else None)
    content = _message_content(data)
    logger.info("文字 LLM 返回 content_len=%s", len(content))
    return content


async def _post_chat(
    route: Any,
    system: str,
    user: str,
    *,
    temperature: float,
    max_tokens: int,
    timeout: float,
    response_format: dict[str, Any] | None,
) -> tuple[str, Any]:
    """Gửi một request chat/completions tới một route; trả (model, JSON). 429/5xx → TransientUpstreamError."""
    api_key, model, base = route.api_key, route.upstream_model, route.base_url
    # kimi 系列仅允许 temperature=0.6，其它值会 400
    effective_temperature = 0.6 if model.lower().startswith("kimi") else temperature

    payload: dict[str, Any] = {
        "model": model,
        "temperature": effective_temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    payload["max_completion_tokens" if is_official_openai(base) else "max_tokens"] = max_tokens
    extra = _llm_extra_body(model)
    if extra:
        payload.update(extra)
    if response_format:
        payload["response_format"] = response_format

    logger.info(
        "调用文字 LLM model=%s base=%s user_len=%s max_tokens=%s",
        model,
        base,
        len(user or ""),
        max_tokens,
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if is_transient_http_status(res.status_code):
            raise TransientUpstreamError(f"LLM error {res.status_code}: {res.text[:800]}")
        if res.status_code >= 400:
            raise RuntimeError(f"LLM error {res.status_code}: {res.text[:800]}")
        body = (res.text or "").strip()
        if not body:
            raise RuntimeError(f"LLM 返回空响应体 (HTTP {res.status_code})")
        lowered = body[:256].lower()
        if lowered.startswith("<!doctype") or lowered.startswith("<html"):
            raise RuntimeError(
                f"LLM 渠道 Base URL 配置错误（返回了网页 HTML 而非 API JSON）。"
                f"当前 base={base}，请检查管理后台「模型渠道」的 Base URL 是否为 OpenAI 兼容 API 地址"
                f"（如 https://api.deepseek.com 或 https://api.moonshot.cn/v1），而非网站首页。"
            )
        try:
            data = res.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LLM 响应不是合法 JSON: {body[:200]}") from exc
    return model, data
