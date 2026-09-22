"""H-1: usage thật của chat/completions (token + model route thực chạy) được ghi trong billing_scope và tính tiền."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services import llm_client
from app.services.billing.context import billing_scope, drain_llm_usage, note_llm_usage
from app.services.billing.usage import record_llm_chat_line
from tests.conftest import make_task, make_user

_REAL_CLIENT = httpx.AsyncClient


@pytest.fixture
def fake_llm(monkeypatch):
    """chat_completions đi qua route giả `gpt-5.6-terra`; usage trả về lấy từ danh sách `usages` (None = không có)."""
    usages: list[dict | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Trả completion kèm usage kế tiếp trong hàng đợi."""
        body = {"choices": [{"message": {"content": "ok"}}]}
        usage = usages.pop(0) if usages else None
        if usage is not None:
            body["usage"] = usage
        return httpx.Response(200, json=body)

    route = SimpleNamespace(api_key="k", upstream_model="gpt-5.6-terra", base_url="https://api.openai.com/v1")
    monkeypatch.setattr(llm_client, "resolve_function_route", lambda _fid: route)
    monkeypatch.setattr(llm_client.httpx, "AsyncClient",
                        lambda **kw: _REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(get_settings(), "billing_usd_cny", 7.0)
    monkeypatch.setattr(get_settings(), "billing_est_llm_tokens", 80_000)
    return usages


async def _scoped_line(db: AsyncSession, calls: int):
    """Trong billing_scope: gọi LLM `calls` lần rồi ghi một dòng llm_chat."""
    user = await make_user(db)
    task = await make_task(db, user, domain="drama", task_type="episode_script")
    async with billing_scope(task.id):
        for _ in range(calls):
            await llm_client.chat_completions("s", "u")
        return await record_llm_chat_line(db, user_id=user.id, domain="drama")


async def test_one_call_with_usage_exact_fen(db_session: AsyncSession, fake_llm, priced_routing) -> None:
    fake_llm.append({"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500})
    ev = await _scoped_line(db_session, 1)
    # 1000 × 2 + 500 × 12 USD/M = 0.008 USD × 7 = 5.6 → 6 fen
    assert ev.model == "gpt-5.6-terra" and ev.estimated is False
    assert (ev.prompt_tokens, ev.completion_tokens, ev.total_tokens) == (1000, 500, 1500)
    assert ev.cost_fen == ev.charge_fen == 6


async def test_two_calls_summed(db_session: AsyncSession, fake_llm, priced_routing) -> None:
    fake_llm.extend([{"prompt_tokens": 1000, "completion_tokens": 500}] * 2)
    ev = await _scoped_line(db_session, 2)
    assert ev.model == "gpt-5.6-terra" and ev.total_tokens == 3000
    assert ev.cost_fen == ev.charge_fen == 12 and ev.estimated is False


async def test_no_usage_falls_back_to_estimate(db_session: AsyncSession, fake_llm, priced_routing) -> None:
    fake_llm.append(None)
    ev = await _scoped_line(db_session, 1)
    # Không có usage nhưng đã biết model thực đã gọi (gpt-5.6-terra) → tính theo giá model đó với
    # 80 000 token ước tính mỗi lần gọi (không còn đoán sang model đắt nhất của slot)
    assert ev.model == "gpt-5.6-terra" and ev.estimated is False and ev.charge_fen == 280


async def test_calls_outside_scope_record_nothing(fake_llm) -> None:
    fake_llm.append({"prompt_tokens": 1000, "completion_tokens": 500})
    assert await llm_client.chat_completions("s", "u") == "ok"
    note_llm_usage("gpt-5.6-terra", {"prompt_tokens": 1})
    assert drain_llm_usage() == []
    async with billing_scope(1):
        assert drain_llm_usage() == []   # scope mới không kế thừa lần gọi trước đó


async def test_mixed_scope_with_and_without_usage_bills_both(db_session: AsyncSession, fake_llm, priced_routing) -> None:
    """Một scope có cả lần gọi trả usage thật lẫn lần không trả usage: cộng đủ phí của cả hai."""
    fake_llm.extend([{"prompt_tokens": 1000, "completion_tokens": 500}, None])
    ev = await _scoped_line(db_session, 2)
    # 6 fen (usage thật) + 280 fen (không usage, ước tính 80 000 token theo giá gpt-5.6-terra)
    assert ev.model == "gpt-5.6-terra" and ev.estimated is False
    assert ev.total_tokens == 1500  # chỉ cộng token thật đo được; lần không usage không có token báo cáo
    assert ev.cost_fen == ev.charge_fen == 6 + 280


async def test_gather_child_task_writes_into_parent_scope(
    db_session: AsyncSession, fake_llm, priced_routing
) -> None:
    """asyncio.gather sao chép context nhưng list usage là cùng một object: task con vẫn ghi vào scope cha."""
    fake_llm.extend([{"prompt_tokens": 1000, "completion_tokens": 500}] * 2)
    user = await make_user(db_session)
    task = await make_task(db_session, user, domain="drama", task_type="episode_script")
    async with billing_scope(task.id):
        await asyncio.gather(
            llm_client.chat_completions("s", "u"),
            llm_client.chat_completions("s", "u"),
        )
        ev = await record_llm_chat_line(db_session, user_id=user.id, domain="drama")
    assert ev.total_tokens == 3000 and ev.cost_fen == ev.charge_fen == 12 and ev.estimated is False


async def test_closed_scope_undrained_calls_do_not_leak(fake_llm) -> None:
    """Scope đóng mà không drain (không ghi dòng llm_chat) thì lần gọi bên trong không rò sang scope kế tiếp."""
    fake_llm.append({"prompt_tokens": 1000, "completion_tokens": 500})
    async with billing_scope(1):
        await llm_client.chat_completions("s", "u")
        # cố tình không gọi record_llm_chat_line / drain_llm_usage trước khi scope đóng
    async with billing_scope(2):
        assert drain_llm_usage() == []
