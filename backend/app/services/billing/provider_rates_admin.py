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
    """Model được gán ở slot/override mà không khớp dòng giá nào (theo thứ tự slot rồi override, không trùng)."""
    from app.services.functions import FUNCTION_BY_ID
    from app.services.model_settings import get_routing_snapshot

    snap = snapshot if snapshot is not None else get_routing_snapshot()
    table = rates if rates is not None else get_provider_rates()
    groups = list(snap.function_bindings.slots.items())
    groups += [(FUNCTION_BY_ID[fid].capability, items)
               for fid, items in snap.function_bindings.overrides.items() if fid in FUNCTION_BY_ID]
    seen: set[tuple[str, str]] = set()
    out: list[UnpricedModel] = []
    for capability, items in groups:
        for b in items:
            key = (b.channel_id, b.model)
            if key in seen or match_rate(b.model, table) is not None:
                continue
            seen.add(key)
            out.append(UnpricedModel(channel_id=b.channel_id, model=b.model, capability=capability))
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
