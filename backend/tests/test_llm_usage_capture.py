"""H-1: usage thật của chat/completions (token + model route thực chạy) được ghi trong billing_scope và tính tiền."""
from __future__ import annotations

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
    # không có usage → 80 000 token ước tính × model đắt nhất của slot văn bản
    assert ev.model == "gpt-5.6-sol" and ev.estimated is True and ev.charge_fen == 493


async def test_calls_outside_scope_record_nothing(fake_llm) -> None:
    fake_llm.append({"prompt_tokens": 1000, "completion_tokens": 500})
    assert await llm_client.chat_completions("s", "u") == "ok"
    note_llm_usage("gpt-5.6-terra", {"prompt_tokens": 1})
    assert drain_llm_usage() == []
    async with billing_scope(1):
        assert drain_llm_usage() == []   # scope mới không kế thừa lần gọi trước đó
