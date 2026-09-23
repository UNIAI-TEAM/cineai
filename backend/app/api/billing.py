# -*- coding: utf-8 -*-
"""钱包、用量与银行转账充值 API。"""
from __future__ import annotations

from datetime import datetime, timezone


from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.errors import AppError
from app.models import Order, Project, UsageEvent, User
from app.models_tasks import TaskRun
from app.services import billing
from app.services.billing import topup
from app.services.billing.money import currency_payload
from app.services.billing.http import http_exception_for_value_error
from app.services.billing.settlement import (
    billing_active,
    ensure_balance_for_task_batch,
)

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()


class CreateOrderBody(BaseModel):
    sku_id: str
    # 兼容旧客户端传 pay_type；当前仅支持银行转账，忽略该值
    pay_type: str | None = None


@router.get("/wallet")
async def wallet(user: User = Depends(get_current_user)) -> dict:
    return {
        "balance_fen": int(user.balance_fen or 0),
        "frozen_fen": int(user.frozen_fen or 0),
        "balance_yuan": round(int(user.balance_fen or 0) / 100, 2),
        "frozen_yuan": round(int(user.frozen_fen or 0) / 100, 2),
        "plan": user.plan or "free",
        "billing_enabled": settings.billing_enabled,
        "markup": settings.billing_markup,
    }


@router.get("/currency")
async def billing_currency() -> dict:
    """展示货币与每分折算系数（公开）。"""
    return currency_payload(get_settings())


@router.get("/skus")
async def list_skus() -> dict:
    """充值包（VND 定价 + 按当前汇率折算的分）与是否开放充值。"""
    return topup.skus_payload(get_settings())


@router.get("/preflight")
async def billing_preflight(
    domain: str = Query(..., min_length=1),
    task_type: str = Query(..., min_length=1),
    count: int = Query(1, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """入队前余额预检：返回单项估算与批量总需求。"""
    if not billing_active(user):
        return {
            "ok": True,
            "billing_enabled": False,
            "balance_fen": int(user.balance_fen or 0),
            "unit_estimate_fen": 0,
            "pending_commitment_fen": 0,
            "requested_total_fen": 0,
            "required_total_fen": 0,
        }
    probe = TaskRun(
        domain=domain.strip(),
        task_type=task_type.strip(),
        requested_by=user.id,
        payload={},
    )
    try:
        summary = await ensure_balance_for_task_batch(db, user, probe, count)
    except ValueError as exc:
        raise http_exception_for_value_error(exc) from exc
    return {
        "ok": True,
        "billing_enabled": True,
        "balance_fen": summary["balance_fen"],
        "balance_yuan": round(summary["balance_fen"] / 100, 2),
        "unit_estimate_fen": summary["unit_estimate_fen"],
        "unit_estimate_yuan": round(summary["unit_estimate_fen"] / 100, 2),
        "pending_commitment_fen": summary["pending_commitment_fen"],
        "pending_commitment_yuan": round(summary["pending_commitment_fen"] / 100, 2),
        "requested_total_fen": summary["requested_total_fen"],
        "requested_total_yuan": round(summary["requested_total_fen"] / 100, 2),
        "required_total_fen": summary["required_total_fen"],
        "required_total_yuan": round(summary["required_total_fen"] / 100, 2),
        "count": int(count),
        "domain": domain.strip(),
        "task_type": task_type.strip(),
    }




@router.post("/orders")
async def create_order(
    body: CreateOrderBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """建银行转账充值单，返回收款信息与转账备注（= 订单号）。"""
    # 下单前先清理该用户已过期的待支付单
    await billing.close_expired_pending_orders(db, user_id=user.id)
    try:
        return await topup.create_bank_transfer_order(db, user, body.sku_id, get_settings())
    except KeyError as exc:
        raise AppError("billing.unknown_package") from exc
    except RuntimeError as exc:
        raise AppError("billing.topup_unavailable") from exc


@router.get("/usage/summary")
async def usage_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """本月 token / 费用汇总，供历史页侧栏展示。"""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(
            func.coalesce(func.sum(UsageEvent.total_tokens), 0),
            func.coalesce(func.sum(UsageEvent.charge_fen), 0),
            func.coalesce(func.sum(UsageEvent.cost_fen), 0),
            func.count(UsageEvent.id),
        ).where(
            UsageEvent.user_id == user.id,
            UsageEvent.created_at >= month_start,
        )
    )
    tokens, charge_fen, cost_fen, calls = result.one()
    return {
        "period": month_start.strftime("%Y-%m"),
        "tokens": int(tokens or 0),
        "charge_fen": int(charge_fen or 0),
        "charge_yuan": round(int(charge_fen or 0) / 100, 2),
        "cost_fen": int(cost_fen or 0),
        "calls": int(calls or 0),
        "balance_fen": int(user.balance_fen or 0),
        "balance_yuan": round(int(user.balance_fen or 0) / 100, 2),
        "frozen_fen": int(user.frozen_fen or 0),
        "frozen_yuan": round(int(user.frozen_fen or 0) / 100, 2),
    }


@router.get("/alerts/pending")
async def billing_alerts_pending(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """待展示的用户额度告警（弹窗）。"""
    from app.services.billing.alerts import list_pending_user_alerts

    rows = await list_pending_user_alerts(db, user.id)
    await db.commit()
    return {
        "items": [
            {
                "id": row.id,
                "kind": row.kind,
                "title": row.title,
                "message": row.message,
                "milestone_fen": int(row.milestone_fen or 0),
                "milestone_yuan": round(int(row.milestone_fen or 0) / 100, 2),
                # 生成告警时的累计扣费；老记录为空时前端只展示里程碑
                "total_charged_fen": (
                    int(row.total_charged_fen) if row.total_charged_fen is not None else None
                ),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }


@router.post("/alerts/{alert_id}/ack")
async def billing_alert_ack(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    from app.services.billing.alerts import acknowledge_user_alert

    ok = await acknowledge_user_alert(db, user.id, alert_id)
    if not ok:
        raise AppError("billing.alert_not_found")
    await db.commit()
    return {"ok": True}


@router.get("/usage/events")
async def usage_events(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """分页返回当前用户的按次扣费记录（新→旧）。"""
    from app.models_drama import DramaProject

    count_stmt = select(func.count()).select_from(UsageEvent).where(UsageEvent.user_id == user.id)
    total = int((await db.execute(count_stmt)).scalar_one() or 0)

    stmt = (
        select(UsageEvent, Project.title, DramaProject.title)
        .outerjoin(Project, UsageEvent.project_id == Project.id)
        .outerjoin(DramaProject, UsageEvent.drama_project_id == DramaProject.id)
        .where(UsageEvent.user_id == user.id)
        .order_by(UsageEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()

    items = []
    for ev, kepu_title, drama_title in rows:
        # context 为旧版中文拼接（兼容保留）；前端用 context_kind / context_title / context_project_id 按语言拼
        if drama_title:
            context = f"漫剧 · {drama_title}"
        elif kepu_title:
            context = f"科普 · {kepu_title}"
        elif ev.project_id:
            context = f"科普 · 项目 #{ev.project_id}"
        elif ev.drama_project_id:
            context = f"漫剧 · 项目 #{ev.drama_project_id}"
        else:
            context = "工具创作"
        if drama_title or ev.drama_project_id:
            context_kind, context_title, context_project_id = "drama", drama_title, ev.drama_project_id
        elif kepu_title or ev.project_id:
            context_kind, context_title, context_project_id = "kepu", kepu_title, ev.project_id
        else:
            context_kind, context_title, context_project_id = "tool", None, None
        charge_fen = int(ev.charge_fen or 0)
        items.append(
            {
                "id": ev.id,
                "billing_key": ev.billing_key,
                "billing_label": billing.billing_key_label(ev.billing_key),
                # 能力类别 llm|image|video|tts|other，前端按语言显示名称（billing_label 仅兼容保留）
                "capability": billing.billing_key_to_capability(ev.billing_key),
                "model": ev.model or "",
                "context": context,
                "context_kind": context_kind,
                "context_title": context_title,
                "context_project_id": context_project_id,
                "total_tokens": int(ev.total_tokens or 0),
                "charge_fen": charge_fen,
                "charge_yuan": round(charge_fen / 100, 2),
                "estimated": bool(ev.estimated),
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
        )
    return {
        "items": items,
        "meta": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/orders")
async def list_orders(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    """充值订单列表（新→旧）；返回前自动关闭过期待支付单。"""
    await billing.close_expired_pending_orders(db, user_id=user.id)
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    items = []
    for o in rows:
        sku = billing.sku_by_id(o.sku_id) or {}
        items.append(
            {
                "out_trade_no": o.out_trade_no,
                "sku_id": o.sku_id,
                "sku_name": str(sku.get("name") or o.sku_id),
                "amount_fen": o.amount_fen,
                "credit_fen": o.credit_fen,
                "pay_type": o.pay_type,
                "pay_amount": o.pay_amount,
                "pay_currency": o.pay_currency,
                "status": o.status,
                "trade_no": o.trade_no,
                "note": o.note,
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
        )
    return {"orders": items}


@router.get("/orders/{out_trade_no}")
async def get_order(
    out_trade_no: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    await billing.close_expired_pending_orders(db, user_id=user.id, out_trade_no=out_trade_no)
    result = await db.execute(select(Order).where(Order.out_trade_no == out_trade_no))
    order = result.scalar_one_or_none()
    if not order or order.user_id != user.id:
        raise AppError("billing.order_not_found")
    return {
        "out_trade_no": order.out_trade_no,
        "status": order.status,
        "amount_fen": order.amount_fen,
        "credit_fen": order.credit_fen,
        "pay_type": order.pay_type,
        "pay_amount": order.pay_amount,
        "pay_currency": order.pay_currency,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    }


@router.post("/orders/{out_trade_no}/close")
async def close_order(
    out_trade_no: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """用户主动取消支付时关闭待支付订单（过期订单由系统自动关闭）。"""
    result = await db.execute(select(Order).where(Order.out_trade_no == out_trade_no))
    order = result.scalar_one_or_none()
    if not order or order.user_id != user.id:
        raise AppError("billing.order_not_found")
    if order.status == "paid":
        raise AppError("billing.order_paid_cannot_close")
    if order.status == "closed":
        return {"out_trade_no": order.out_trade_no, "status": "closed"}
    if order.status != "pending":
        raise AppError("billing.order_cannot_close")
    order.status = "closed"
    await db.commit()
    return {"out_trade_no": order.out_trade_no, "status": "closed"}
