# 管理端充值订单：分页列表 + 银行转账确认到账 / 关闭
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database import get_db
from app.deps import get_current_admin
from app.errors import AppError
from app.models import Order, User
from app.schemas import AdminOrderActionBody, AdminOrderListOut, AdminOrderOut, PageMeta
from app.services.billing import topup

router = APIRouter()


@router.get("/orders", response_model=AdminOrderListOut)
async def list_orders(
    status: str | None = None,
    user_id: int | None = None,
    out_trade_no: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminOrderListOut:
    # Paginated recharge orders with owner email
    owner = aliased(User)
    stmt = select(Order, owner.email).outerjoin(owner, owner.id == Order.user_id)
    count_stmt = select(func.count()).select_from(Order)

    if status and status.strip():
        stmt = stmt.where(Order.status == status.strip())
        count_stmt = count_stmt.where(Order.status == status.strip())
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
        count_stmt = count_stmt.where(Order.user_id == user_id)
    if out_trade_no and out_trade_no.strip():
        trade = out_trade_no.strip()
        stmt = stmt.where(Order.out_trade_no == trade)
        count_stmt = count_stmt.where(Order.out_trade_no == trade)

    total = int((await db.execute(count_stmt)).scalar_one() or 0)
    rows = (
        await db.execute(
            stmt.order_by(Order.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()

    items: list[AdminOrderOut] = []
    for order, email in rows:
        data = AdminOrderOut.model_validate(order)
        data.user_email = email
        items.append(data)

    return AdminOrderListOut(items=items, meta=PageMeta(page=page, page_size=page_size, total=total))


async def _order_out(db: AsyncSession, order: Order) -> AdminOrderOut:
    """附带用户邮箱的订单输出。"""
    data = AdminOrderOut.model_validate(order)
    owner = await db.get(User, order.user_id)
    data.user_email = owner.email if owner else None
    return data


@router.post("/orders/{out_trade_no}/confirm", response_model=AdminOrderOut)
async def confirm_order(
    out_trade_no: str,
    body: AdminOrderActionBody | None = None,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminOrderOut:
    """确认银行转账已到账并入账（幂等：已 paid 直接返回）。"""
    note = (body.note if body else "") or ""
    try:
        order = await topup.confirm_order(db, out_trade_no, admin_id=int(admin.id), note=note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn nạp tiền") from exc
    except AppError:
        # 保留错误码交给全局处理器，管理端按 code 翻译
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await _order_out(db, order)


@router.post("/orders/{out_trade_no}/close", response_model=AdminOrderOut)
async def close_order(
    out_trade_no: str,
    body: AdminOrderActionBody | None = None,
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminOrderOut:
    """关闭待支付单（已支付单不可关闭）。"""
    note = (body.note if body else "") or ""
    try:
        order = await topup.close_order_by_admin(db, out_trade_no, note=note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn nạp tiền") from exc
    except AppError:
        # 保留错误码交给全局处理器，管理端按 code 翻译
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await _order_out(db, order)
