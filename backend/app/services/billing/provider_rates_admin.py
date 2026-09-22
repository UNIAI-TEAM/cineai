"""Admin đọc/ghi bảng giá provider trong app_settings.config_json["provider_rates"]."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_settings import AppSettings
from app.schemas_provider_rates import (
    AdminProviderRatesOut,
    AdminProviderRatesPut,
    ProviderRateRow,
    ProviderRateUnit,
    UnpricedModel,
)
from app.services.billing.money import usd_cny_rate
from app.services.billing.provider_rates import (
    DEFAULT_PROVIDER_RATES,
    RATE_UNIT_LABELS,
    RATE_UNITS,
    ProviderRate,
    get_provider_rates,
    match_rate,
    parse_provider_rates,
    rate_to_dict,
    validate_provider_rates,
)


def _row(rate: ProviderRate) -> ProviderRateRow:
    """ProviderRate → dòng schema admin."""
    return ProviderRateRow(**rate_to_dict(rate))


def unpriced_models(snapshot: Any | None = None, rates: list[ProviderRate] | None = None) -> list[UnpricedModel]:
    """Model hiệu lực (provider còn bật + đủ key, qua allowed_bindings) mà không khớp dòng giá nào, không trùng.

    Đi qua từng chức năng trong catalog (không phải slot thô) để tái dùng đúng bộ lọc provider tắt/thiếu key/
    model không còn bật mà `rate_quotes.function_models()` đã dùng khi ước tính (Review Focus #5); binding của
    provider đã tắt hoặc thiếu key không bao giờ được gọi nên không được liệt vào đây.
    """
    from app.services.function_router import allowed_bindings
    from app.services.functions import FUNCTIONS
    from app.services.model_settings import get_routing_snapshot

    snap = snapshot if snapshot is not None else get_routing_snapshot()
    table = rates if rates is not None else get_provider_rates()
    seen: set[tuple[str, str]] = set()
    out: list[UnpricedModel] = []
    for fn in FUNCTIONS:
        for b in allowed_bindings(fn.id, snapshot=snap):
            key = (b.channel_id, b.model)
            if key in seen or match_rate(b.model, table) is not None:
                continue
            seen.add(key)
            out.append(UnpricedModel(channel_id=b.channel_id, model=b.model, capability=fn.capability))
    return out


async def _app_row(db: AsyncSession) -> AppSettings | None:
    """Dòng app_settings duy nhất (id="default")."""
    return (await db.execute(select(AppSettings).where(AppSettings.id == "default"))).scalar_one_or_none()


async def get_provider_rates_admin(db: AsyncSession) -> AdminProviderRatesOut:
    """Bảng giá đang áp dụng (cache process, đã nạp từ DB) kèm dữ liệu phụ cho màn admin."""
    rates = get_provider_rates()
    row = await _app_row(db)
    return AdminProviderRatesOut(
        items=[_row(r) for r in rates],
        defaults=[_row(r) for r in DEFAULT_PROVIDER_RATES],
        units=[ProviderRateUnit(id=u, label=RATE_UNIT_LABELS[u]) for u in RATE_UNITS],
        unpriced_models=unpriced_models(rates=rates),
        usd_cny=usd_cny_rate(),
        updated_at=row.updated_at if row else None,
    )


async def save_provider_rates_admin(db: AsyncSession, body: AdminProviderRatesPut) -> AdminProviderRatesOut:
    """Validate rồi thay toàn bộ bảng giá; lỗi → ValueError (tiếng Việt, tối đa 5 lỗi), cache giữ nguyên."""
    from app.services.model_settings import load_model_settings_cache

    items = [r.model_dump() for r in body.items]
    errors = validate_provider_rates(items)
    if errors:
        raise ValueError("; ".join(errors[:5]))
    await load_model_settings_cache(db)  # bảo đảm có dòng app_settings "default" đã migrate
    row = await _app_row(db)
    config = dict(row.config_json or {})
    config["provider_rates"] = [rate_to_dict(r) for r in parse_provider_rates(items)]
    row.config_json = config
    await db.commit()
    await load_model_settings_cache(db)
    return await get_provider_rates_admin(db)
