# -*- coding: utf-8 -*-
"""展示货币层：钱包内部仍以「分」（1/100 CNY）记账，对外只按 VND / USD 展示。

汇率来自配置：`billing_cny_vnd`（1 CNY 折 VND）与 `billing_usd_cny`（1 USD 折 CNY）。
`per_fen[c]` = 1 分折合货币 c 的数值，前端 amount = fen × per_fen[c]。
"""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings

SUPPORTED_CURRENCIES: tuple[str, ...] = ("VND", "USD")
DEFAULT_CNY_VND = 3600.0
DEFAULT_USD_CNY = 7.0


def _cny_vnd(settings: Settings) -> float:
    try:
        rate = float(getattr(settings, "billing_cny_vnd", None) or DEFAULT_CNY_VND)
    except (TypeError, ValueError):
        rate = DEFAULT_CNY_VND
    return rate if rate > 0 else DEFAULT_CNY_VND


def _usd_cny(settings: Settings) -> float:
    try:
        rate = float(getattr(settings, "billing_usd_cny", None) or DEFAULT_USD_CNY)
    except (TypeError, ValueError):
        rate = DEFAULT_USD_CNY
    return rate if rate > 0 else DEFAULT_USD_CNY


def display_currency(settings: Settings | None = None) -> str:
    """默认展示货币；非法值回落 VND。"""
    s = settings or get_settings()
    raw = str(getattr(s, "billing_display_currency", "") or "").strip().upper()
    return raw if raw in SUPPORTED_CURRENCIES else "VND"


def per_fen_rates(settings: Settings | None = None) -> dict[str, float]:
    """每分折合各货币的系数。"""
    s = settings or get_settings()
    return {
        "VND": _cny_vnd(s) / 100.0,
        "USD": 1.0 / (100.0 * _usd_cny(s)),
    }


def fen_to_amount(fen: int, currency: str, settings: Settings | None = None) -> float:
    """分 → 货币金额（VND 取整，USD 保留两位）。"""
    rates = per_fen_rates(settings)
    code = currency.upper() if currency and currency.upper() in rates else display_currency(settings)
    value = int(fen) * rates[code]
    return float(round(value)) if code == "VND" else round(value, 2)


def vnd_to_fen(amount_vnd: int | float, settings: Settings | None = None) -> int:
    """VND → 分（四舍五入，至少 1 分）。"""
    s = settings or get_settings()
    return max(1, int(round(float(amount_vnd) / _cny_vnd(s) * 100)))


def format_amount(amount: float, currency: str) -> str:
    """按货币惯例格式化已换算金额：VND `1.000.000 ₫`，USD `$12.34`。"""
    code = (currency or "").upper()
    if code == "USD":
        return f"${amount:,.2f}"
    grouped = f"{int(round(amount)):,}".replace(",", ".")
    return f"{grouped} ₫"


def format_money(fen: int, currency: str | None = None, settings: Settings | None = None) -> str:
    """分 → 按展示货币格式化的字符串（用于对用户/管理员的提示文案）。"""
    code = (currency or display_currency(settings)).upper()
    return format_amount(fen_to_amount(fen, code, settings), code)


def currency_payload(settings: Settings | None = None) -> dict[str, Any]:
    """GET /api/billing/currency 的响应体。"""
    s = settings or get_settings()
    return {
        "default": display_currency(s),
        "options": list(SUPPORTED_CURRENCIES),
        "per_fen": per_fen_rates(s),
    }
