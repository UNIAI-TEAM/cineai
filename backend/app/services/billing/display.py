# -*- coding: utf-8 -*-
"""用量展示：计费依据标签与筛选。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Integer, and_, cast, func, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.elements import ColumnElement

from app.models import UsageEvent
from app.services.billing.pricing import parse_upstream_cost_fen
from app.services.billing.provider_rates import usage_block

_BASIS_LABELS = {
    "estimate": "估算",
    "upstream_usage": "实测(token)",
    "upstream_cost": "实测(费用)",
    "unknown": "实测(未分类)",
}

_UPSTREAM_COST_JSON_KEYS = (
    "cost_fen",
    "cost_cents",
)


def resolve_billing_basis(*, estimated: bool, raw_usage_json: str | None = None) -> str:
    """推断计费依据：estimate | upstream_usage | upstream_cost | unknown。"""
    if estimated:
        return "estimate"
    raw: dict[str, Any] | None = None
    if raw_usage_json:
        try:
            parsed = json.loads(raw_usage_json)
            if isinstance(parsed, dict):
                raw = parsed
        except json.JSONDecodeError:
            raw = None
    if isinstance(raw, dict) and raw.get("llm_calls"):
        # 由 _captured_llm_usage 汇总：usage.cost_fen 是本地 provider_rates × token 算出，非上游直接报价
        return "upstream_usage"
    usage = usage_block(raw)
    if isinstance(usage, dict):
        if parse_upstream_cost_fen({"usage": usage}) is not None:
            return "upstream_cost"
        if int(usage.get("total_tokens") or 0) > 0:
            return "upstream_usage"
    return "unknown"


def billing_basis_label(basis: str) -> str:
    return _BASIS_LABELS.get(basis, basis or "—")


def _raw_usage_jsonb() -> ColumnElement[Any]:
    return cast(UsageEvent.raw_usage_json, JSONB)


def _usage_has_upstream_cost_clause() -> ColumnElement[Any]:
    """JSON 块内是否含上游费用字段（与 parse_upstream_cost_fen 键集合一致）。"""
    raw = _raw_usage_jsonb()
    usage = raw["usage"]
    return or_(*[usage.has_key(key) for key in _UPSTREAM_COST_JSON_KEYS])


def _usage_has_upstream_tokens_clause() -> ColumnElement[Any]:
    raw = _raw_usage_jsonb()
    usage = raw["usage"]
    return cast(func.coalesce(usage["total_tokens"].astext, "0"), Integer) > 0


def billing_basis_sql_filter(basis: str) -> ColumnElement[bool] | None:
    """按计费依据生成 UsageEvent SQL 筛选条件；未知 basis 返回 None。"""
    normalized = (basis or "").strip().lower()
    if normalized == "estimate":
        return UsageEvent.estimated.is_(True)
    if normalized == "upstream":
        return UsageEvent.estimated.is_(False)
    # 与 resolve_billing_basis 一致：带 llm_calls 的 LLM 汇总行归 upstream_usage（其 cost_fen 为本地价目算出）
    has_llm_calls = _raw_usage_jsonb().has_key("llm_calls")
    if normalized == "upstream_cost":
        return and_(
            UsageEvent.estimated.is_(False),
            UsageEvent.raw_usage_json.isnot(None),
            ~has_llm_calls,
            _usage_has_upstream_cost_clause(),
        )
    if normalized == "upstream_usage":
        return and_(
            UsageEvent.estimated.is_(False),
            UsageEvent.raw_usage_json.isnot(None),
            or_(
                has_llm_calls,
                and_(~_usage_has_upstream_cost_clause(), _usage_has_upstream_tokens_clause()),
            ),
        )
    return None
