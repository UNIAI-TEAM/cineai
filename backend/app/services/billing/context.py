# -*- coding: utf-8 -*-
"""任务计费上下文：当前 task_run_id + các lần gọi LLM thật (usage + model) trong scope tính tiền."""
from __future__ import annotations

from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncIterator

_current_task_run_id: ContextVar[int | None] = ContextVar("billing_task_run_id", default=None)
# Một list cho mỗi billing_scope, sửa tại chỗ: task con (gather/create_task) chép context vẫn ghi vào cùng list
_llm_usage: ContextVar[list[dict[str, Any]] | None] = ContextVar("billing_llm_usage", default=None)


def get_current_task_run_id() -> int | None:
    return _current_task_run_id.get()


def set_current_task_run_id(task_run_id: int | None) -> None:
    _current_task_run_id.set(task_run_id)


def _tokens(usage: dict[str, Any], *keys: str) -> int:
    """Số token nguyên không âm đầu tiên có trong các khoá; không có → 0."""
    for key in keys:
        try:
            value = int(usage.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 0


def note_llm_usage(model: str, usage: dict[str, Any] | None) -> None:
    """Ghi một lần gọi LLM vào scope tính tiền hiện hành (ngoài scope → bỏ qua).

    Ghi cả khi upstream không trả usage (usage=None/rỗng, total_tokens=0) để `_captured_llm_usage`
    tính đủ phí lần gọi đó bằng ước tính mỗi lần gọi, thay vì âm thầm bỏ sót.
    """
    bucket = _llm_usage.get()
    if bucket is None:
        return
    prompt = completion = total = 0
    if isinstance(usage, dict):
        prompt = _tokens(usage, "prompt_tokens", "input_tokens")
        completion = _tokens(usage, "completion_tokens", "output_tokens")
        total = _tokens(usage, "total_tokens") or prompt + completion
    bucket.append({"model": model or "", "prompt_tokens": prompt, "completion_tokens": completion,
                   "total_tokens": total})


def drain_llm_usage() -> list[dict[str, Any]]:
    """Lấy và xoá các lần gọi LLM đã ghi trong scope hiện hành."""
    bucket = _llm_usage.get()
    if not bucket:
        return []
    out = list(bucket)
    bucket.clear()
    return out


@asynccontextmanager
async def billing_scope(task_run_id: int | None) -> AsyncIterator[None]:
    """Đặt task_run_id hiện hành và mở list ghi usage LLM thật cho scope."""
    token = _current_task_run_id.set(task_run_id)
    usage_token = _llm_usage.set([])
    try:
        yield
    finally:
        _llm_usage.reset(usage_token)
        _current_task_run_id.reset(token)
