"""Schema admin cho bảng giá provider (`/api/admin/settings/billing/model-rates`)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProviderRateRow(BaseModel):
    """Một dòng giá admin xem/gửi; ràng buộc ngữ nghĩa kiểm ở service để trả thông điệp tiếng Việt."""

    pattern: str = Field(default="")
    unit: str = Field(default="", max_length=32)
    usd: float | None = None
    usd_out: float | None = None
    note: str = Field(default="", max_length=200)


class ProviderRateUnit(BaseModel):
    """Một đơn vị tính giá và nhãn hiển thị tiếng Việt."""

    id: str
    label: str


class UnpricedModel(BaseModel):
    """Model đang được gán nhưng chưa khớp dòng giá nào (sẽ tính theo giá token dự phòng)."""

    channel_id: str
    model: str
    capability: str


class AdminProviderRatesOut(BaseModel):
    """Bảng giá đang áp dụng + bảng mặc định + đơn vị + model chưa có giá + tỉ giá USD→CNY."""

    items: list[ProviderRateRow]
    defaults: list[ProviderRateRow]
    units: list[ProviderRateUnit]
    unpriced_models: list[UnpricedModel]
    usd_cny: float
    updated_at: datetime | None = None


class AdminProviderRatesPut(BaseModel):
    """Thay toàn bộ bảng giá (thứ tự dòng = thứ tự ưu tiên khớp)."""

    items: list[ProviderRateRow] = Field(default_factory=list)
