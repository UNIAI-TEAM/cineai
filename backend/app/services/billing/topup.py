# -*- coding: utf-8 -*-
"""银行转账充值：建单、管理员确认到账 / 关闭。

流程：用户选充值包 → 建 pending 单并展示收款信息（备注 = 订单号）→ 用户转账 →
管理员在后台确认到账（行锁 + 幂等）→ `credit_topup` 入账。未配置收款账号时不可下单。
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import Order, User
from app.services.billing.money import display_currency, vnd_to_fen
from app.services.billing.pricing import SKUS, order_expire_seconds, sku_by_id
from app.services.billing.settlement import credit_topup

PAY_TYPE_BANK_TRANSFER = "bank_transfer"
VIETQR_IMAGE_BASE = "https://img.vietqr.io/image"


def bank_info(settings: Settings | None = None) -> dict[str, str]:
    """收款账户信息（管理端配置）。"""
    s = settings or get_settings()
    return {
        "name": str(getattr(s, "topup_bank_name", "") or "").strip(),
        "account": str(getattr(s, "topup_bank_account", "") or "").strip(),
        "holder": str(getattr(s, "topup_bank_holder", "") or "").strip(),
        "bin": str(getattr(s, "topup_bank_bin", "") or "").strip(),
    }


def topup_enabled(settings: Settings | None = None) -> bool:
    """是否已配置收款账号（账号与户名齐全才开放充值）。"""
    info = bank_info(settings)
    return bool(info["account"] and info["holder"])


def sku_quote(sku: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    """按当前汇率把 VND 充值包换算成分：amount_fen / credit_fen。"""
    amount_vnd = int(sku["amount_vnd"])
    bonus_pct = int(sku.get("bonus_pct") or 0)
    amount_fen = vnd_to_fen(amount_vnd, settings)
    credit_fen = int(round(amount_fen * (100 + bonus_pct) / 100))
    return {
        "id": str(sku["id"]),
        "name": str(sku["name"]),
        "amount_vnd": amount_vnd,
        "bonus_pct": bonus_pct,
        "amount_fen": amount_fen,
        "credit_fen": credit_fen,
        "recommended": bool(sku.get("recommended", False)),
    }


def skus_payload(settings: Settings | None = None) -> dict[str, Any]:
    """GET /api/billing/skus 响应体。"""
    s = settings or get_settings()
    return {
        "skus": [sku_quote(sku, s) for sku in SKUS],
        "pay_types": [PAY_TYPE_BANK_TRANSFER],
        "topup_enabled": topup_enabled(s),
        "currency": "VND",
    }


def vietqr_url(info: dict[str, str], amount: int, note: str) -> str:
    """有银行 BIN 时生成 VietQR 图片地址，否则返回空串。"""
    if not (info.get("bin") and info.get("account")):
        return ""
    query = f"amount={int(amount)}&addInfo={quote(note)}&accountName={quote(info.get('holder') or '')}"
    return f"{VIETQR_IMAGE_BASE}/{info['bin']}-{info['account']}-compact2.png?{query}"


def new_out_trade_no(user_id: int) -> str:
    return f"PF{int(time.time())}{int(user_id):04d}{uuid.uuid4().hex[:8]}"


async def create_bank_transfer_order(
    db: AsyncSession,
    user: User,
    sku_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """建 pending 单并返回转账指引。未知包抛 KeyError；未开放充值抛 RuntimeError。"""
    s = settings or get_settings()
    sku = sku_by_id(sku_id)
    if not sku:
        raise KeyError(sku_id)
    if not topup_enabled(s):
        raise RuntimeError("充值暂未开放：尚未配置收款账户")
    quote_ = sku_quote(sku, s)
    order = Order(
        out_trade_no=new_out_trade_no(int(user.id)),
        user_id=int(user.id),
        sku_id=quote_["id"],
        amount_fen=quote_["amount_fen"],
        credit_fen=quote_["credit_fen"],
        pay_type=PAY_TYPE_BANK_TRANSFER,
        pay_amount=quote_["amount_vnd"],
        pay_currency="VND",
        status="pending",
    )
    db.add(order)
    await db.commit()
    return order_instructions(order, s)


def order_instructions(order: Order, settings: Settings | None = None) -> dict[str, Any]:
    """POST /api/billing/orders 响应体（转账指引）。"""
    s = settings or get_settings()
    info = bank_info(s)
    sku = sku_by_id(order.sku_id) or {}
    pay_amount = int(order.pay_amount or 0)
    return {
        "out_trade_no": order.out_trade_no,
        "sku_id": order.sku_id,
        "sku_name": str(sku.get("name") or order.sku_id),
        "pay_type": order.pay_type,
        "amount_fen": int(order.amount_fen),
        "credit_fen": int(order.credit_fen),
        "pay_amount": pay_amount,
        "pay_currency": order.pay_currency or "VND",
        "bank": info,
        "transfer_note": order.out_trade_no,
        "vietqr_url": vietqr_url(info, pay_amount, order.out_trade_no),
        "expire_seconds": order_expire_seconds(order.pay_type, s),
        "display_currency": display_currency(s),
    }


async def confirm_order(
    db: AsyncSession,
    out_trade_no: str,
    *,
    admin_id: int,
    note: str = "",
) -> Order:
    """管理员确认到账：行锁串行化，已 paid 直接幂等返回；非 pending 抛 ValueError。"""
    result = await db.execute(select(Order).where(Order.out_trade_no == out_trade_no).with_for_update())
    order = result.scalar_one_or_none()
    if order is None:
        raise LookupError(out_trade_no)
    if order.status == "paid":
        return order
    if order.status != "pending":
        raise ValueError("订单已关闭，无法确认到账")
    user = await db.get(User, order.user_id)
    if user is None:
        raise LookupError(f"user:{order.user_id}")
    order.status = "paid"
    order.paid_at = datetime.now(timezone.utc)
    order.trade_no = f"admin:{int(admin_id)}"
    order.note = (note or "").strip()[:255] or None
    await credit_topup(
        db,
        user,
        int(order.credit_fen),
        ref_type="order",
        ref_id=order.out_trade_no,
        note=f"{order.pay_type}:admin:{int(admin_id)}",
    )
    await db.commit()
    return order


async def close_order_by_admin(db: AsyncSession, out_trade_no: str, *, note: str = "") -> Order:
    """管理员关闭待支付单；已支付单不可关闭。"""
    result = await db.execute(select(Order).where(Order.out_trade_no == out_trade_no).with_for_update())
    order = result.scalar_one_or_none()
    if order is None:
        raise LookupError(out_trade_no)
    if order.status == "paid":
        raise ValueError("已支付订单无法关闭")
    if order.status == "pending":
        order.status = "closed"
        if note:
            order.note = note.strip()[:255]
        await db.commit()
    return order
