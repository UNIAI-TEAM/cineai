"""Admin: tài chính theo ngày — tiền trừ user vs chi phí local (cost_fen tính theo provider_rates)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UsageEvent


def _utc_today() -> date:
    """Ngày UTC hiện tại, khớp cửa sổ danh sách tài chính."""
    return datetime.now(UTC).date()


async def _local_usage_daily(db: AsyncSession, *, since: date, until: date) -> dict[str, dict[str, int]]:
    """Gộp usage_events theo ngày: tiền trừ, chi phí, token."""
    day_expr = cast(UsageEvent.created_at, Date)
    rows = (
        await db.execute(
            select(
                day_expr.label("day"),
                func.coalesce(func.sum(UsageEvent.charge_fen), 0).label("charge_fen"),
                func.coalesce(func.sum(UsageEvent.cost_fen), 0).label("cost_fen"),
                func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("tokens"),
            )
            .where(day_expr >= since, day_expr <= until)
            .group_by(day_expr)
            .order_by(day_expr.asc())
        )
    ).all()
    return {
        str(row.day)[:10]: {
            "charge_fen": int(row.charge_fen or 0),
            "cost_fen": int(row.cost_fen or 0),
            "tokens": int(row.tokens or 0),
        }
        for row in rows
    }


def _profit_fen(*, charge_fen: int, cost_fen: int) -> int:
    """Lợi nhuận = tiền trừ user − chi phí."""
    return int(charge_fen - cost_fen)


async def build_finance_daily_list(db: AsyncSession, *, days: int = 30) -> dict[str, Any]:
    """Chuỗi N ngày gần nhất + tổng; actual_cost_fen = cost_fen (không còn đối chiếu upstream)."""
    window_days = max(1, min(90, int(days)))
    today = _utc_today()
    start = today - timedelta(days=window_days - 1)
    local_map = await _local_usage_daily(db, since=start, until=today)

    series: list[dict[str, Any]] = []
    totals: dict[str, Any] = {"charge_fen": 0, "cost_fen": 0, "tokens": 0, "actual_cost_fen": 0, "profit_fen": 0}
    cur = start
    while cur <= today:
        key = cur.isoformat()
        hit = local_map.get(key) or {"charge_fen": 0, "cost_fen": 0, "tokens": 0}
        charge_fen, cost_fen, tokens = hit["charge_fen"], hit["cost_fen"], hit["tokens"]
        profit_fen = _profit_fen(charge_fen=charge_fen, cost_fen=cost_fen)
        series.append({
            "date": key,
            "charge_fen": charge_fen,
            "cost_fen": cost_fen,
            "tokens": tokens,
            "actual_cost_fen": cost_fen,
            "profit_fen": profit_fen,
            "profit_pct": round(profit_fen / charge_fen * 100.0, 2) if charge_fen > 0 else None,
        })
        totals["charge_fen"] += charge_fen
        totals["cost_fen"] += cost_fen
        totals["tokens"] += tokens
        totals["actual_cost_fen"] += cost_fen
        totals["profit_fen"] += profit_fen
        cur += timedelta(days=1)
    if totals["charge_fen"] > 0:
        totals["profit_pct"] = round(totals["profit_fen"] / totals["charge_fen"] * 100.0, 2)
    return {"days": window_days, "totals": totals, "series": series}
