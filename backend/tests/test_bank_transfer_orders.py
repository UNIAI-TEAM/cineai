# -*- coding: utf-8 -*-
"""银行转账充值：VND 充值包换算、建单指引、未配置收款账户拒单、过期关闭按支付方式。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order
from app.services.billing import close_expired_pending_orders
from app.services.billing.pricing import SKUS, order_expire_seconds, sku_by_id
from app.services.billing import topup

from tests.conftest import make_user


def _settings(**overrides):
    base = {
        "billing_cny_vnd": 3600.0,
        "billing_usd_cny": 7.0,
        "billing_display_currency": "VND",
        "topup_bank_name": "Vietcombank",
        "topup_bank_account": "0011002233",
        "topup_bank_holder": "NGUYEN VAN A",
        "topup_bank_bin": "970436",
        "topup_order_expire_hours": 24,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_sku_quote_converts_vnd_to_fen_with_bonus():
    sku = sku_by_id("topup_1m")
    assert sku is not None
    quote = topup.sku_quote(sku, _settings())
    # 1_000_000 VND / 3600 = 277.78 CNY → 27778 分；+5% → 29167
    assert quote["amount_fen"] == 27778
    assert quote["credit_fen"] == 29167
    assert quote["amount_vnd"] == 1_000_000 and quote["bonus_pct"] == 5


def test_skus_payload_reports_topup_disabled_without_bank_account():
    payload = topup.skus_payload(_settings(topup_bank_account="", topup_bank_holder=""))
    assert payload["topup_enabled"] is False
    assert payload["pay_types"] == ["bank_transfer"]
    assert [s["id"] for s in payload["skus"]] == [s["id"] for s in SKUS]


def test_vietqr_url_only_with_bin():
    info = topup.bank_info(_settings())
    url = topup.vietqr_url(info, 500_000, "PF123")
    assert url.startswith("https://img.vietqr.io/image/970436-0011002233-compact2.png?amount=500000")
    assert "addInfo=PF123" in url
    assert topup.vietqr_url(topup.bank_info(_settings(topup_bank_bin="")), 1, "x") == ""


def test_order_expire_seconds_by_pay_type():
    assert order_expire_seconds("bank_transfer", _settings(topup_order_expire_hours=2)) == 7200
    assert order_expire_seconds("alipay", _settings()) == 300


async def test_create_order_returns_transfer_instructions(db_session: AsyncSession):
    user = await make_user(db_session, balance_fen=0)
    data = await topup.create_bank_transfer_order(db_session, user, "topup_100k", _settings())
    assert data["pay_type"] == "bank_transfer"
    assert data["pay_amount"] == 100_000 and data["pay_currency"] == "VND"
    assert data["transfer_note"] == data["out_trade_no"]
    assert data["bank"]["account"] == "0011002233"
    assert data["expire_seconds"] == 24 * 3600
    order = (
        await db_session.execute(select(Order).where(Order.out_trade_no == data["out_trade_no"]))
    ).scalar_one_or_none()
    assert order is not None and order.status == "pending" and order.pay_amount == 100_000


async def test_create_order_rejects_when_bank_not_configured(db_session: AsyncSession):
    user = await make_user(db_session, balance_fen=0)
    with pytest.raises(RuntimeError):
        await topup.create_bank_transfer_order(db_session, user, "topup_100k", _settings(topup_bank_account=""))
    with pytest.raises(KeyError):
        await topup.create_bank_transfer_order(db_session, user, "topup_nope", _settings())


async def test_bank_transfer_orders_do_not_expire_in_five_minutes(db_session: AsyncSession, monkeypatch):
    user = await make_user(db_session, balance_fen=0)
    ten_min_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
    bank = Order(out_trade_no="BT1", user_id=user.id, sku_id="topup_100k", amount_fen=1, credit_fen=1,
                 pay_type="bank_transfer", status="pending", created_at=ten_min_ago)
    legacy = Order(out_trade_no="AL1", user_id=user.id, sku_id="topup_10", amount_fen=1, credit_fen=1,
                   pay_type="alipay", status="pending", created_at=ten_min_ago)
    db_session.add_all([bank, legacy])
    await db_session.flush()
    await close_expired_pending_orders(db_session, user_id=user.id)
    await db_session.refresh(bank)
    await db_session.refresh(legacy)
    assert bank.status == "pending"
    assert legacy.status == "closed"
