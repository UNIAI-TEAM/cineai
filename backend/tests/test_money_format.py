# -*- coding: utf-8 -*-
"""展示货币层：分 → VND / USD 换算与格式化。"""
from __future__ import annotations

from types import SimpleNamespace

from app.services.billing.money import (
    currency_payload,
    display_currency,
    fen_to_amount,
    format_amount,
    format_money,
    per_fen_rates,
    vnd_to_fen,
)


def _s(**kw):
    base = {"billing_display_currency": "VND", "billing_cny_vnd": 3600.0, "billing_usd_cny": 7.0}
    base.update(kw)
    return SimpleNamespace(**base)


def test_rates_and_conversion():
    rates = per_fen_rates(_s())
    assert rates["VND"] == 36.0
    assert abs(rates["USD"] - 1 / 700) < 1e-9
    assert fen_to_amount(10000, "VND", _s()) == 360000.0
    assert fen_to_amount(10000, "USD", _s()) == 14.29
    assert vnd_to_fen(100_000, _s()) == 2778


def test_format():
    assert format_amount(1234567, "VND") == "1.234.567 ₫"
    assert format_amount(12.5, "USD") == "$12.50"
    assert format_money(10000, settings=_s()) == "360.000 ₫"
    assert format_money(10000, "USD", _s()) == "$14.29"


def test_display_currency_fallback_and_payload():
    assert display_currency(_s(billing_display_currency="usd")) == "USD"
    assert display_currency(_s(billing_display_currency="EUR")) == "VND"
    payload = currency_payload(_s())
    assert payload["default"] == "VND" and payload["options"] == ["VND", "USD"]
    assert set(payload["per_fen"]) == {"VND", "USD"}
