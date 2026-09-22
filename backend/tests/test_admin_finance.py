"""Tài chính theo ngày: chi phí thật = cost_fen local (provider_rates), lợi nhuận = tiền trừ − chi phí."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.admin.finance import _profit_fen, build_finance_daily_list
from tests.conftest import make_user
from tests.test_admin_stats import _add_usage, _utc_days_ago


def test_profit_fen_is_charge_minus_cost() -> None:
    assert _profit_fen(charge_fen=200, cost_fen=120) == 80


async def test_finance_daily_list_uses_local_cost(db_session: AsyncSession) -> None:
    """Dữ liệu mới phản ánh vào đúng ngày; actual_cost_fen == cost_fen (so tăng thêm, chịu DB test dùng chung)."""
    user = await make_user(db_session)
    target_day = _utc_days_ago(5)
    key = target_day.date().isoformat()
    before = next(r for r in (await build_finance_daily_list(db_session, days=30))["series"] if r["date"] == key)

    await _add_usage(db_session, user_id=user.id, charge_fen=200, cost_fen=120, total_tokens=5000,
                     created_at=target_day, capability="video", billing_key="seedance2:video0")
    await db_session.commit()

    out = await build_finance_daily_list(db_session, days=30)
    after = next(r for r in out["series"] if r["date"] == key)
    assert after["charge_fen"] - before["charge_fen"] == 200
    assert after["cost_fen"] - before["cost_fen"] == 120
    assert after["actual_cost_fen"] == after["cost_fen"]
    assert after["profit_fen"] == after["charge_fen"] - after["cost_fen"]
    assert set(out) == {"days", "totals", "series"}
