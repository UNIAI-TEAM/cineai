# Admin finance daily ledger API
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin
from app.models import User
from app.schemas import AdminFinanceDailyOut
from app.services.admin.finance import build_finance_daily_list

router = APIRouter(prefix="/finance", tags=["admin-finance"])


@router.get("/daily", response_model=AdminFinanceDailyOut)
async def admin_finance_daily(
    days: int = Query(30, ge=1, le=90),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminFinanceDailyOut:
    """Tài chính theo ngày: tiền trừ user, chi phí (cost_fen theo provider_rates), token, lợi nhuận."""
    raw = await build_finance_daily_list(db, days=days)
    return AdminFinanceDailyOut(**raw)
