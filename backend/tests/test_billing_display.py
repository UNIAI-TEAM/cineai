"""计费依据展示与筛选。"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UsageEvent
from app.services.billing.display import (
    billing_basis_label,
    billing_basis_sql_filter,
    resolve_billing_basis,
)
from tests.conftest import make_user


def test_resolve_billing_basis_estimate():
    assert resolve_billing_basis(estimated=True, raw_usage_json=None) == "estimate"
    assert billing_basis_label("estimate") == "估算"


def test_resolve_billing_basis_upstream_tokens():
    raw = '{"usage": {"total_tokens": 120000}}'
    assert resolve_billing_basis(estimated=False, raw_usage_json=raw) == "upstream_usage"
    assert billing_basis_label("upstream_usage") == "实测(token)"


def test_resolve_billing_basis_upstream_cost():
    raw = '{"usage": {"cost_fen": 500}}'
    assert resolve_billing_basis(estimated=False, raw_usage_json=raw) == "upstream_cost"
    assert billing_basis_label("upstream_cost") == "实测(费用)"


def test_resolve_billing_basis_captured_llm_line_is_upstream_usage_not_cost():
    """Dòng llm_chat gộp từ _captured_llm_usage (đánh dấu llm_calls) mang usage.cost_fen local × token thật,
    không phải upstream báo thẳng chi phí → phải hiện 实测(token), không phải 实测(费用)."""
    raw = '{"model": "gpt-5.6-terra", "llm_calls": 2, "usage": {"total_tokens": 1500, "cost_fen": 6}}'
    assert resolve_billing_basis(estimated=False, raw_usage_json=raw) == "upstream_usage"


def test_resolve_billing_basis_unknown_without_usage():
    assert resolve_billing_basis(estimated=False, raw_usage_json=None) == "unknown"
    assert billing_basis_label("unknown") == "实测(未分类)"


@pytest.mark.asyncio
async def test_billing_basis_sql_filter_cost(db_session: AsyncSession) -> None:
    from app.api.admin.usage import list_usage_events

    user = await make_user(db_session)
    user.email = f"basis-{uuid.uuid4().hex[:8]}@example.com"
    user.role = "admin"
    await db_session.flush()

    db_session.add_all(
        [
            UsageEvent(
                user_id=user.id,
                domain="drama",
                capability="video",
                billing_key="seedance",
                model="m",
                charge_fen=10,
                estimated=False,
                raw_usage_json=json.dumps({"usage": {"cost_fen": 88}}),
            ),
            UsageEvent(
                user_id=user.id,
                domain="drama",
                capability="video",
                billing_key="seedance",
                model="m",
                charge_fen=5,
                estimated=False,
                raw_usage_json=json.dumps({"usage": {"total_tokens": 1000}}),
            ),
            UsageEvent(
                user_id=user.id,
                domain="drama",
                capability="llm",
                billing_key="llm_chat",
                model="m",
                charge_fen=1,
                estimated=True,
            ),
        ]
    )
    await db_session.commit()

    cost_only = await list_usage_events(
        user_id=user.id,
        task_run_id=None,
        project_id=None,
        drama_project_id=None,
        domain=None,
        billing_key=None,
        capability=None,
        estimated=None,
        billing_basis="upstream_cost",
        created_from=None,
        created_to=None,
        page=1,
        page_size=20,
        _admin=user,
        db=db_session,
    )
    assert len(cost_only.items) == 1
    assert cost_only.items[0].billing_basis == "upstream_cost"

    token_only = await list_usage_events(
        user_id=user.id,
        task_run_id=None,
        project_id=None,
        drama_project_id=None,
        domain=None,
        billing_key=None,
        capability=None,
        estimated=None,
        billing_basis="upstream_usage",
        created_from=None,
        created_to=None,
        page=1,
        page_size=20,
        _admin=user,
        db=db_session,
    )
    assert len(token_only.items) == 1
    assert token_only.items[0].billing_basis == "upstream_usage"

    assert billing_basis_sql_filter("invalid") is None


async def _basis_items(db: AsyncSession, admin, basis: str) -> list:
    """以管理端列表接口按计费依据筛选当前用户的用量行。"""
    from app.api.admin.usage import list_usage_events

    out = await list_usage_events(
        user_id=admin.id, task_run_id=None, project_id=None, drama_project_id=None, domain=None,
        billing_key=None, capability=None, estimated=None, billing_basis=basis, created_from=None,
        created_to=None, page=1, page_size=20, _admin=admin, db=db,
    )
    return list(out.items)


@pytest.mark.asyncio
async def test_billing_basis_sql_filter_matches_label_for_captured_llm(db_session: AsyncSession) -> None:
    """带 llm_calls 的 LLM 汇总行标签为 实测(token)，SQL 筛选也必须归入 upstream_usage 而非 upstream_cost。"""
    user = await make_user(db_session)
    user.role = "admin"
    await db_session.flush()
    llm_raw = {"model": "gpt-5.6-terra", "llm_calls": 2, "usage": {"total_tokens": 1500, "cost_fen": 6}}
    db_session.add_all([
        UsageEvent(user_id=user.id, domain="drama", capability="video", billing_key="seedance", model="m",
                   charge_fen=10, estimated=False, raw_usage_json=json.dumps({"usage": {"cost_fen": 88}})),
        UsageEvent(user_id=user.id, domain="drama", capability="llm", billing_key="llm_chat", model="m",
                   charge_fen=6, estimated=False, raw_usage_json=json.dumps(llm_raw)),
    ])
    await db_session.commit()

    cost_items = await _basis_items(db_session, user, "upstream_cost")
    usage_items = await _basis_items(db_session, user, "upstream_usage")
    assert [i.billing_key for i in cost_items] == ["seedance"]
    assert [i.billing_key for i in usage_items] == ["llm_chat"]
    assert all(i.billing_basis == "upstream_cost" for i in cost_items)
    assert all(i.billing_basis == "upstream_usage" for i in usage_items)
